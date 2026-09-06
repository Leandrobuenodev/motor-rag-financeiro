import pytest

import app.infrastructure.embeddings as embeddings_module
from app.config import settings
from app.infrastructure.embeddings import (
    EMBEDDING_DIMENSION,
    LocalEmbeddingService,
    SimulatedEmbeddingService,
    create_embedding_service,
)


class FakeVector:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def tolist(self) -> list[float]:
        return self.values


class FakeFastEmbedModel:
    def __init__(self) -> None:
        self.passage_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def passage_embed(self, texts: list[str]) -> list[FakeVector]:
        self.passage_calls.append(texts)
        return [self._vector() for _ in texts]

    def query_embed(self, text: str) -> list[FakeVector]:
        self.query_calls.append(text)
        return [self._vector()]

    @staticmethod
    def _vector() -> FakeVector:
        return FakeVector(
            [float(index == 0) for index in range(EMBEDDING_DIMENSION)]
        )


def test_simulated_provider_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "simulated")
    service = create_embedding_service()
    assert isinstance(service, SimulatedEmbeddingService)


def test_local_provider_is_selected_without_loading_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = SimulatedEmbeddingService()
    monkeypatch.setattr(settings, "embedding_provider", "local")
    monkeypatch.setattr(
        embeddings_module, "LocalEmbeddingService", lambda: sentinel
    )

    assert create_embedding_service() is sentinel


@pytest.mark.anyio
async def test_local_provider_uses_query_and_passage_paths() -> None:
    model = FakeFastEmbedModel()
    service = LocalEmbeddingService(model=model)

    documents = await service.embed_documents(["Relatório financeiro"])
    query = await service.embed_query("financial report")

    assert len(documents[0]) == EMBEDDING_DIMENSION
    assert len(query) == EMBEDDING_DIMENSION
    assert model.passage_calls == [["Relatório financeiro"]]
    assert model.query_calls == ["financial report"]
    assert documents[0][0] == 1.0


@pytest.mark.anyio
async def test_local_provider_rejects_wrong_vector_dimension() -> None:
    class WrongDimensionModel:
        def query_embed(self, text: str) -> list[FakeVector]:
            return [FakeVector([1.0])]

    service = LocalEmbeddingService(model=WrongDimensionModel())

    with pytest.raises(ValueError, match="must produce 384 dimensions"):
        await service.embed_query("query")


@pytest.mark.anyio
async def test_simulated_embeddings_are_deterministic_but_not_semantic() -> None:
    service = SimulatedEmbeddingService()

    document = (await service.embed_documents(["same text"]))[0]
    query = await service.embed_query("same text")

    assert document == query
    assert len(query) == EMBEDDING_DIMENSION
