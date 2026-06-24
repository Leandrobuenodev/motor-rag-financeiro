from fastapi import FastAPI

app = FastAPI(
    title="Motor RAG Financeiro",
    description="Motor de busca vetorial local para relatórios financeiros",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "motor-rag-financeiro"}
