# uses whisper api to transcribe audio files, with support for language hints to improve accuracy in code-switched conversations

from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.schemas import TranscriptionResult


class WhisperTranscriptionError(RuntimeError):
    pass


def transcribe_audio_file(audio_path: Path, language_hint: str) -> TranscriptionResult:
    if not settings.openai_api_key:
        raise WhisperTranscriptionError("OPENAI_API_KEY is not set")

    resolved_language = _resolve_language(language_hint)
    client = OpenAI(api_key=settings.openai_api_key)

    try:
        with audio_path.open("rb") as audio_file:
            request_kwargs = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json",
                "prompt": "The speaker may switch between English and Tagalog in the same conversation.",
            }
            if resolved_language is not None:
                request_kwargs["language"] = resolved_language

            response = client.audio.transcriptions.create(
                **request_kwargs,
            )
    except Exception as exc:
        raise WhisperTranscriptionError(f"Whisper transcription failed: {exc}") from exc

    transcript = getattr(response, "text", "") or ""
    if not transcript.strip():
        raise WhisperTranscriptionError("Whisper returned an empty transcript")

    return TranscriptionResult(
        transcript=transcript,
        detected_language=getattr(response, "language", None),
    )


def _resolve_language(language_hint: str) -> str | None:
    normalized = (language_hint or "auto").strip().lower()
    if normalized in {"tl", "tagalog"}:
        return "tl"
    if normalized in {"en", "english"}:
        return "en"
    return None
