"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Set
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the URL Shortener application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core App
    app_name: str = "Production URL Shortener API"
    app_env: str = "development"
    debug: bool = False
    base_url: str = "http://localhost:8000"

    # Database
    database_url: str = "sqlite:///./url_shortener.db"

    # Short Code Generation Policy
    short_code_length: int = Field(default=6, ge=4, le=30)
    short_code_max_retries: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias=AliasChoices(
            "short_code_max_retries",
            "short_code_max_collision_retries",
        ),
        description="Maximum attempts to resolve random short code collisions",
    )

    # Custom Alias Constraints
    min_alias_length: int = Field(default=3, ge=1, le=10)
    max_alias_length: int = Field(default=30, ge=10, le=100)
    alias_regex: str = r"^[a-zA-Z0-9_-]+$"

    # Reserved routes/keywords that cannot be used as custom aliases
    reserved_aliases: Set[str] = {
        "links",
        "docs",
        "redoc",
        "openapi.json",
        "health",
        "api",
        "static",
        "favicon.ico",
        "admin",
        "robots.txt",
    }


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
