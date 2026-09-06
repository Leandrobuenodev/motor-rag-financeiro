import pytest

from app.config import settings
from app.infrastructure.embeddings import (
    AzureEmbeddingService,
    SimulatedEmbeddingService,
    create_embedding_service,
)


def test_simulated_provider_is_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "simulated")
    service = create_embedding_service()
    assert isinstance(service, SimulatedEmbeddingService)


def test_azure_provider_requires_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "azure")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "")
    monkeypatch.setattr(settings, "azure_openai_api_key", "")

    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER=azure requires"):
        create_embedding_service()


@pytest.mark.anyio
async def test_configured_azure_provider_is_created_without_remote_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "azure")
    monkeypatch.setattr(
        settings, "azure_openai_endpoint", "https://example.openai.azure.com/"
    )
    monkeypatch.setattr(settings, "azure_openai_api_key", "test-placeholder")
    monkeypatch.setattr(settings, "azure_openai_embedding_deployment", "embedding")

    service = create_embedding_service()
    assert isinstance(service, AzureEmbeddingService)
    await service.close()
