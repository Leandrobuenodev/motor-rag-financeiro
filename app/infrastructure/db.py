from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from app.config import settings
from app.infrastructure.embeddings import EMBEDDING_DIMENSION
from app.infrastructure.repositories import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        vector_type = await conn.scalar(
            text(
                "SELECT format_type(attribute.atttypid, attribute.atttypmod) "
                "FROM pg_attribute AS attribute "
                "JOIN pg_class AS relation ON relation.oid = attribute.attrelid "
                "JOIN pg_namespace AS namespace "
                "ON namespace.oid = relation.relnamespace "
                "WHERE relation.relname = 'chunks' "
                "AND attribute.attname = 'embedding' "
                "AND namespace.nspname = current_schema() "
                "AND NOT attribute.attisdropped"
            )
        )
        expected_vector_type = f"vector({EMBEDDING_DIMENSION})"
        if vector_type != expected_vector_type:
            raise RuntimeError(
                "Existing chunks table uses an incompatible embedding dimension "
                f"({vector_type}); expected {expected_vector_type}. Recreate the local "
                "PoC database volume before starting this version."
            )

        # Keep volumes from the earlier provenance schema compatible.
        await conn.execute(
            text(
                "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS "
                "source_filename TEXT"
            )
        )
        await conn.execute(
            text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS page_number INTEGER")
        )
        await conn.execute(
            text(
                "UPDATE chunks SET source_filename = 'unknown' "
                "WHERE source_filename IS NULL"
            )
        )
        await conn.execute(
            text("UPDATE chunks SET page_number = 1 WHERE page_number IS NULL")
        )
        await conn.execute(
            text("ALTER TABLE chunks ALTER COLUMN source_filename SET NOT NULL")
        )
        await conn.execute(
            text("ALTER TABLE chunks ALTER COLUMN page_number SET NOT NULL")
        )


async def dispose_engine() -> None:
    await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
