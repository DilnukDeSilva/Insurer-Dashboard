from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    port: int = 8080
    host: str = "0.0.0.0"
    environment: str = "development"
    data_dir: Path = Path("./data")

    openmvg_bin_dir: Optional[Path] = None
    openmvs_bin_dir: Optional[Path] = None
    zero_dce_repo_dir: Optional[Path] = None
    zero_dce_weights: Optional[Path] = None

    r2_endpoint_url: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "insurer_dashboard"
    jwt_secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    supabase_url: str = ""
    supabase_key: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"


settings = Settings()
