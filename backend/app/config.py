from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    port: int = 8000
    host: str = "0.0.0.0"
    environment: str = "development"
    data_dir: Path = Path("./data")

    openmvg_bin_dir: Optional[Path] = None
    openmvs_bin_dir: Optional[Path] = None
    zero_dce_repo_dir: Optional[Path] = None
    zero_dce_weights: Optional[Path] = None

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"


settings = Settings()
