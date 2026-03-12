from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status
import gdown
from yt_dlp import DownloadError, YoutubeDL

from app.core.config import settings


def download_video_from_url(video_url: str, destination_dir: Path) -> tuple[Path, dict[str, Any]]:
    if _is_google_drive_url(video_url):
        return _download_google_drive_video(video_url, destination_dir)

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


def _download_google_drive_video(video_url: str, destination_dir: Path) -> tuple[Path, dict[str, Any]]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    if "/folders/" in video_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Drive folder links are not supported. Provide a share link for a single public video file.",
        )

    output_path = destination_dir / "google-drive-import"
    try:
        downloaded_path = gdown.download(
            url=video_url,
            output=str(output_path),
            quiet=True,
            fuzzy=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unable to download the Google Drive file. Make sure the link is a valid public file-share link "
                f"and not private or expired. Details: {exc}"
            ),
        ) from exc

    if not downloaded_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to download the Google Drive file. Make sure the link points to a public video file.",
        )

    resolved_path = Path(downloaded_path)
    if not resolved_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google Drive download completed but the file could not be located on disk.",
        )

    file_size = resolved_path.stat().st_size
    if file_size > settings.max_upload_size_bytes:
        resolved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Downloaded video exceeds the {settings.max_upload_size_bytes // (1024 * 1024)} MB limit",
        )

    return resolved_path, {
        "extractor": "google_drive",
        "extractor_key": "GoogleDrive",
        "title": resolved_path.stem,
        "webpage_url": video_url,
        "uploader": "Google Drive",
        "duration": None,
        "thumbnail": None,
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


def _is_google_drive_url(video_url: str) -> bool:
    parsed = urlparse(video_url)
    return parsed.netloc.lower() in {"drive.google.com", "docs.google.com"}
