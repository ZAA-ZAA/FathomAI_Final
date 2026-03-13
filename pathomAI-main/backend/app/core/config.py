from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _load_root_env() -> None:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return


_load_root_env()


@dataclass(slots=True)
class Settings:
    app_name: str = "PathomAI Backend"
    api_prefix: str = "/api"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://pathomai:pathomai@localhost:5432/pathomai",
    )
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    agent_service_url: str = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")
    auth_session_ttl_hours: int = int(os.getenv("AUTH_SESSION_TTL_HOURS", "168"))
    max_upload_size_bytes: int = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(500 * 1024 * 1024)))
    video_storage_provider: str = os.getenv("VIDEO_STORAGE_PROVIDER", "local").strip().lower()
    r2_bucket_name: str = os.getenv("R2_BUCKET_NAME", "").strip()
    r2_endpoint_url: str = os.getenv("R2_ENDPOINT_URL", "").strip().rstrip("/")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    r2_key_prefix: str = os.getenv("R2_KEY_PREFIX", "videos").strip().strip("/")
    cors_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    )
    backend_root: Path = field(init=False)
    storage_root: Path = field(init=False)
    upload_dir: Path = field(init=False)
    audio_dir: Path = field(init=False)
    frontend_dist_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        self.backend_root = backend_root
        self.storage_root = Path(os.getenv("STORAGE_DIR", backend_root / "storage"))
        self.upload_dir = self.storage_root / "uploads"
        self.audio_dir = self.storage_root / "audio"
        default_frontend_dist = backend_root.parent / "dist"
        self.frontend_dist_dir = Path(os.getenv("FRONTEND_DIST_DIR", default_frontend_dist))

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        if self.video_storage_provider not in {"local", "r2"}:
            raise ValueError("VIDEO_STORAGE_PROVIDER must be either 'local' or 'r2'")

        if self.video_storage_provider == "r2":
            missing = [
                name
                for name, value in (
                    ("R2_BUCKET_NAME", self.r2_bucket_name),
                    ("R2_ENDPOINT_URL", self.r2_endpoint_url),
                    ("R2_ACCESS_KEY_ID", self.r2_access_key_id),
                    ("R2_SECRET_ACCESS_KEY", self.r2_secret_access_key),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "R2 storage is enabled but the following environment variables are missing: "
                    + ", ".join(missing)
                )


settings = Settings()
