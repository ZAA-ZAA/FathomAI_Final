from __future__ import annotations

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

    try:
        response = httpx.post(url, json=payload, timeout=90.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise AgentServiceError(f"Agent service request failed: {exc}") from exc

    return AgentAnalysisResult.model_validate(response.json())
