"""Application configuration via environment variables (12-Factor)."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://scadmin:changeme@localhost:5432/songchau"
    db_pool_min: int = 1
    db_pool_max: int = 5

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire: int = 900       # 15 min
    refresh_token_expire: int = 604800   # 7 days

    # App
    app_env: str = "production"
    debug: bool = False
    app_title: str = "Song Chau ERP"
    app_version: str = "1.0.0"

    # Rate limiting
    rate_limit_per_second: int = 30
    login_rate_limit_per_min: int = 5

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
