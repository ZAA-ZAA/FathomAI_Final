from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import settings
from app.schemas import AgentAnalysisResult


class AgentServiceError(RuntimeError):
    pass


def request_transcript_analysis(
    transcript: str,
    video_title: str,
    source_language: str | None,
) -> AgentAnalysisResult:
    if not transcript.strip():
        raise AgentServiceError("Transcript is empty; analysis was skipped")

    url = f"{settings.agent_service_url.rstrip('/')}/internal/transcript-analysis"
    payload: dict[str, Any] = {
        "transcript": transcript,
        "video_title": video_title,
        "source_language": source_language,
    }

    last_error: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            response = httpx.post(url, json=payload, timeout=90.0)
            response.raise_for_status()
            return AgentAnalysisResult.model_validate(response.json())
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(2)

    raise AgentServiceError(f"Agent service request failed: {last_error}") from last_error
