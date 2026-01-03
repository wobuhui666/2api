"""Configuration management for the application."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Proxy Configuration
    proxy: str | None = Field(default=None, description="HTTP proxy URL")

    # Timeout Configuration
    timeout: int = Field(default=120, description="Request timeout in seconds")

    # Retry Configuration
    max_retry: int = Field(default=3, description="Maximum retry attempts")

    # Response Configuration
    text_response: bool = Field(
        default=True, description="Whether to include text in response"
    )

    # System Prompt
    system_prompt: str | None = Field(default=None, description="System prompt")

    # Vertex AI Anonymous API Configuration
    vertex_ai_base_api: str = Field(
        default="https://cloudconsole-pa.clients6.google.com",
        description="Vertex AI base API URL",
    )
    recaptcha_base_api: str = Field(
        default="https://www.google.com", description="Recaptcha base API URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()