from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import get_answer_service, get_embedding_service, router
from app.config import settings
from app.infrastructure.db import dispose_engine, init_db

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    embedding_service = None
    answer_service = None
    try:
        embedding_service = get_embedding_service()
        answer_service = get_answer_service()
        await init_db()
        yield
    finally:
        try:
            try:
                if answer_service is not None:
                    await answer_service.close()
            finally:
                if embedding_service is not None:
                    await embedding_service.close()
        finally:
            get_answer_service.cache_clear()
            get_embedding_service.cache_clear()
            await dispose_engine()

app = FastAPI(
    title="Grounded Financial Document QA",
    description=(
        "PoC for local semantic retrieval and grounded answers over financial PDFs"
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def portfolio_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "motor-rag-financeiro",
        "embedding_provider": settings.embedding_provider,
        "answer_provider": settings.answer_provider,
        "answer_model": settings.answer_model,
    }
