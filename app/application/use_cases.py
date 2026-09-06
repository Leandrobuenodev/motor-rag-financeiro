import asyncio
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import TypedDict

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chunker import Chunk, Chunker
from app.domain.document import Document
from app.infrastructure.answers import AnswerService, GroundingPassage
from app.infrastructure.embeddings import EmbeddingService
from app.infrastructure.repositories import ChunkModel, ChunkRepository


class InvalidPdfError(ValueError):
    pass


class NoExtractableTextError(ValueError):
    pass


class UploadedChunk(TypedDict):
    id: str
    source_filename: str
    page: int
    chunk_index: int
    text_preview: str


class UploadResult(TypedDict):
    document_id: str
    source_filename: str
    chunk_count: int
    chunks: list[UploadedChunk]


class SearchResult(TypedDict):
    chunk_id: str
    document_id: str
    source_filename: str
    page: int
    chunk_index: int
    text: str
    l2_distance: float


class AnswerCitation(TypedDict):
    source_id: int
    chunk_id: str
    document_id: str
    source_filename: str
    page: int
    chunk_index: int


class AnswerResult(TypedDict):
    answer: str
    insufficient_evidence: bool
    citations: list[AnswerCitation]
    retrieved_passages: list[SearchResult]


@dataclass
class FusedCandidate:
    chunk: ChunkModel
    distance: float
    score: float


class UploadUseCase:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        chunker: Chunker | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service
        self.chunker = chunker or Chunker()
        self.repository = ChunkRepository(session)

    async def execute(self, filename: str, file_content: bytes) -> UploadResult:
        pages = self._extract_pages_from_pdf(file_content)
        document = Document(
            name=filename,
            content="\n".join(page_text for _, page_text in pages),
        )

        chunks_with_pages: list[tuple[Chunk, int]] = []
        next_chunk_index = 0
        for page_number, page_text in pages:
            page_chunks = self.chunker.split(
                page_text,
                document_id=document.id,
                start_index=next_chunk_index,
            )
            chunks_with_pages.extend(
                (chunk, page_number) for chunk in page_chunks
            )
            next_chunk_index += len(page_chunks)

        texts = [chunk.text for chunk, _ in chunks_with_pages]
        embeddings = await self.embedding_service.embed_documents(texts)

        saved_chunks: list[UploadedChunk] = []
        for (chunk, page_number), embedding in zip(
            chunks_with_pages, embeddings, strict=True
        ):
            model = await self.repository.insert(
                document_id=chunk.document_id,
                source_filename=filename,
                page_number=page_number,
                chunk_index=chunk.index,
                text=chunk.text,
                embedding=embedding,
            )
            saved_chunks.append(
                {
                    "id": model.id,
                    "source_filename": model.source_filename,
                    "page": model.page_number,
                    "chunk_index": model.chunk_index,
                    "text_preview": model.text[:200],
                }
            )

        await self.session.commit()

        return {
            "document_id": document.id,
            "source_filename": filename,
            "chunk_count": len(saved_chunks),
            "chunks": saved_chunks,
        }

    def _extract_pages_from_pdf(self, file_content: bytes) -> list[tuple[int, str]]:
        if b"%PDF-" not in file_content[:1024]:
            raise InvalidPdfError("The uploaded file is not a valid PDF")

        try:
            reader = PdfReader(BytesIO(file_content))
            pages = []
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    pages.append((page_number, page_text))
        except (PyPdfError, EOFError, ValueError) as exc:
            raise InvalidPdfError("The PDF is invalid or corrupted") from exc

        if not pages:
            raise NoExtractableTextError(
                "The PDF contains no extractable text; OCR is not supported"
            )
        return pages


class SearchUseCase:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service
        self.repository = ChunkRepository(session)

    async def execute(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query_embedding = await self.embedding_service.embed_query(query)
        # Keep a broad internal pool; only the final top_k passages reach the
        # answer model. This prevents a weak semantic rank from hiding an exact
        # financial-term match.
        candidate_limit = max(300, top_k * 20)
        semantic = await self.repository.search_similar(
            query_embedding, top_k=candidate_limit
        )
        normalized_query = self._normalize_query(query)
        lexical = await self.repository.search_lexical(
            normalized_query, top_k=candidate_limit
        )

        # Reciprocal Rank Fusion keeps the two rank scales comparable and makes
        # exact report terminology competitive with semantic matches.
        fused: dict[str, FusedCandidate] = {}
        for rank, semantic_result in enumerate(semantic, start=1):
            fused[semantic_result.chunk.id] = FusedCandidate(
                chunk=semantic_result.chunk,
                distance=semantic_result.l2_distance,
                score=1.0 / (60 + rank),
            )
        for rank, lexical_result in enumerate(lexical, start=1):
            item = fused.setdefault(
                lexical_result.chunk.id,
                FusedCandidate(
                    chunk=lexical_result.chunk, distance=2.0, score=0.0
                ),
            )
            item.score += 1.0 / (60 + rank)

        query_tokens = self._tokens(normalized_query)
        ranked = sorted(
            fused.values(),
            key=lambda item: (
                item.score
                + self._metric_bonus(normalized_query, item.chunk.text)
                + 0.1
                * self._overlap(
                    query_tokens, self._tokens(item.chunk.text)
                ),
                -item.distance,
            ),
            reverse=True,
        )[:top_k]
        results = [self._result(item) for item in ranked]
        expanded = await asyncio.gather(
            *(self._expand_context(result) for result in results)
        )
        return list(expanded)

    @staticmethod
    def _metric_bonus(query: str, text: str) -> float:
        query_lower = query.casefold()
        text_tokens = SearchUseCase._tokens(text)
        aliases = (
            ("lucro", "líquido", "ajustado"),
            ("margem", "financeira", "bruta"),
            ("inadimplência", "inad", "90d"),
            ("índice", "basileia"),
            ("carteira", "crédito", "expandida"),
        )
        for alias in aliases:
            if all(term.casefold() in query_lower for term in alias):
                normalized_alias = SearchUseCase._tokens(" ".join(alias))
                if len(normalized_alias & text_tokens) >= max(
                    2, len(normalized_alias) - 1
                ):
                    return 0.5
        return 0.0

    async def _expand_context(self, result: SearchResult) -> SearchResult:
        text = result["text"]
        # Tables often flatten into numeric rows. Keep a small same-page window so
        # period headers and their values reach the generator together.
        if not (
            len(re.findall(r"\d", text)) >= 3
            and (
                "%" in text
                or re.search(
                    r"\b(?:mar|jun|sep|dec|1t|2t|3t|4t)\b", text, re.I
                )
            )
        ):
            return result
        neighbors = await self.repository.get_neighbors(
            result["document_id"], result["page"], result["chunk_index"]
        )
        context = "\n\n".join(chunk.text for chunk in neighbors)
        if context and text not in context:
            context = f"{context}\n\n{text}"
        return {**result, "text": context or text}

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Add stable bilingual finance terminology for lexical recall."""
        normalized = query
        aliases = {
            "adjusted net income": "lucro líquido ajustado",
            "gross financial margin": "margem financeira bruta",
            "90-day delinquency ratio": "inadimplência inad+90d",
            "basel ratio": "índice de basileia",
            "expanded credit portfolio": "carteira de crédito expandida",
        }
        lowered = query.casefold()
        for english, portuguese in aliases.items():
            if english in lowered:
                normalized = f"{normalized} {portuguese}"
        return normalized

    @staticmethod
    def _tokens(value: str) -> set[str]:
        normalized = unicodedata.normalize("NFKD", value)
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        return set(re.findall(r"[a-z0-9]{3,}", normalized.lower()))

    @staticmethod
    def _overlap(query_tokens: set[str], text_tokens: set[str]) -> float:
        return len(query_tokens & text_tokens) / max(len(query_tokens), 1)

    @staticmethod
    def _result(item: FusedCandidate) -> SearchResult:
        chunk = item.chunk
        return {
            "chunk_id": chunk.id,
            "document_id": chunk.document_id,
            "source_filename": chunk.source_filename,
            "page": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "l2_distance": item.distance,
        }


class AnswerUseCase:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        answer_service: AnswerService,
    ) -> None:
        self.search = SearchUseCase(session, embedding_service)
        self.answer_service = answer_service

    async def execute(self, question: str, top_k: int = 5) -> AnswerResult:
        retrieved = await self.search.execute(question, top_k=top_k)
        if not retrieved:
            return self._insufficient_result(retrieved)

        passages = [
            GroundingPassage(source_id=index, text=result["text"])
            for index, result in enumerate(retrieved, start=1)
        ]
        generated = await self.answer_service.generate(question, passages)

        unique_source_ids = list(dict.fromkeys(generated.source_ids))
        retrieved_by_id = {
            index: result for index, result in enumerate(retrieved, start=1)
        }
        has_untrusted_source = any(
            source_id not in retrieved_by_id for source_id in unique_source_ids
        )
        if (
            generated.insufficient_evidence
            or not unique_source_ids
            or has_untrusted_source
        ):
            return self._insufficient_result(
                retrieved,
                answer=(
                    generated.answer if generated.insufficient_evidence else None
                ),
            )

        citations = [
            self._citation_from_result(source_id, retrieved_by_id[source_id])
            for source_id in unique_source_ids
        ]
        return {
            "answer": generated.answer,
            "insufficient_evidence": False,
            "citations": citations,
            "retrieved_passages": retrieved,
        }

    @staticmethod
    def _citation_from_result(
        source_id: int, result: SearchResult
    ) -> AnswerCitation:
        return {
            "source_id": source_id,
            "chunk_id": result["chunk_id"],
            "document_id": result["document_id"],
            "source_filename": result["source_filename"],
            "page": result["page"],
            "chunk_index": result["chunk_index"],
        }

    @staticmethod
    def _insufficient_result(
        retrieved: list[SearchResult], answer: str | None = None
    ) -> AnswerResult:
        return {
            "answer": answer
            or (
                "The retrieved passages do not contain enough evidence to answer "
                "this question."
            ),
            "insufficient_evidence": True,
            "citations": [],
            "retrieved_passages": retrieved,
        }
