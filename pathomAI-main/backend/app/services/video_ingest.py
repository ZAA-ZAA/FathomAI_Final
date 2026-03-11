from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from yt_dlp import DownloadError, YoutubeDL

from app.core.config import settings


def download_video_from_url(video_url: str, destination_dir: Path) -> tuple[Path, dict[str, Any]]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(destination_dir / "%(title).120B-%(id)s.%(ext)s")

    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
    }

    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(video_url, download=True)
            resolved_path = _resolve_downloaded_path(info, destination_dir)
    except DownloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to download the provided video URL: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while downloading the video URL: {exc}",
        ) from exc

    file_size = resolved_path.stat().st_size
    if file_size > settings.max_upload_size_bytes:
        resolved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Downloaded video exceeds the {settings.max_upload_size_bytes // (1024 * 1024)} MB limit",
        )

    return resolved_path, {
        "extractor": info.get("extractor"),
        "extractor_key": info.get("extractor_key"),
        "title": info.get("title"),
        "webpage_url": info.get("webpage_url") or video_url,
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "content_type": mimetypes.guess_type(resolved_path.name)[0],
    }


def build_filename_from_download(download_metadata: dict[str, Any], file_path: Path) -> str:
    title = str(download_metadata.get("title") or "").strip()
    extension = file_path.suffix or ".mp4"
    if title:
        safe_title = title.replace("/", "_").replace("\\", "_").strip()
        return f"{safe_title}{extension}"
    return file_path.name


def _resolve_downloaded_path(info: dict[str, Any], destination_dir: Path) -> Path:
    requested_downloads = info.get("requested_downloads") or []
    for entry in requested_downloads:
        filepath = entry.get("filepath")
        if filepath:
            candidate = Path(filepath)
            if candidate.exists():
                return candidate

    if info.get("_filename"):
        candidate = Path(info["_filename"])
        if candidate.exists():
            return candidate

    files = sorted([path for path in destination_dir.iterdir() if path.is_file()], key=lambda item: item.stat().st_mtime, reverse=True)
    if files:
        return files[0]

    raise FileNotFoundError("Downloaded video file could not be located")
