from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status

from app.core.config import settings

REMOTE_STORAGE_SCHEME = "r2://"


def is_remote_storage_enabled() -> bool:
    return settings.video_storage_provider == "r2"


def is_remote_storage_path(storage_path: str | None) -> bool:
    return bool(storage_path and storage_path.startswith(REMOTE_STORAGE_SCHEME))


def upload_video_source(
    local_path: Path,
    tenant_id: str,
    job_id: str,
    stored_filename: str,
    content_type: str | None,
) -> str:
    if not is_remote_storage_enabled():
        return str(local_path)

    try:
        with local_path.open("rb") as file_handle:
            return _upload_object(file_handle, build_video_object_key(tenant_id, job_id, stored_filename), content_type)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to upload the source video to object storage.",
        ) from exc


def upload_report_bytes(
    pdf_bytes: bytes,
    tenant_id: str,
    job_id: str,
    relative_path: str,
    content_type: str = "application/pdf",
) -> str:
    if not is_remote_storage_enabled():
        raise RuntimeError("Remote object storage is not enabled")

    try:
        return _upload_object(pdf_bytes, build_report_object_key(tenant_id, job_id, relative_path), content_type)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to upload the report PDF to object storage.",
        ) from exc


def download_video_source(storage_path: str, destination_path: Path) -> Path:
    if not is_remote_storage_path(storage_path):
        return Path(storage_path)

    bucket_name, object_key = parse_remote_storage_path(storage_path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination_path.open("wb") as file_handle:
            get_s3_client().download_fileobj(bucket_name, object_key, file_handle)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video source file not found") from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to download the source video from object storage.",
        ) from exc
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to download the source video from object storage.",
        ) from exc

    return destination_path


def open_storage_stream(storage_path: str, content_type: str | None, filename: str) -> tuple[object, str, dict[str, str]]:
    bucket_name, object_key = parse_remote_storage_path(storage_path)
    try:
        response = get_s3_client().get_object(Bucket=bucket_name, Key=object_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video source file not found") from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to stream the source video from object storage.",
        ) from exc
    except BotoCoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to stream the source video from object storage.",
        ) from exc

    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
    }
    content_length = response.get("ContentLength")
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    media_type = response.get("ContentType") or content_type or "video/mp4"
    return response["Body"], media_type, headers


def open_video_stream(storage_path: str, content_type: str | None, filename: str) -> tuple[object, str, dict[str, str]]:
    return open_storage_stream(storage_path, content_type, filename)


def build_video_object_key(tenant_id: str, job_id: str, stored_filename: str) -> str:
    return f"{settings.r2_key_prefix}/{tenant_id}/{job_id}/{Path(stored_filename).name}"


def build_report_object_key(tenant_id: str, job_id: str, relative_path: str) -> str:
    normalized_path = Path(relative_path).as_posix().lstrip("/")
    return f"{settings.r2_key_prefix}/{tenant_id}/{job_id}/reports/{normalized_path}"


def build_remote_storage_path(bucket_name: str, object_key: str) -> str:
    return f"{REMOTE_STORAGE_SCHEME}{bucket_name}/{object_key}"


def parse_remote_storage_path(storage_path: str) -> tuple[str, str]:
    if not is_remote_storage_path(storage_path):
        raise ValueError("Storage path does not point to remote object storage")

    remainder = storage_path[len(REMOTE_STORAGE_SCHEME):]
    bucket_name, _, object_key = remainder.partition("/")
    if not bucket_name or not object_key:
        raise ValueError("Invalid remote storage path")
    return bucket_name, object_key


@lru_cache(maxsize=1)
def get_s3_client():
    if not is_remote_storage_enabled():
        raise RuntimeError("Remote object storage is not enabled")

    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def _upload_object(body: object, object_key: str, content_type: str | None) -> str:
    bucket_name = settings.r2_bucket_name
    put_kwargs = {
        "Bucket": bucket_name,
        "Key": object_key,
        "Body": body,
    }
    if content_type:
        put_kwargs["ContentType"] = content_type
    get_s3_client().put_object(**put_kwargs)
    return build_remote_storage_path(bucket_name, object_key)
