import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.embeddings import SimulatedEmbeddingService
from app.infrastructure.repositories import ChunkRepository


class TestChunkRepository:
    @pytest.mark.anyio
    async def test_insert_and_search_similar(
        self,
        db_session: AsyncSession,
        repository: ChunkRepository,
        embedding_service: SimulatedEmbeddingService,
    ):
        texts = [
            "Receita líquida da empresa no trimestre foi de R$ 500 milhões.",
            "O lucro operacional apresentou queda de 12% em relação ao ano anterior.",
            "A previsão do tempo indica sol para os próximos dias.",
        ]
        embeddings = await embedding_service.embed(texts)

        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            await repository.insert(
                document_id="test-doc-1",
                chunk_index=i,
                text=text,
                embedding=emb,
            )
        await db_session.commit()

        query_embedding = (
            await embedding_service.embed(
                ["Receita e lucro da empresa no trimestre"]
            )
        )[0]
        results = await repository.search_similar(query_embedding, top_k=2)

        assert len(results) == 2
        assert results[0].document_id == "test-doc-1"
        assert any("Receita" in r.text for r in results)

    @pytest.mark.anyio
    async def test_insert_multiple_documents(
        self,
        db_session: AsyncSession,
        repository: ChunkRepository,
        embedding_service: SimulatedEmbeddingService,
    ):
        e1 = (await embedding_service.embed(["Balanço ativo circulante"]))[0]
        e2 = (await embedding_service.embed(["Demonstrativo de resultado"]))[0]

        await repository.insert(
            document_id="doc-a",
            chunk_index=0,
            text="Balanço ativo circulante",
            embedding=e1,
        )
        await repository.insert(
            document_id="doc-b",
            chunk_index=0,
            text="Demonstrativo de resultado",
            embedding=e2,
        )
        await db_session.commit()

        query_emb = (await embedding_service.embed(["balanço financeiro"]))[0]
        results = await repository.search_similar(query_emb, top_k=5)

        assert len(results) >= 1

    @pytest.mark.anyio
    async def test_search_respects_top_k(
        self,
        db_session: AsyncSession,
        repository: ChunkRepository,
        embedding_service: SimulatedEmbeddingService,
    ):
        embeddings = await embedding_service.embed([f"Texto {i}" for i in range(10)])
        for i, emb in enumerate(embeddings):
            await repository.insert(
                document_id="doc-multi",
                chunk_index=i,
                text=f"Texto {i}",
                embedding=emb,
            )
        await db_session.commit()

        query_emb = (await embedding_service.embed(["Texto 5"]))[0]
        results = await repository.search_similar(query_emb, top_k=3)

        assert len(results) == 3
