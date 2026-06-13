"""Runtime settings, loaded once from env (PETWALK_-prefixed) / .env.

Defaults are dev-safe so the app boots from a clean clone with zero config:
SQLite on disk, a throwaway JWT secret, an all-zero AES key. Every one of these
MUST be overridden in production — see .env.example.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PETWALK_", env_file=".env", extra="ignore")

    # --- Storage --------------------------------------------------------
    # SQLite for a zero-infra local run. The grid approximation (see
    # core/security.grid_cell) keeps proximity search to integer-equality on a
    # cell id, so PostGIS is a *production* swap, not a prerequisite — point
    # DATABASE_URL at Postgres and the same code runs.
    database_url: str = "sqlite:///./petwalk.db"

    # --- Auth -----------------------------------------------------------
    jwt_secret: str = "dev-secret-change-me-in-production-0123456789abcdef"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 14

    # --- Crypto ---------------------------------------------------------
    # 32-byte key (64 hex chars) for AES-256-GCM column encryption (phone).
    aes_key_hex: str = "0" * 64

    # --- Domain ---------------------------------------------------------
    # Cell size for location privacy. ~0.003deg ~= 300m near Seoul. Exact GPS
    # never leaves the server; clients only ever see the cell centre.
    grid_size_deg: float = 0.003

    # --- Ops ------------------------------------------------------------
    rate_limit_per_min: int = 120
    # Per-step pause in the async matcher so the UI can show real progress.
    # Set to 0 in tests for determinism/speed.
    match_step_delay_s: float = 0.35
    # Seed demo users + public meeting places on startup (off in tests).
    seed_on_startup: bool = True

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
