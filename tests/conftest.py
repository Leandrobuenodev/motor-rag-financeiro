import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from app.infrastructure.embeddings import SimulatedEmbeddingService
from app.infrastructure.repositories import Base, ChunkRepository
from app.main import app

TEST_DATABASE_URL = (
    "postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb"
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def repository(db_session: AsyncSession) -> ChunkRepository:
    return ChunkRepository(db_session)


@pytest_asyncio.fixture
def embedding_service() -> SimulatedEmbeddingService:
    return SimulatedEmbeddingService(dimension=1536)
