from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import get_embedding_service, router
from app.infrastructure.db import dispose_engine, init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    embedding_service = None
    try:
        embedding_service = get_embedding_service()
        await init_db()
        yield
    finally:
        try:
            if embedding_service is not None:
                await embedding_service.close()
        finally:
            get_embedding_service.cache_clear()
            await dispose_engine()

app = FastAPI(
    title="Financial Document Vector Retrieval",
    description="PoC for PDF ingestion and vector retrieval over financial reports",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "motor-rag-financeiro"}
