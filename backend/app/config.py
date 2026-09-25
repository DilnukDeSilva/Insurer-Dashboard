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

    # Base URL of the public claimant-facing web app (kaduna-web) — used only
    # to build the shareable link returned by POST /claims/claim-links.
    # Defaults to the real production domain rather than localhost: this
    # value wasn't reliably taking effect via the platform's env var UI in
    # production, so the safe default is "correct in prod even if the env
    # var is never set", not "correct locally, wrong everywhere else". Local
    # dev that needs a different value should still set
    # CLAIMANT_WEB_BASE_URL explicitly in backend/.env, same as every other
    # environment-specific setting here.
    claimant_web_base_url: str = "https://kaduna.lk"

    # Notify.lk (Sri Lanka SMS gateway) — used to text the claim link straight
    # to the claimant's phone. Left blank by default; sending is disabled
    # (returns a clear error, not a silent no-op) until these are set.
    notify_lk_user_id: str = ""
    notify_lk_api_key: str = ""
    notify_lk_sender_id: str = "NotifyDEMO"

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
