from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases import (
    InvalidPdfError,
    NoExtractableTextError,
    SearchUseCase,
    UploadUseCase,
)
from app.infrastructure.db import get_session
from app.infrastructure.embeddings import EmbeddingService, create_embedding_service

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class UploadChunkResponse(BaseModel):
    id: str
    source_filename: str
    page: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    text_preview: str


class UploadResponse(BaseModel):
    document_id: str
    source_filename: str
    chunk_count: int = Field(ge=1)
    chunks: list[UploadChunkResponse]


class SearchResultResponse(BaseModel):
    chunk_id: str
    document_id: str
    source_filename: str
    page: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    text: str
    l2_distance: float = Field(ge=0)


class SearchResponse(BaseModel):
    results: list[SearchResultResponse]
    count: int = Field(ge=0)


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return create_embedding_service()


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    use_case = UploadUseCase(session, embedding_service)
    try:
        result = await use_case.execute(filename=file.filename, file_content=content)
    except (InvalidPdfError, NoExtractableTextError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UploadResponse.model_validate(result)


@router.post("/search", response_model=SearchResponse)
async def search_chunks(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> SearchResponse:
    use_case = SearchUseCase(session, embedding_service)
    results = await use_case.execute(query=request.query, top_k=request.top_k)
    return SearchResponse.model_validate(
        {"results": results, "count": len(results)}
    )
