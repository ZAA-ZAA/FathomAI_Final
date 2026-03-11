# uses whisper api to transcribe audio files, with support for language hints to improve accuracy in code-switched conversations

from __future__ import annotations

from pathlib import Path
from typing import Any

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
                "timestamp_granularities": ["segment", "word"],
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

    transcript_segments = _extract_transcript_segments(response)

    return TranscriptionResult(
        transcript=transcript,
        detected_language=getattr(response, "language", None),
        transcript_segments=transcript_segments,
    )


def _resolve_language(language_hint: str) -> str | None:
    normalized = (language_hint or "auto").strip().lower()
    if normalized in {"tl", "tagalog"}:
        return "tl"
    if normalized in {"en", "english"}:
        return "en"
    return None


def _extract_transcript_segments(response: Any) -> list[dict[str, Any]]:
    raw_words = getattr(response, "words", None)
    if raw_words is None and hasattr(response, "model_dump"):
        raw_words = response.model_dump().get("words")

    word_segments = _build_segments_from_words(raw_words)
    if word_segments:
        return word_segments

    raw_segments = getattr(response, "segments", None)
    if raw_segments is None and hasattr(response, "model_dump"):
        raw_segments = response.model_dump().get("segments")
    if raw_segments is None:
        return []

    normalized_segments: list[dict[str, Any]] = []
    for segment in raw_segments:
        if hasattr(segment, "model_dump"):
            payload = segment.model_dump()
        elif isinstance(segment, dict):
            payload = segment
        else:
            payload = {
                "id": getattr(segment, "id", None),
                "start": getattr(segment, "start", None),
                "end": getattr(segment, "end", None),
                "text": getattr(segment, "text", None),
            }

        text = str(payload.get("text") or "").strip()
        if not text:
            continue

        normalized_segments.append(
            {
                "id": payload.get("id"),
                "start": _safe_float(payload.get("start")),
                "end": _safe_float(payload.get("end")),
                "text": text,
            }
        )

    return normalized_segments


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_segments_from_words(raw_words: Any) -> list[dict[str, Any]]:
    if not raw_words:
        return []

    normalized_words: list[dict[str, Any]] = []
    for index, word in enumerate(raw_words):
        if hasattr(word, "model_dump"):
            payload = word.model_dump()
        elif isinstance(word, dict):
            payload = word
        else:
            payload = {
                "word": getattr(word, "word", None),
                "start": getattr(word, "start", None),
                "end": getattr(word, "end", None),
            }

        text = str(payload.get("word") or "").strip()
        if not text:
            continue

        normalized_words.append(
            {
                "index": index,
                "text": text,
                "start": _safe_float(payload.get("start")),
                "end": _safe_float(payload.get("end")),
            }
        )

    if not normalized_words:
        return []

    segments: list[dict[str, Any]] = []
    current_words: list[dict[str, Any]] = []

    def flush_current() -> None:
        nonlocal current_words
        if not current_words:
            return

        text = _join_words(current_words)
        if not text:
            current_words = []
            return

        segments.append(
            {
                "id": len(segments),
                "start": current_words[0]["start"],
                "end": current_words[-1]["end"],
                "text": text,
            }
        )
        current_words = []

    for word in normalized_words:
        if current_words:
            previous_word = current_words[-1]
            pause = None
            if previous_word["end"] is not None and word["start"] is not None:
                pause = word["start"] - previous_word["end"]
        else:
            pause = None

        current_words.append(word)

        joined_text = _join_words(current_words)
        should_flush = False
        if joined_text.endswith((".", "?", "!", ":", ";")):
            should_flush = True
        elif pause is not None and pause >= 0.9 and len(current_words) >= 4:
            should_flush = True
        elif len(current_words) >= 22:
            should_flush = True
        elif len(joined_text) >= 180:
            should_flush = True

        if should_flush:
            flush_current()

    flush_current()
    return segments


def _join_words(words: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    for word in words:
        text = str(word["text"])
        if not pieces:
            pieces.append(text)
            continue

        if text[:1] in {".", ",", "!", "?", ":", ";", "%", "'"}:
            pieces[-1] = f"{pieces[-1]}{text}"
        else:
            pieces.append(text)

    return " ".join(pieces).strip()
