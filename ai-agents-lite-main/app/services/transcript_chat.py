from __future__ import annotations

import json

from openai import OpenAI

from app.config import settings
from app.schemas.transcript_chat import (
    TranscriptChatRequest,
    TranscriptChatResponse,
    TranscriptSuggestionRequest,
    TranscriptSuggestionResponse,
)


class TranscriptChatService:
    def __init__(self, model: str | None = None) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.default_model

    def answer_question(self, request: TranscriptChatRequest) -> TranscriptChatResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=self._build_chat_messages(request),
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
        except Exception as exc:
            raise RuntimeError(f"Transcript chat failed: {exc}") from exc

        answer = str(payload.get("answer", "")).strip()
        if not answer:
            raise RuntimeError("Transcript chat returned an empty answer")

        return TranscriptChatResponse(
            answer=answer,
            suggested_questions=self._normalize_questions(payload.get("suggested_questions", [])),
        )

    def suggest_questions(self, request: TranscriptSuggestionRequest) -> TranscriptSuggestionResponse:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=self._build_suggestion_messages(request),
            )
            content = response.choices[0].message.content or "{}"
            payload = json.loads(content)
        except Exception as exc:
            raise RuntimeError(f"Transcript suggestions failed: {exc}") from exc

        return TranscriptSuggestionResponse(
            suggested_questions=self._normalize_questions(payload.get("suggested_questions", [])),
        )

    def _build_chat_messages(self, request: TranscriptChatRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You answer questions about one uploaded video using only the provided transcript context. "
                    "The transcript may contain English, Tagalog, or code-switching. "
                    "If the answer is not grounded in the transcript, say that the transcript does not confirm it. "
                    "Use timestamps when the transcript segments support them. "
                    "Return strict JSON with keys: answer, suggested_questions. "
                    "suggested_questions must be an array of 3 short, useful follow-up questions that do not repeat already asked questions."
                ),
            },
            {
                "role": "user",
                "content": self._build_context_block(
                    transcript=request.transcript,
                    transcript_segments=request.transcript_segments,
                    video_title=request.video_title,
                    source_language=request.source_language,
                    summary=request.summary,
                    sentiment=request.sentiment,
                    action_items=request.action_items,
                    asked_questions=request.asked_questions,
                ),
            },
        ]

        for message in request.chat_history[-8:]:
            messages.append({"role": message.role, "content": message.content})

        messages.append({"role": "user", "content": request.question})
        return messages

    def _build_suggestion_messages(self, request: TranscriptSuggestionRequest) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You generate suggested questions about one uploaded video. "
                    "Use only the provided transcript context. "
                    "The transcript may contain English, Tagalog, or code-switching. "
                    "Return strict JSON with key suggested_questions. "
                    "suggested_questions must be an array of exactly 3 concise, relevant questions. "
                    "Do not repeat or lightly paraphrase already asked questions."
                ),
            },
            {
                "role": "user",
                "content": self._build_context_block(
                    transcript=request.transcript,
                    transcript_segments=request.transcript_segments,
                    video_title=request.video_title,
                    source_language=request.source_language,
                    summary=request.summary,
                    sentiment=request.sentiment,
                    action_items=request.action_items,
                    asked_questions=request.asked_questions,
                ),
            },
        ]

    def _build_context_block(
        self,
        transcript: str,
        transcript_segments: list,
        video_title: str | None,
        source_language: str | None,
        summary: str | None,
        sentiment: str | None,
        action_items: list[str],
        asked_questions: list[str],
    ) -> str:
        lines = [
            f"Video title: {video_title or 'Unknown'}",
            f"Source language hint: {source_language or 'unknown'}",
            f"Summary: {summary or 'Not available'}",
            f"Sentiment: {sentiment or 'Not available'}",
            "Action items:",
        ]
        if action_items:
            lines.extend(f"- {item}" for item in action_items[:10])
        else:
            lines.append("- None extracted")

        lines.append("Previously asked questions:")
        if asked_questions:
            lines.extend(f"- {question}" for question in asked_questions[-10:])
        else:
            lines.append("- None")

        lines.append("Timestamped transcript segments:")
        if transcript_segments:
            for segment in transcript_segments[:120]:
                start = self._format_timestamp(getattr(segment, "start", None))
                end = self._format_timestamp(getattr(segment, "end", None))
                text = getattr(segment, "text", "").strip()
                if text:
                    lines.append(f"[{start} - {end}] {text}")
        else:
            lines.append("- No timestamp segments available")

        lines.append("Full transcript:")
        lines.append(transcript.strip())
        return "\n".join(lines)

    def _normalize_questions(self, questions: object) -> list[str]:
        if not isinstance(questions, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in questions:
            text = str(item).strip()
            key = text.lower()
            if text and key not in seen:
                normalized.append(text)
                seen.add(key)
            if len(normalized) == 3:
                break
        return normalized

    def _format_timestamp(self, seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        total_seconds = max(0, int(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        remaining_seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
        return f"{minutes:02d}:{remaining_seconds:02d}"
