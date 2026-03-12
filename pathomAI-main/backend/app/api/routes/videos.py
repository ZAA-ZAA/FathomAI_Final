from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import JobStatus, VideoChatMessageRecord, VideoJob
from app.schemas import (
    VideoChatMessageRead,
    VideoChatRequest,
    VideoChatResponse,
    VideoChatSuggestionRequest,
    VideoChatSuggestionResponse,
    CustomSummaryRequest,
    CustomSummaryResponse,
    VideoJobRead,
    VideoJobSummary,
    VideoUploadResponse,
    VideoUrlUploadRequest,
)
from app.services.agent_client import (
    AgentServiceError,
    request_custom_summary,
    request_transcript_chat,
    request_transcript_chat_suggestions,
)
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
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    return job


@router.get("/{job_id}/source", response_model=None)
def stream_video_source(
    job_id: str,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
):
    job = _get_tenant_job(db, auth_context, job_id)
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

    job = _create_job_record(
        db=db,
        auth_context=auth_context,
        original_filename=file.filename,
        language_hint=normalized_hint,
        content_type=file.content_type,
        source_type="file",
        source_url=None,
    )

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

    return VideoUploadResponse(id=job.id, status=job.status, message="Video upload accepted for processing")


@router.post("/import", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def import_video_from_url(
    request: VideoUrlUploadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoUploadResponse:
    normalized_hint = (request.language_hint or "auto").strip().lower()
    if normalized_hint not in ALLOWED_LANGUAGE_HINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language hint")

    parsed_url = urlparse(str(request.video_url))
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid video URL is required")

    provisional_name = parsed_url.path.rsplit("/", 1)[-1] or parsed_url.netloc
    job = _create_job_record(
        db=db,
        auth_context=auth_context,
        original_filename=provisional_name[:255],
        language_hint=normalized_hint,
        content_type=None,
        source_type="url",
        source_url=str(request.video_url),
    )
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_video_job, job.id, settings.audio_dir)
    return VideoUploadResponse(id=job.id, status=job.status, message="Video URL accepted for processing")


@router.post("/{job_id}/retry", response_model=VideoUploadResponse)
def retry_video_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoUploadResponse:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed jobs can be retried")

    if job.source_type == "url":
        if not job.source_url:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The original source URL is missing")

        file_path = Path(job.storage_path) if job.storage_path else None
        if file_path and not file_path.exists():
            job.storage_path = ""
            job.stored_filename = job.original_filename
            job.content_type = None
            job.file_size_bytes = 0
            job.duration_seconds = None
            job.video_metadata = {}
    else:
        file_path = Path(job.storage_path)
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original video file is missing")

    job.status = JobStatus.QUEUED.value
    job.error_message = None
    job.transcript = None
    job.transcript_segments = []
    job.summary = None
    job.custom_summary_prompt = None
    job.custom_summary_text = None
    job.custom_summary_updated_at = None
    job.sentiment = None
    job.action_items = []
    job.detected_language = None
    job.completed_at = None
    db.commit()

    background_tasks.add_task(process_video_job, job.id, settings.audio_dir)
    return VideoUploadResponse(id=job.id, status=job.status, message="Retry started")


@router.post("/{job_id}/chat", response_model=VideoChatResponse)
def chat_about_video(
    job_id: str,
    request: VideoChatRequest,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoChatResponse:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    if job.status != JobStatus.COMPLETED.value or not _job_has_chat_context(job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transcript chat is only available for completed jobs")

    try:
        _store_chat_message(db, job.id, auth_context, "user", request.question.strip())
        response = request_transcript_chat(
            transcript=job.transcript or "",
            transcript_segments=job.transcript_segments or [],
            question=request.question.strip(),
            chat_history=[message.model_dump() for message in request.chat_history],
            asked_questions=[question.strip() for question in request.asked_questions if question.strip()],
            video_title=job.original_filename,
            source_language=job.detected_language or job.language_hint,
            summary=job.summary,
            sentiment=job.sentiment,
            action_items=job.action_items or [],
        )
        _store_chat_message(db, job.id, auth_context, "assistant", response.answer)
        db.commit()
        return response
    except AgentServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{job_id}/chat/suggestions", response_model=VideoChatSuggestionResponse)
def suggest_video_questions(
    job_id: str,
    request: VideoChatSuggestionRequest,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoChatSuggestionResponse:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    if job.status != JobStatus.COMPLETED.value or not _job_has_chat_context(job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transcript chat is only available for completed jobs")

    try:
        return request_transcript_chat_suggestions(
            transcript=job.transcript or "",
            transcript_segments=job.transcript_segments or [],
            asked_questions=[question.strip() for question in request.asked_questions if question.strip()],
            video_title=job.original_filename,
            source_language=job.detected_language or job.language_hint,
            summary=job.summary,
            sentiment=job.sentiment,
            action_items=job.action_items or [],
        )
    except AgentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{job_id}/summary/regenerate", response_model=CustomSummaryResponse)
def regenerate_video_summary(
    job_id: str,
    request: CustomSummaryRequest,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> CustomSummaryResponse:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    if job.status != JobStatus.COMPLETED.value or not _job_has_chat_context(job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Custom summary is only available for completed jobs")

    try:
        response = request_custom_summary(
            transcript=_job_transcript_text(job),
            instruction=request.instruction.strip(),
            video_title=job.original_filename,
            source_language=job.detected_language or job.language_hint,
        )
    except AgentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    updated_at = datetime.now(timezone.utc)
    job.custom_summary_prompt = request.instruction.strip()
    job.custom_summary_text = response.summary
    job.custom_summary_updated_at = updated_at
    db.commit()

    return CustomSummaryResponse(
        summary=response.summary,
        instruction=job.custom_summary_prompt,
        updated_at=updated_at,
    )


@router.get("/{job_id}/chat/messages", response_model=list[VideoChatMessageRead])
def list_video_chat_messages(
    job_id: str,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> list[VideoChatMessageRecord]:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")

    statement = (
        select(VideoChatMessageRecord)
        .where(
            VideoChatMessageRecord.job_id == job_id,
            VideoChatMessageRecord.tenant_id == auth_context.tenant_id,
        )
        .order_by(VideoChatMessageRecord.created_at.asc())
    )
    return list(db.scalars(statement).all())


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


def _get_tenant_job(db: Session, auth_context: AuthContext, job_id: str) -> VideoJob | None:
    statement = select(VideoJob).where(
        VideoJob.id == job_id,
        VideoJob.tenant_id == auth_context.tenant_id,
    )
    return db.scalar(statement)


def _job_has_chat_context(job: VideoJob) -> bool:
    if (job.transcript or "").strip():
        return True
    return any(str(segment.get("text", "")).strip() for segment in (job.transcript_segments or []))


def _job_transcript_text(job: VideoJob) -> str:
    if (job.transcript or "").strip():
        return (job.transcript or "").strip()
    return "\n".join(
        text
        for text in (str(segment.get("text", "")).strip() for segment in (job.transcript_segments or []))
        if text
    )


def _store_chat_message(
    db: Session,
    job_id: str,
    auth_context: AuthContext,
    role: str,
    content: str,
) -> None:
    db.execute(
        VideoChatMessageRecord.__table__.insert().values(
            id=str(uuid4()),
            job_id=job_id,
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
    )


def _safe_filename(filename: str) -> str:
    return Path(filename).name.replace(" ", "_")


def _normalize_language_hint(language_hint: str) -> str:
    if language_hint in {"english"}:
        return "en"
    if language_hint in {"tagalog"}:
        return "tl"
    return language_hint


def _create_job_record(
    db: Session,
    auth_context: AuthContext,
    original_filename: str,
    language_hint: str,
    content_type: str | None,
    source_type: str,
    source_url: str | None,
) -> VideoJob:
    job = VideoJob(
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id,
        source_type=source_type,
        source_url=source_url,
        original_filename=original_filename,
        stored_filename=original_filename,
        storage_path="",
        content_type=content_type,
        language_hint=_normalize_language_hint(language_hint),
        status=JobStatus.QUEUED.value,
    )
    db.add(job)
    db.flush()
    return job
