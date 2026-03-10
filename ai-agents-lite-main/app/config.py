from __future__ import annotations

import os
from dataclasses import dataclass
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
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    default_model: str = os.getenv("TRANSCRIPT_ANALYSIS_MODEL", "gpt-4o")


settings = Settings()
