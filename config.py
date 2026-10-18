"""Configuration settings for CustomerGraph AI."""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    OPENAI_API_KEY: str = Field(
        default="",
        description="API key for OpenAI API",
    )
    FALKORDB_HOST: str = Field(
        default="localhost",
        description="FalkorDB / Redis host address",
    )
    FALKORDB_PORT: int = Field(
        default=6379,
        description="FalkorDB / Redis port number",
    )
    APP_HOST: str = Field(
        default="0.0.0.0",
        description="FastAPI application host address",
    )
    APP_PORT: int = Field(
        default=8000,
        description="FastAPI application port number",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging verbosity level",
    )
    LLM_MODEL: str = Field(
        default="gpt-4o",
        description="Default LLM model identifier",
    )
    GRAPH_NAME: str = Field(
        default="customer_graph",
        description="FalkorDB graph key name",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings.

    Returns:
        Settings: Application configuration settings instance.
    """
    return Settings()
