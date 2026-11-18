"""
Application configuration.

All values are read from environment variables or a .env file.
Secrets (API keys, credentials) must never appear in source code.
"""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Aegis Global Intelligence"
    app_env: str = "development"
    debug: bool = True

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # ── Persistence ───────────────────────────────────────────────────────────
    # Options: sqlite | firestore_emulator
    persistence_backend: str = "sqlite"
    sqlite_db_path: str = "./data/aegis.db"

    # Firestore emulator (set when PERSISTENCE_BACKEND=firestore_emulator)
    firestore_emulator_host: str = ""  # e.g. "localhost:8086"

    # ── Message bus ───────────────────────────────────────────────────────────
    # Options: in_memory | pubsub_emulator | pubsub
    # message_bus_type is the canonical selector; message_bus_backend is kept
    # for backward compatibility and defaults to the same value.
    message_bus_type: str = "in_memory"
    message_bus_backend: str = "in_memory"
    pubsub_project_id: str = "aegis-local"
    pubsub_emulator_host: Optional[str] = "localhost:8085"

    # Topic and subscription names
    events_topic: str = "aegis-events"
    events_subscription: str = "aegis-events-worker"
    dead_letter_topic: str = "aegis-events-dlq"

    # ── Model provider ────────────────────────────────────────────────────────
    # Options: deterministic | gemini | vertex
    model_provider: str = "deterministic"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # ── Retrieval ─────────────────────────────────────────────────────────────
    # Options: lexical | bge_m3
    retrieval_backend: str = "lexical"
    knowledge_base_path: str = "./data/synthetic"
    retrieval_top_k: int = 5

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    # Options: json | text
    log_format: str = "json"

    # ── Worker ────────────────────────────────────────────────────────────────
    worker_concurrency: int = 3
    max_retry_attempts: int = 3
    retry_backoff_seconds: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the singleton Settings instance (lazy-initialised)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the singleton — used in tests to pick up .env overrides."""
    global _settings
    _settings = None
