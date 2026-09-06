import hashlib
import math
from abc import ABC, abstractmethod

from openai import AsyncAzureOpenAI

from app.config import settings


class EmbeddingService(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...

    async def close(self) -> None:
        """Release provider resources when the application stops."""


class SimulatedEmbeddingService(EmbeddingService):
    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(text) for text in texts]

    def _hash_embed(self, text: str) -> list[float]:
        result: list[float] = []
        h = hashlib.sha256(text.encode()).digest()
        for i in range(self.dimension):
            byte_val = h[i % len(h)]
            shift = (i * 3 + 7) % 8
            val = (math.sin(byte_val * (i + 1) * 0.01 + shift) + 1.0) / 2.0
            result.append(val)

        norm = math.sqrt(sum(v * v for v in result))
        if norm > 0:
            result = [v / norm for v in result]
        return result


class AzureEmbeddingService(EmbeddingService):
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        api_version: str | None = None,
        deployment: str | None = None,
    ) -> None:
        self.client = AsyncAzureOpenAI(
            azure_endpoint=endpoint or settings.azure_openai_endpoint,
            api_key=api_key or settings.azure_openai_api_key,
            api_version=api_version or settings.azure_openai_api_version,
        )
        self.deployment = deployment or settings.azure_openai_embedding_deployment

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.deployment,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def close(self) -> None:
        await self.client.close()


def create_embedding_service() -> EmbeddingService:
    """Build the configured provider without making a remote API call."""
    if settings.embedding_provider == "simulated":
        return SimulatedEmbeddingService()

    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
            ("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
            (
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
                settings.azure_openai_embedding_deployment,
            ),
        )
        if not value.strip()
    ]
    if missing:
        missing_names = ", ".join(missing)
        raise ValueError(
            "EMBEDDING_PROVIDER=azure requires the following settings: "
            f"{missing_names}"
        )

    return AzureEmbeddingService()
