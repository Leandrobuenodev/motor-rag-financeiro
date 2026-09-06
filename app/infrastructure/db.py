from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from app.config import settings
from app.infrastructure.repositories import Base

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        # Keep existing local PoC volumes compatible with the current schema.
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
