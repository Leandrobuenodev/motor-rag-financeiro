from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases import SearchUseCase, UploadUseCase
from app.infrastructure.db import get_session
from app.infrastructure.embeddings import SimulatedEmbeddingService

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


def get_embedding_service() -> SimulatedEmbeddingService:
    return SimulatedEmbeddingService()


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    embedding_service: SimulatedEmbeddingService = Depends(
        get_embedding_service
    ),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    use_case = UploadUseCase(session, embedding_service)
    result = await use_case.execute(filename=file.filename, file_content=content)
    return result


@router.post("/search")
async def search_chunks(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
    embedding_service: SimulatedEmbeddingService = Depends(
        get_embedding_service
    ),
):
    use_case = SearchUseCase(session, embedding_service)
    results = await use_case.execute(query=request.query, top_k=request.top_k)
    return {"results": results, "count": len(results)}
