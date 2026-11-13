from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: str = "local"
    photo_storage_path: Path = ROOT / "storage" / "worker-photos"
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "skillsync_backend"
    db_user: str = "postgres"
    db_password: str = ""
    database_url: str | None = None
    token_ttl_minutes: int = Field(default=480, ge=5, le=10080)

    def database_dsn(self) -> str | URL:
        return self.database_url or URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )
