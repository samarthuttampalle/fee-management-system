"""Application settings loader (Pydantic Settings)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration for the Function App."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    environment: str = "local"
    functions_worker_runtime: str = "python"
    log_level: str = "INFO"

    sql_server_host: str = ""
    sql_database_name: str = "sqldb-feemgmt-dev"
    sql_auth_mode: str = "sql"
    sql_connection_string: str = ""

    aad_tenant_id: str = ""
    aad_audience: str = ""
    local_auth_bypass_token: str = ""
    local_auth_bypass_student_token: str = ""
    local_auth_bypass_student_oid: str = "11111111-1111-1111-1111-111111111111"

    sendgrid_mode: str = "mock"
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""

    applicationinsights_connection_string: str = ""
    reminder_cron_schedule: str = "0 30 1 * * *"

    # SQLAlchemy pool (TDD §17.1)
    sql_pool_size: int = Field(default=5, ge=1)
    sql_max_overflow: int = Field(default=10, ge=0)
    sql_pool_recycle: int = Field(default=280, ge=30)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings loaded from environment variables."""
    return Settings()
