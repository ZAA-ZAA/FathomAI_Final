# This module defines the main processing pipeline for video jobs, including audio extraction, transcription, and analysis. It interacts with the database to update job statuses and handles errors gracefully.

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import SessionLocal
from app.models import JobStatus, VideoJob
from app.services.agent_client import request_transcript_analysis
from app.services.media import extract_audio
from app.services.object_storage import download_video_source, is_remote_storage_path, upload_video_source
from app.services.report_delivery import generate_and_store_report, generate_store_and_email_report
from app.services.transcription import transcribe_audio_file
from app.services.video_ingest import build_filename_from_download, download_video_from_url
from app.services.media import probe_video_metadata


def process_video_job(job_id: str, audio_root: Path, local_source_path: str | None = None) -> None:
    audio_path: Path | None = None
    local_video_path: Path | None = Path(local_source_path) if local_source_path else None
    session = SessionLocal()
    try:
        job = session.get(VideoJob, job_id)
        if job is None:
            return

        if job.source_type == "url" and job.source_url and not job.storage_path:
            local_video_path, download_metadata = download_video_from_url(
                job.source_url,
                settings.upload_dir / job.tenant_id / job.id,
            )
            metadata = probe_video_metadata(local_video_path)
            job.stored_filename = local_video_path.name
            job.original_filename = build_filename_from_download(download_metadata, local_video_path)[:255]
            job.content_type = download_metadata.get("content_type")
            job.file_size_bytes = local_video_path.stat().st_size
            job.duration_seconds = metadata.get("duration_seconds")
            existing_metadata = dict(job.video_metadata or {})
            job.video_metadata = {
                **existing_metadata,
                **metadata,
                "source": {
                    "type": "url",
                    "url": job.source_url,
                    "extractor": download_metadata.get("extractor"),
                    "extractor_key": download_metadata.get("extractor_key"),
                    "webpage_url": download_metadata.get("webpage_url"),
                    "uploader": download_metadata.get("uploader"),
                    "thumbnail": download_metadata.get("thumbnail"),
                },
            }
            job.storage_path = upload_video_source(
                local_video_path,
                job.tenant_id,
                job.id,
                job.stored_filename,
                job.content_type,
            )
            session.commit()

        if local_video_path is None:
            local_video_path = _resolve_local_video_path(job)

        _update_status(session, job, JobStatus.EXTRACTING_AUDIO.value)
        audio_path = audio_root / job.id / f"{local_video_path.stem}.wav"
        extract_audio(local_video_path, audio_path)

        _update_status(session, job, JobStatus.TRANSCRIBING.value)
        transcription = transcribe_audio_file(audio_path, job.language_hint)
        job.transcript = transcription.transcript
        job.transcript_segments = transcription.transcript_segments
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
        _handle_job_delivery(session, job)
    except Exception as exc:
        if 'job' in locals() and job is not None:
            job.status = JobStatus.FAILED.value
            job.error_message = str(exc)
            session.commit()
    finally:
        session.close()
        if audio_path and audio_path.exists():
            audio_path.unlink(missing_ok=True)
        if (
            local_video_path
            and local_video_path.exists()
            and 'job' in locals()
            and job is not None
            and is_remote_storage_path(job.storage_path)
        ):
            local_video_path.unlink(missing_ok=True)


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


def _resolve_local_video_path(job: VideoJob) -> Path:
    if not job.storage_path:
        raise FileNotFoundError("Video source file is missing")

    if is_remote_storage_path(job.storage_path):
        destination_path = settings.upload_dir / job.tenant_id / job.id / job.stored_filename
        return download_video_source(job.storage_path, destination_path)

    candidate = Path(job.storage_path)
    if not candidate.exists():
        raise FileNotFoundError("Video source file is missing")
    return candidate


def _handle_job_delivery(session: Session, job: VideoJob) -> None:
    metadata = dict(job.video_metadata or {})
    delivery = dict(metadata.get("delivery") or {})
    reports = dict(metadata.get("reports") or {})
    notify_email = str(delivery.get("notify_email") or "").strip() or None
    export_pdf = bool(delivery.get("export_pdf"))
    requested_path = str(delivery.get("export_pdf_path") or "").strip() or None

    if not notify_email and not export_pdf:
        return

    report_record: dict[str, object] | None = None
    if notify_email:
        try:
            report_record = generate_store_and_email_report(
                notify_email,
                job,
                "summary",
                requested_path,
                source="pipeline",
            )
            delivery["email_status"] = "sent"
            delivery["email_error"] = None
            delivery["email_sent_to"] = notify_email
        except Exception as exc:
            delivery["email_status"] = "failed"
            delivery["email_error"] = str(exc)

    if export_pdf and report_record is None:
        try:
            report_record = generate_and_store_report(
                job,
                "summary",
                requested_path,
                source="pipeline",
            )
        except Exception as exc:
            delivery["pdf_status"] = "failed"
            delivery["pdf_saved_path"] = None
            delivery["pdf_storage_path"] = None
            delivery["pdf_error"] = str(exc)

    if report_record is not None:
        reports["summary"] = report_record
        delivery["pdf_status"] = "saved"
        delivery["pdf_saved_path"] = report_record.get("saved_path")
        delivery["pdf_storage_path"] = report_record.get("storage_path")
        delivery["pdf_error"] = report_record.get("error")
        if report_record.get("email_status"):
            delivery["email_status"] = report_record.get("email_status")
            delivery["email_error"] = report_record.get("email_error")
            delivery["email_sent_to"] = report_record.get("emailed_to")

    metadata["reports"] = reports
    metadata["delivery"] = delivery
    job.video_metadata = metadata
    session.commit()
