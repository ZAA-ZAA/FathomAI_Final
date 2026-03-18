from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import settings
from app.schemas import (
    AgentAnalysisResult,
    AgentCustomSummaryResult,
    VideoChatResponse,
    VideoChatSuggestionResponse,
)


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


def request_transcript_chat(
    transcript: str,
    transcript_segments: list[dict],
    question: str,
    chat_history: list[dict[str, str]],
    asked_questions: list[str],
    video_title: str,
    source_language: str | None,
    summary: str | None,
    sentiment: str | None,
    action_items: list[str],
) -> VideoChatResponse:
    normalized_transcript = _normalize_transcript_context(transcript, transcript_segments)
    if not normalized_transcript:
        raise AgentServiceError("Transcript is empty; chat is unavailable")

    url = f"{settings.agent_service_url.rstrip('/')}/internal/transcript-chat"
    payload: dict[str, Any] = {
        "transcript": normalized_transcript,
        "transcript_segments": transcript_segments,
        "question": question,
        "chat_history": chat_history,
        "asked_questions": asked_questions,
        "video_title": video_title,
        "source_language": source_language,
        "summary": summary,
        "sentiment": sentiment,
        "action_items": action_items,
    }

    return _post_with_retry(url, payload, VideoChatResponse)


def request_transcript_chat_suggestions(
    transcript: str,
    transcript_segments: list[dict],
    asked_questions: list[str],
    video_title: str,
    source_language: str | None,
    summary: str | None,
    sentiment: str | None,
    action_items: list[str],
) -> VideoChatSuggestionResponse:
    normalized_transcript = _normalize_transcript_context(transcript, transcript_segments)
    if not normalized_transcript:
        raise AgentServiceError("Transcript is empty; chat suggestions are unavailable")

    url = f"{settings.agent_service_url.rstrip('/')}/internal/transcript-chat/suggestions"
    payload: dict[str, Any] = {
        "transcript": normalized_transcript,
        "transcript_segments": transcript_segments,
        "asked_questions": asked_questions,
        "video_title": video_title,
        "source_language": source_language,
        "summary": summary,
        "sentiment": sentiment,
        "action_items": action_items,
    }

    return _post_with_retry(url, payload, VideoChatSuggestionResponse)


def request_custom_summary(
    transcript: str,
    instruction: str,
    video_title: str,
    source_language: str | None,
) -> AgentCustomSummaryResult:
    if not transcript.strip():
        raise AgentServiceError("Transcript is empty; custom summary is unavailable")

    url = f"{settings.agent_service_url.rstrip('/')}/internal/custom-summary"
    payload: dict[str, Any] = {
        "transcript": transcript,
        "instruction": instruction,
        "video_title": video_title,
        "source_language": source_language,
    }
    return _post_with_retry(url, payload, AgentCustomSummaryResult)


def _post_with_retry(url: str, payload: dict[str, Any], response_model):
    last_error: httpx.HTTPError | None = None
    for attempt in range(3):
        try:
            response = httpx.post(url, json=payload, timeout=90.0)
            response.raise_for_status()
            return response_model.model_validate(response.json())
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt == 2:
                break
            time.sleep(2)

    raise AgentServiceError(f"Agent service request failed: {last_error}") from last_error


def _normalize_transcript_context(transcript: str, transcript_segments: list[dict]) -> str:
    normalized = transcript.strip()
    if normalized:
        return normalized

    segment_lines = [
        str(segment.get("text", "")).strip()
        for segment in transcript_segments
        if isinstance(segment, dict)
    ]
    return "\n".join(line for line in segment_lines if line)
