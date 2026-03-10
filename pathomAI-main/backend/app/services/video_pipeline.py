# This module defines the main processing pipeline for video jobs, including audio extraction, transcription, and analysis. It interacts with the database to update job statuses and handles errors gracefully.

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import JobStatus, VideoJob
from app.services.agent_client import request_transcript_analysis
from app.services.media import extract_audio
from app.services.transcription import transcribe_audio_file


def process_video_job(job_id: str, audio_root: Path) -> None:
    audio_path: Path | None = None
    session = SessionLocal()
    try:
        job = session.get(VideoJob, job_id)
        if job is None:
            return

        _update_status(session, job, JobStatus.EXTRACTING_AUDIO.value)
        video_path = Path(job.storage_path)
        audio_path = audio_root / job.id / f"{video_path.stem}.wav"
        extract_audio(video_path, audio_path)

        _update_status(session, job, JobStatus.TRANSCRIBING.value)
        transcription = transcribe_audio_file(audio_path, job.language_hint)
        job.transcript = transcription.transcript
        job.detected_language = transcription.detected_language or _fallback_language(job.language_hint)
        session.commit()

        _update_status(session, job, JobStatus.ANALYZING.value)
        analysis = request_transcript_analysis(
            transcript=job.transcript or "",
            video_title=job.original_filename,
            source_language=job.detected_language,
        )
        job.summary = analysis.summary
        job.action_items = analysis.action_items
        job.sentiment = analysis.sentiment
        job.status = JobStatus.COMPLETED.value
        job.error_message = None
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
    except Exception as exc:
        if 'job' in locals() and job is not None:
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            session.commit()
    finally:
        session.close()
        if audio_path and audio_path.exists():
            audio_path.unlink(missing_ok=True)


def _update_status(session: Session, job: VideoJob, status: str) -> None:
    job.status = status
    job.error_message = None
    session.commit()


def _fallback_language(language_hint: str) -> str | None:
    normalized = (language_hint or "auto").lower()
    if normalized in {"en", "english"}:
        return "en"
    if normalized in {"tl", "tagalog"}:
        return "tl"
    return None
