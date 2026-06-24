from io import BytesIO

from pypdf import PdfReader
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chunker import Chunker
from app.domain.document import Document
from app.infrastructure.embeddings import EmbeddingService
from app.infrastructure.repositories import ChunkRepository


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

    async def execute(self, filename: str, file_content: bytes) -> dict:
        text = self._extract_text_from_pdf(file_content)
        document = Document(name=filename, content=text)
        chunks = self.chunker.split(text, document_id=document.id)

        if not chunks:
            return {
                "document_id": document.id,
                "chunk_count": 0,
                "chunks": [],
            }

        texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed(texts)

        saved_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            model = await self.repository.insert(
                document_id=chunk.document_id,
                chunk_index=chunk.index,
                text=chunk.text,
                embedding=embedding,
            )
            saved_chunks.append(
                {
                    "id": model.id,
                    "chunk_index": model.chunk_index,
                    "text_preview": model.text[:200],
                }
            )

        await self.session.commit()

        return {
            "document_id": document.id,
            "chunk_count": len(saved_chunks),
            "chunks": saved_chunks,
        }

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        reader = PdfReader(BytesIO(file_content))
        texts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                texts.append(page_text)
        return "\n".join(texts)


class SearchUseCase:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service
        self.repository = ChunkRepository(session)

    async def execute(self, query: str, top_k: int = 5) -> list[dict]:
        embeddings = await self.embedding_service.embed([query])
        query_embedding = embeddings[0]
        results = await self.repository.search_similar(
            query_embedding, top_k=top_k
        )
        return [
            {
                "id": r.id,
                "document_id": r.document_id,
                "chunk_index": r.chunk_index,
                "text": r.text,
            }
            for r in results
        ]
