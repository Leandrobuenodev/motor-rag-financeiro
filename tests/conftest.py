import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.infrastructure.embeddings import SimulatedEmbeddingService
from app.infrastructure.repositories import Base, ChunkRepository

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    schema_name = f"test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with admin_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        execution_options={
            "schema_translate_map": {None: schema_name},
        },
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        await admin_engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def repository(db_session: AsyncSession) -> ChunkRepository:
    return ChunkRepository(db_session)


@pytest.fixture
def embedding_service() -> SimulatedEmbeddingService:
    return SimulatedEmbeddingService(dimension=1536)


@pytest_asyncio.fixture
async def client(db_engine, monkeypatch: pytest.MonkeyPatch):
    import app.infrastructure.db as db_module
    from app.main import app

    monkeypatch.setattr(db_module, "engine", db_engine)
    monkeypatch.setattr(
        db_module,
        "async_session",
        async_sessionmaker(
            db_engine, class_=AsyncSession, expire_on_commit=False
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
