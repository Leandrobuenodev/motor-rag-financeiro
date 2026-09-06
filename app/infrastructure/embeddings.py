import asyncio
import hashlib
import math
import warnings
from abc import ABC, abstractmethod
from typing import Any

from app.config import settings

EMBEDDING_DIMENSION = 384


class EmbeddingService(ABC):
    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        ...

    async def close(self) -> None:
        """Release provider resources when the application stops."""


class SimulatedEmbeddingService(EmbeddingService):
    """Deterministic vectors for tests; they have no semantic meaning."""

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._hash_embed(text)

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


class LocalEmbeddingService(EmbeddingService):
    """Multilingual ONNX embeddings executed in a worker thread."""

    def __init__(
        self,
        model_name: str | None = None,
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name or settings.local_embedding_model
        if model is None:
            from fastembed import TextEmbedding

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"The model .* now uses mean pooling instead of CLS.*",
                )
                model = TextEmbedding(model_name=self.model_name)
        self.model = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        values = await asyncio.to_thread(
            lambda: list(self.model.passage_embed(texts))
        )
        return self._normalize(values)

    async def embed_query(self, text: str) -> list[float]:
        values = await asyncio.to_thread(
            lambda: list(self.model.query_embed(text))
        )
        embeddings = self._normalize(values)
        return embeddings[0]

    @staticmethod
    def _normalize(values: list[Any]) -> list[list[float]]:
        result = [
            [float(value) for value in vector.tolist()] for vector in values
        ]
        if any(len(vector) != EMBEDDING_DIMENSION for vector in result):
            raise ValueError(
                f"Embedding model must produce {EMBEDDING_DIMENSION} dimensions"
            )
        normalized: list[list[float]] = []
        for vector in result:
            norm = math.sqrt(sum(value * value for value in vector))
            if norm == 0:
                raise ValueError("Embedding model produced a zero vector")
            normalized.append([value / norm for value in vector])
        return normalized


def create_embedding_service() -> EmbeddingService:
    """Build the configured local or test-only embedding provider."""
    if settings.embedding_provider == "simulated":
        return SimulatedEmbeddingService()
    return LocalEmbeddingService()
