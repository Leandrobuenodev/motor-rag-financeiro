from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Document:
    name: str
    content: str
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Document name must not be empty")
        if not self.content or not self.content.strip():
            raise ValueError("Document content must not be empty")
