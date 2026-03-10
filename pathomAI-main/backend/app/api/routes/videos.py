from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import JobStatus, VideoJob
from app.schemas import VideoJobRead, VideoJobSummary, VideoUploadResponse
from app.services.auth import AuthContext, require_auth_context
from app.services.media import probe_video_metadata
from app.services.video_pipeline import process_video_job

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_LANGUAGE_HINTS = {"auto", "en", "english", "tl", "tagalog"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


@router.get("", response_model=list[VideoJobSummary])
def list_video_jobs(
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> list[VideoJob]:
    statement = (
        select(VideoJob)
        .where(VideoJob.tenant_id == auth_context.tenant_id)
        .order_by(VideoJob.created_at.desc())
    )
    return list(db.scalars(statement).all())


@router.get("/{job_id}", response_model=VideoJobRead)
def get_video_job(
    job_id: str,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoJob:
    statement = select(VideoJob).where(
        VideoJob.id == job_id,
        VideoJob.tenant_id == auth_context.tenant_id,
    )
    job = db.scalar(statement)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    return job


@router.get("/{job_id}/source", response_model=None)
def stream_video_source(
    job_id: str,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
):
    statement = select(VideoJob).where(
        VideoJob.id == job_id,
        VideoJob.tenant_id == auth_context.tenant_id,
    )
    job = db.scalar(statement)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")

    file_path = Path(job.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video source file not found")

    return FileResponse(file_path, media_type=job.content_type or "video/mp4", filename=job.original_filename)


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language_hint: str = Form("auto"),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoUploadResponse:
    normalized_hint = (language_hint or "auto").strip().lower()
    if normalized_hint not in ALLOWED_LANGUAGE_HINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language hint")

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only video uploads are supported")

    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported video file type")

    job = VideoJob(
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id,
        original_filename=file.filename,
        stored_filename=file.filename,
        storage_path="",
        content_type=file.content_type,
        language_hint=_normalize_language_hint(normalized_hint),
        status=JobStatus.QUEUED.value,
    )
    db.add(job)
    db.flush()

    job_directory = settings.upload_dir / auth_context.tenant_id / job.id
    job_directory.mkdir(parents=True, exist_ok=True)
    stored_path = job_directory / _safe_filename(file.filename)

    try:
        file_size = _save_upload(file, stored_path)
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

    metadata = probe_video_metadata(stored_path)
    job.storage_path = str(stored_path)
    job.stored_filename = stored_path.name
    job.file_size_bytes = file_size
    job.duration_seconds = metadata.get("duration_seconds")
    job.video_metadata = metadata
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_video_job, job.id, settings.audio_dir)

    return VideoUploadResponse(
        id=job.id,
        status=job.status,
        message="Video upload accepted for processing",
    )


@router.post("/{job_id}/retry", response_model=VideoUploadResponse)
def retry_video_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoUploadResponse:
    statement = select(VideoJob).where(
        VideoJob.id == job_id,
        VideoJob.tenant_id == auth_context.tenant_id,
    )
    job = db.scalar(statement)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed jobs can be retried")

    file_path = Path(job.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original video file is missing")

    job.status = JobStatus.QUEUED.value
    job.error_message = None
    job.transcript = None
    job.summary = None
    job.sentiment = None
    job.action_items = []
    job.detected_language = None
    job.completed_at = None
    db.commit()

    background_tasks.add_task(process_video_job, job.id, settings.audio_dir)
    return VideoUploadResponse(id=job.id, status=job.status, message="Retry started")


def _save_upload(file: UploadFile, destination: Path) -> int:
    total_bytes = 0
    with destination.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > settings.max_upload_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Video exceeds the {settings.max_upload_size_bytes // (1024 * 1024)} MB upload limit",
                )
            buffer.write(chunk)
    return total_bytes


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def _normalize_language_hint(language_hint: str) -> str:
    if language_hint in {"english"}:
        return "en"
    if language_hint in {"tagalog"}:
        return "tl"
    return language_hint
