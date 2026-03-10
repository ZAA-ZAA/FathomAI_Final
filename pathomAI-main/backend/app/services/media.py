# converts the video audio to WAV format and extracts metadata using ffmpeg

from __future__ import annotations

from pathlib import Path
from typing import Any

import ffmpeg


def probe_video_metadata(video_path: Path) -> dict[str, Any]:
    try:
        probe = ffmpeg.probe(str(video_path))
    except (ffmpeg.Error, FileNotFoundError):
        return {}

    format_info = probe.get("format", {})
    streams = probe.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})

    metadata: dict[str, Any] = {
        "format_name": format_info.get("format_name"),
        "duration_seconds": _safe_float(format_info.get("duration")),
        "bit_rate": _safe_int(format_info.get("bit_rate")),
    }

    if video_stream:
        metadata["width"] = _safe_int(video_stream.get("width"))
        metadata["height"] = _safe_int(video_stream.get("height"))
        metadata["video_codec"] = video_stream.get("codec_name")
    if audio_stream:
        metadata["audio_codec"] = audio_stream.get("codec_name")
        metadata["sample_rate"] = _safe_int(audio_stream.get("sample_rate"))

    return {key: value for key, value in metadata.items() if value is not None}


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        (
            ffmpeg
            .input(str(video_path))
            .output(str(audio_path), acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        error_output = exc.stderr.decode("utf-8", errors="ignore").strip() if exc.stderr else str(exc)
        raise RuntimeError(f"Audio extraction failed: {error_output}") from exc
    return audio_path


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
