from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import JobStatus, VideoJob
from app.schemas import VideoJobRead, VideoJobSummary, VideoUploadResponse
from app.services.media import probe_video_metadata
from app.services.video_pipeline import process_video_job

router = APIRouter(prefix="/api/videos", tags=["videos"])

ALLOWED_LANGUAGE_HINTS = {"auto", "en", "english", "tl", "tagalog"}


@router.get("", response_model=list[VideoJobSummary])
def list_video_jobs(db: Session = Depends(get_db)) -> list[VideoJob]:
    statement = select(VideoJob).order_by(VideoJob.created_at.desc())
    return list(db.scalars(statement).all())


@router.get("/{job_id}", response_model=VideoJobRead)
def get_video_job(job_id: str, db: Session = Depends(get_db)) -> VideoJob:
    job = db.get(VideoJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    return job


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language_hint: str = Form("auto"),
    db: Session = Depends(get_db),
) -> VideoUploadResponse:
    normalized_hint = (language_hint or "auto").strip().lower()
    if normalized_hint not in ALLOWED_LANGUAGE_HINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language hint")

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only video uploads are supported")

    job = VideoJob(
        original_filename=file.filename,
        stored_filename=file.filename,
        storage_path="",
        content_type=file.content_type,
        language_hint=_normalize_language_hint(normalized_hint),
        status=JobStatus.QUEUED.value,
    )
    db.add(job)
    db.flush()

    job_directory = settings.upload_dir / job.id
    job_directory.mkdir(parents=True, exist_ok=True)
    stored_path = job_directory / _safe_filename(file.filename)
    _save_upload(file, stored_path)

    metadata = probe_video_metadata(stored_path)
    job.storage_path = str(stored_path)
    job.stored_filename = stored_path.name
    job.file_size_bytes = stored_path.stat().st_size
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


def _save_upload(file: UploadFile, destination: Path) -> None:
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    file.file.close()


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def _normalize_language_hint(language_hint: str) -> str:
    if language_hint in {"english"}:
        return "en"
    if language_hint in {"tagalog"}:
        return "tl"
    return language_hint
