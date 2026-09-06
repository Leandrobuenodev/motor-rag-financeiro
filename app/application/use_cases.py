from io import BytesIO
from typing import TypedDict

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chunker import Chunk, Chunker
from app.domain.document import Document
from app.infrastructure.answers import AnswerService, GroundingPassage
from app.infrastructure.embeddings import EmbeddingService
from app.infrastructure.repositories import ChunkRepository


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
        results = await self.repository.search_similar(
            query_embedding, top_k=top_k
        )
        return [
            {
                "chunk_id": result.chunk.id,
                "document_id": result.chunk.document_id,
                "source_filename": result.chunk.source_filename,
                "page": result.chunk.page_number,
                "chunk_index": result.chunk.chunk_index,
                "text": result.chunk.text,
                "l2_distance": result.l2_distance,
            }
            for result in results
        ]


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
