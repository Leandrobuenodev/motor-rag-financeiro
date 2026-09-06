from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Chunk:
    text: str
    document_id: str
    index: int
    id: str = field(default_factory=lambda: str(uuid4()))


class Chunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(
        self, text: str, document_id: str, start_index: int = 0
    ) -> list[Chunk]:
        if not text or not text.strip():
            return []

        chunks: list[Chunk] = []
        start = 0
        index = start_index

        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            chunks.append(
                Chunk(
                    text=chunk_text.strip(),
                    document_id=document_id,
                    index=index,
                )
            )
            if end >= len(text):
                break
            start += self.chunk_size - self.chunk_overlap
            index += 1

        return chunks
