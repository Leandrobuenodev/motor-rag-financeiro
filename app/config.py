from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb"
    embedding_provider: Literal["simulated", "azure"] = "simulated"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-02-01"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
