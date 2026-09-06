import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.embeddings import SimulatedEmbeddingService
from app.infrastructure.repositories import ChunkRepository


class TestChunkRepository:
    @pytest.mark.anyio
    async def test_insert_and_search_returns_nearest_vector(
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
        embeddings = await embedding_service.embed_documents(texts)

        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            await repository.insert(
                document_id="test-doc-1",
                source_filename="report.pdf",
                page_number=1,
                chunk_index=i,
                text=text,
                embedding=emb,
            )
        await db_session.commit()

        query_embedding = await embedding_service.embed_query(texts[0])
        results = await repository.search_similar(query_embedding, top_k=1)

        assert len(results) == 1
        assert results[0].chunk.document_id == "test-doc-1"
        assert results[0].chunk.text == texts[0]
        assert results[0].l2_distance == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.anyio
    async def test_insert_multiple_documents(
        self,
        db_session: AsyncSession,
        repository: ChunkRepository,
        embedding_service: SimulatedEmbeddingService,
    ):
        e1 = (await embedding_service.embed_documents(
            ["Balanço ativo circulante"]
        ))[0]
        e2 = (await embedding_service.embed_documents(
            ["Demonstrativo de resultado"]
        ))[0]

        await repository.insert(
            document_id="doc-a",
            source_filename="balance-sheet.pdf",
            page_number=2,
            chunk_index=0,
            text="Balanço ativo circulante",
            embedding=e1,
        )
        await repository.insert(
            document_id="doc-b",
            source_filename="income-statement.pdf",
            page_number=3,
            chunk_index=0,
            text="Demonstrativo de resultado",
            embedding=e2,
        )
        await db_session.commit()

        query_emb = await embedding_service.embed_query(
            "Balanço ativo circulante"
        )
        results = await repository.search_similar(query_emb, top_k=5)

        assert results[0].chunk.document_id == "doc-a"
        assert results[0].chunk.source_filename == "balance-sheet.pdf"
        assert results[0].chunk.page_number == 2
        assert results[0].l2_distance == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.anyio
    async def test_search_respects_top_k(
        self,
        db_session: AsyncSession,
        repository: ChunkRepository,
        embedding_service: SimulatedEmbeddingService,
    ):
        embeddings = await embedding_service.embed_documents(
            [f"Texto {i}" for i in range(10)]
        )
        for i, emb in enumerate(embeddings):
            await repository.insert(
                document_id="doc-multi",
                source_filename="report.pdf",
                page_number=1,
                chunk_index=i,
                text=f"Texto {i}",
                embedding=emb,
            )
        await db_session.commit()

        query_emb = await embedding_service.embed_query("Texto 5")
        results = await repository.search_similar(query_emb, top_k=3)

        assert len(results) == 3
        assert results[0].chunk.chunk_index == 5
        assert results[0].l2_distance == pytest.approx(0.0, abs=1e-6)
