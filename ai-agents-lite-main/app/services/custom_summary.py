from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.schemas.custom_summary import CustomSummaryRequest, CustomSummaryResponse


class CustomSummaryService:
    def __init__(self, model: str | None = None) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.default_model

    def generate(self, request: CustomSummaryRequest) -> CustomSummaryResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=self._build_messages(request),
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
        except Exception as exc:
            raise RuntimeError(f"Custom summary generation failed: {exc}") from exc

        summary = str(payload.get("summary", "")).strip()
        if not summary:
            raise RuntimeError("Custom summary generation returned an empty summary")
        return CustomSummaryResponse(summary=summary)

    def _build_messages(self, request: CustomSummaryRequest) -> list[dict[str, str]]:
        context_lines = [
            "You generate a focused summary for one video transcript.",
            "Follow the user's instruction exactly, but stay grounded in the transcript.",
            "The transcript may include English, Tagalog, or code-switching.",
            "If the requested topic is not covered by the transcript, say so clearly.",
            "Return JSON with one key: summary.",
        ]
        if request.video_title:
            context_lines.append(f"Video title: {request.video_title}")
        if request.source_language:
            context_lines.append(f"Source language hint: {request.source_language}")

        return [
            {"role": "system", "content": "\n".join(context_lines)},
            {
                "role": "user",
                "content": f"Instruction:\n{request.instruction.strip()}\n\nTranscript:\n{request.transcript.strip()}",
            },
        ]
