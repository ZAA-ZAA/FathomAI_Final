from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.schemas.transcript_analysis import (
    TranscriptAnalysisRequest,
    TranscriptAnalysisResponse,
)


class TranscriptAnalysisService:
    def __init__(self, model: str | None = None) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.default_model

    def analyze(self, request: TranscriptAnalysisRequest) -> TranscriptAnalysisResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=self._build_messages(request),
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        return TranscriptAnalysisResponse(
            summary=str(payload.get("summary", "")).strip(),
            action_items=self._normalize_action_items(payload.get("action_items", [])),
            sentiment=str(payload.get("sentiment", "neutral")).strip().lower() or "neutral",
        )

    def _build_messages(self, request: TranscriptAnalysisRequest) -> list[dict[str, str]]:
        context_lines = [
            "Analyze the provided transcript from a video intelligence platform.",
            "The transcript may include English, Tagalog, or code-switching between them.",
            "Return JSON with keys: summary, action_items, sentiment.",
            "Keep the summary concise but decision-useful.",
            "Action items must be an array of concrete follow-up tasks.",
            "Sentiment must be a single label such as positive, neutral, mixed, or negative.",
        ]
        if request.video_title:
            context_lines.append(f"Video title: {request.video_title}")
        if request.source_language:
            context_lines.append(f"Source language hint: {request.source_language}")

        return [
            {"role": "system", "content": "\n".join(context_lines)},
            {"role": "user", "content": request.transcript},
        ]

    def _normalize_action_items(self, action_items: object) -> list[str]:
        if not isinstance(action_items, list):
            return []
        normalized: list[str] = []
        for item in action_items:
            text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized
