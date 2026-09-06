import uuid
from dataclasses import dataclass
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
    source_filename: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )


@dataclass(frozen=True)
class ChunkSearchResult:
    chunk: ChunkModel
    l2_distance: float


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(
        self,
        document_id: str,
        source_filename: str,
        page_number: int,
        chunk_index: int,
        text: str,
        embedding: list[float],
    ) -> ChunkModel:
        chunk = ChunkModel(
            document_id=document_id,
            source_filename=source_filename,
            page_number=page_number,
            chunk_index=chunk_index,
            text=text,
            embedding=embedding,
        )
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def search_similar(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[ChunkSearchResult]:
        distance = ChunkModel.embedding.l2_distance(query_embedding).label(
            "l2_distance"
        )
        stmt = (
            select(ChunkModel, distance).order_by(distance).limit(top_k)
        )
        result = await self.session.execute(stmt)
        return [
            ChunkSearchResult(chunk=row.ChunkModel, l2_distance=float(row.l2_distance))
            for row in result
        ]
