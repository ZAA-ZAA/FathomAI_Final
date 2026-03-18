from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import mimetypes
import shutil
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import EmailStr, TypeAdapter, ValidationError
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
    VideoReportEmailRequest,
    VideoReportRequest,
    VideoReportResponse,
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
from app.services.host_paths import resolve_client_source_path
from app.services.media import probe_video_metadata
from app.services.object_storage import (
    is_remote_storage_path,
    open_storage_stream,
    open_video_stream,
    upload_video_source,
)
from app.services.report_delivery import (
    REPORT_TARGETS,
    generate_and_store_report,
    generate_store_and_email_report,
    get_report_download_name,
    get_report_media_type,
    get_report_storage_path,
    is_email_delivery_configured,
    validate_requested_pdf_path,
)
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

    if not job.storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video source file not found")

    if is_remote_storage_path(job.storage_path):
        body, media_type, headers = open_video_stream(
            job.storage_path,
            job.content_type,
            job.original_filename,
        )
        return StreamingResponse(_iter_stream_body(body), media_type=media_type, headers=headers)

    file_path = Path(job.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video source file not found")

    return FileResponse(file_path, media_type=job.content_type or "video/mp4", filename=job.original_filename)


@router.post("/{job_id}/reports/{target}", response_model=VideoReportResponse)
def generate_video_report(
    job_id: str,
    target: str,
    request: VideoReportRequest,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoReportResponse:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    _ensure_report_ready(job, target)

    requested_path = _normalize_report_export_path(request.export_pdf_path)
    try:
        report_record = generate_and_store_report(
            job,
            target,
            requested_path,
            show_timestamps=request.show_timestamps,
            source="manual_export",
            use_custom_summary=request.use_custom_summary,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    _save_report_record(job, target, report_record)
    db.commit()

    if report_record.get("email_status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_coerce_optional_str(report_record.get("email_error")) or "Unable to send report email",
        )

    generated_at = _parse_optional_datetime(report_record.get("generated_at"))
    return VideoReportResponse(
        target=target,
        message=f"{target.title()} PDF generated successfully",
        saved_path=_coerce_optional_str(report_record.get("saved_path")),
        storage_path=_coerce_optional_str(report_record.get("storage_path")),
        filename=_coerce_optional_str(report_record.get("filename")),
        email_status=_coerce_optional_str(report_record.get("email_status")),
        emailed_to=_coerce_optional_str(report_record.get("emailed_to")),
        generated_at=generated_at,
    )


@router.get("/{job_id}/reports/{target}", response_model=None)
def download_video_report(
    job_id: str,
    target: str,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
):
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    _ensure_valid_report_target(target)

    storage_path = get_report_storage_path(job, target)
    if not storage_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report PDF not found")

    filename = get_report_download_name(job, target)
    if is_remote_storage_path(storage_path):
        body, media_type, headers = open_storage_stream(storage_path, get_report_media_type(), filename)
        return StreamingResponse(_iter_stream_body(body), media_type=media_type, headers=headers)

    file_path = Path(storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report PDF not found")
    return FileResponse(file_path, media_type=get_report_media_type(), filename=filename)


@router.post("/{job_id}/reports/{target}/email", response_model=VideoReportResponse)
def email_video_report(
    job_id: str,
    target: str,
    request: VideoReportEmailRequest,
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoReportResponse:
    job = _get_tenant_job(db, auth_context, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    _ensure_report_ready(job, target)

    if not is_email_delivery_configured():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email delivery is not configured on the server")

    requested_path = _normalize_report_export_path(request.export_pdf_path)
    try:
        report_record = generate_store_and_email_report(
            str(request.recipient_email).lower(),
            job,
            target,
            requested_path,
            show_timestamps=request.show_timestamps,
            source="manual_email",
            use_custom_summary=request.use_custom_summary,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    _save_report_record(job, target, report_record)
    db.commit()

    generated_at = _parse_optional_datetime(report_record.get("generated_at"))
    return VideoReportResponse(
        target=target,
        message=f"{target.title()} report emailed successfully",
        saved_path=_coerce_optional_str(report_record.get("saved_path")),
        storage_path=_coerce_optional_str(report_record.get("storage_path")),
        filename=_coerce_optional_str(report_record.get("filename")),
        email_status=_coerce_optional_str(report_record.get("email_status")),
        emailed_to=_coerce_optional_str(report_record.get("emailed_to")),
        generated_at=generated_at,
    )


@router.post("/upload", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    file_path: str | None = Form(None),
    language_hint: str = Form("auto"),
    notify_email: str | None = Form(None),
    export_pdf: bool = Form(False),
    export_pdf_path: str | None = Form(None),
    db: Session = Depends(get_db),
    auth_context: AuthContext = Depends(require_auth_context),
) -> VideoUploadResponse:
    normalized_hint = (language_hint or "auto").strip().lower()
    if normalized_hint not in ALLOWED_LANGUAGE_HINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported language hint")

    delivery_options = _build_delivery_options(notify_email, export_pdf, export_pdf_path)

    using_uploaded_file = file is not None
    using_server_file_path = bool(file_path and file_path.strip())
    if using_uploaded_file == using_server_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of file or file_path",
        )

    if using_uploaded_file and file and not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    if using_uploaded_file and file:
        source_name = file.filename
    else:
        try:
            resolved_source_path = resolve_client_source_path(file_path or "")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        source_name = resolved_source_path.name

    extension = Path(source_name).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported video file type")

    upload_content_type = _normalize_upload_content_type(
        file.content_type if using_uploaded_file and file else None,
        source_name,
    )

    job = _create_job_record(
        db=db,
        auth_context=auth_context,
        original_filename=source_name,
        language_hint=normalized_hint,
        content_type=upload_content_type,
        source_type="file_path" if using_server_file_path else "file",
        source_url=file_path.strip() if using_server_file_path and file_path else None,
        initial_video_metadata={"delivery": delivery_options},
    )

    job_directory = settings.upload_dir / auth_context.tenant_id / job.id
    job_directory.mkdir(parents=True, exist_ok=True)
    stored_path = job_directory / _safe_filename(source_name)

    try:
        if using_uploaded_file and file:
            file_size = _save_upload(file, stored_path)
        else:
            shutil.copy2(resolved_source_path, stored_path)
            file_size = stored_path.stat().st_size
    except HTTPException:
        stored_path.unlink(missing_ok=True)
        raise
    finally:
        if file is not None:
            file.file.close()

    try:
        metadata = probe_video_metadata(stored_path)
        job.stored_filename = stored_path.name
        job.file_size_bytes = file_size
        job.duration_seconds = metadata.get("duration_seconds")
        job.video_metadata = {**metadata, "delivery": delivery_options}
        job.storage_path = upload_video_source(
            stored_path,
            auth_context.tenant_id,
            job.id,
            job.stored_filename,
            job.content_type,
        )
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_video_job, job.id, settings.audio_dir, str(stored_path))

    return VideoUploadResponse(
        id=job.id,
        status=job.status,
        message="Video upload accepted for processing",
        notify_email=delivery_options["notify_email"],
        export_pdf=delivery_options["export_pdf"],
        export_pdf_path=delivery_options["export_pdf_path"],
    )


@router.post("/transcribe", response_model=VideoUploadResponse, status_code=status.HTTP_202_ACCEPTED)
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

    delivery_options = _build_delivery_options(
        request.notify_email,
        request.export_pdf,
        request.export_pdf_path,
    )

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
        initial_video_metadata={"delivery": delivery_options},
    )
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_video_job, job.id, settings.audio_dir)
    return VideoUploadResponse(
        id=job.id,
        status=job.status,
        message="Video URL accepted for processing",
        notify_email=delivery_options["notify_email"],
        export_pdf=delivery_options["export_pdf"],
        export_pdf_path=delivery_options["export_pdf_path"],
    )


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
        if not job.source_url and not job.storage_path:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The original source URL is missing")

        file_path = Path(job.storage_path) if job.storage_path and not is_remote_storage_path(job.storage_path) else None
        if file_path and not file_path.exists():
            job.storage_path = ""
            job.stored_filename = job.original_filename
            job.content_type = None
            job.file_size_bytes = 0
            job.duration_seconds = None
            job.video_metadata = {}
    else:
        if not job.storage_path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original video file is missing")
        if is_remote_storage_path(job.storage_path):
            file_path = None
        else:
            file_path = Path(job.storage_path)
        if file_path and not file_path.exists():
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
    metadata = dict(job.video_metadata or {})
    metadata["custom_summary_action_items"] = response.action_items
    job.video_metadata = metadata
    db.commit()

    return CustomSummaryResponse(
        summary=response.summary,
        action_items=response.action_items,
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


def _normalize_upload_content_type(content_type: str | None, filename: str) -> str | None:
    normalized = (content_type or "").strip().lower()
    if normalized.startswith("video/"):
        return normalized

    guessed_type = mimetypes.guess_type(filename)[0]
    if guessed_type and guessed_type.startswith("video/"):
        return guessed_type

    return normalized or None


def _build_delivery_options(
    notify_email: str | None,
    export_pdf: bool,
    export_pdf_path: str | None,
) -> dict[str, str | bool | None]:
    normalized_email: str | None = None
    if notify_email:
        try:
            normalized_email = str(TypeAdapter(EmailStr).validate_python(notify_email.strip())).lower()
        except ValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid notification email is required") from exc
        if not is_email_delivery_configured():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email delivery is not configured on the server")

    normalized_export_path = export_pdf_path.strip() if export_pdf_path else None
    if normalized_export_path and not export_pdf:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="export_pdf must be true when export_pdf_path is provided")
    if normalized_export_path:
        try:
            normalized_export_path = validate_requested_pdf_path(normalized_export_path)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="export_pdf_path must be a relative path or an allowed absolute Windows, WSL, or Linux path",
            ) from exc

    return {
        "notify_email": normalized_email,
        "export_pdf": bool(export_pdf),
        "export_pdf_path": normalized_export_path or None,
    }


def _iter_stream_body(body):
    try:
        yield from body.iter_chunks()
    finally:
        body.close()


def _create_job_record(
    db: Session,
    auth_context: AuthContext,
    original_filename: str,
    language_hint: str,
    content_type: str | None,
    source_type: str,
    source_url: str | None,
    initial_video_metadata: dict | None = None,
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
        video_metadata=initial_video_metadata or {},
    )
    db.add(job)
    db.flush()
    return job


def _ensure_valid_report_target(target: str) -> None:
    if target not in REPORT_TARGETS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported report target")


def _ensure_report_ready(job: VideoJob, target: str) -> None:
    _ensure_valid_report_target(target)
    if job.status != JobStatus.COMPLETED.value or not _job_has_chat_context(job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reports are only available for completed jobs")


def _normalize_report_export_path(export_pdf_path: str | None) -> str | None:
    normalized_export_path = export_pdf_path.strip() if export_pdf_path else None
    if not normalized_export_path:
        return None
    try:
        return validate_requested_pdf_path(normalized_export_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="export_pdf_path must be a relative path or an allowed absolute Windows, WSL, or Linux path",
        ) from exc


def _save_report_record(job: VideoJob, target: str, report_record: dict[str, object]) -> None:
    metadata = dict(job.video_metadata or {})
    reports = dict(metadata.get("reports") or {})
    reports[target] = report_record
    metadata["reports"] = reports
    job.video_metadata = metadata


def _coerce_optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _parse_optional_datetime(value: object) -> datetime | None:
    text_value = _coerce_optional_str(value)
    if not text_value:
        return None
    try:
        return datetime.fromisoformat(text_value)
    except ValueError:
        return None
