from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb"
    embedding_provider: Literal["local", "simulated"] = "local"
    local_embedding_model: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    answer_provider: Literal["opencode-go"] = "opencode-go"
    answer_model: str = "deepseek-v4-pro"
    opencode_go_api_key: SecretStr = SecretStr("")
    opencode_go_endpoint: str = (
        "https://opencode.ai/zen/go/v1/chat/completions"
    )
    answer_timeout_seconds: float = 60.0

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
