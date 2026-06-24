import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ChunkModel(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(
        self,
        document_id: str,
        chunk_index: int,
        text: str,
        embedding: list[float],
    ) -> ChunkModel:
        chunk = ChunkModel(
            document_id=document_id,
            chunk_index=chunk_index,
            text=text,
            embedding=embedding,
        )
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def search_similar(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[ChunkModel]:
        stmt = (
            select(ChunkModel)
            .order_by(ChunkModel.embedding.l2_distance(query_embedding))
            .limit(top_k)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

