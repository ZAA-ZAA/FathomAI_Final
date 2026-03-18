from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.core.config import settings

WINDOWS_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


@dataclass(frozen=True, slots=True)
class ExportDestination:
    logical_path: str
    local_mirror_path: Path | None
    display_path: str


def resolve_client_source_path(raw_path: str) -> Path:
    normalized = raw_path.strip()
    if not normalized:
        raise ValueError("file_path cannot be empty")

    mapped_path = _map_client_path(normalized)
    if mapped_path is None:
        raise ValueError("file_path must use an allowed Windows, WSL, or Linux absolute path")
    if not mapped_path.exists():
        raise FileNotFoundError("The file_path does not exist from the server's point of view")
    if not mapped_path.is_file():
        raise ValueError("file_path must point to a single file")
    return mapped_path


def normalize_requested_export_path(raw_path: str) -> str:
    normalized = raw_path.strip()
    if not normalized:
        raise ValueError("export_pdf_path cannot be empty")

    if WINDOWS_PATH_PATTERN.match(normalized):
        return str(PureWindowsPath(normalized))

    if normalized.startswith("/"):
        return str(PurePosixPath(normalized))

    return _normalize_relative_path(PurePosixPath(normalized))


def resolve_export_destination(requested_path: str | None, default_filename: str) -> ExportDestination:
    if not requested_path:
        logical_path = f"reports/{default_filename}"
        return ExportDestination(
            logical_path=logical_path,
            local_mirror_path=None,
            display_path=logical_path,
        )

    normalized = normalize_requested_export_path(requested_path)
    mapped_path = _map_client_path(normalized)
    if mapped_path is not None:
        final_path = _ensure_pdf_path(mapped_path, default_filename)
        logical_path = _build_external_logical_path(normalized, final_path.name)
        return ExportDestination(
            logical_path=logical_path,
            local_mirror_path=final_path,
            display_path=_format_display_path(normalized, final_path.name),
        )

    relative_path = _ensure_pdf_relative_path(PurePosixPath(normalized), default_filename)
    return ExportDestination(
        logical_path=relative_path,
        local_mirror_path=None,
        display_path=relative_path,
    )


def _map_client_path(client_path: str) -> Path | None:
    if WINDOWS_PATH_PATTERN.match(client_path):
        return _map_windows_path(PureWindowsPath(client_path))

    posix_path = PurePosixPath(client_path)
    if client_path.startswith(settings.client_wsl_windows_root):
        return _map_posix_root(posix_path, PurePosixPath(settings.client_wsl_windows_root), settings.host_mount_windows_root)
    if client_path.startswith(settings.client_linux_root):
        return _map_posix_root(posix_path, PurePosixPath(settings.client_linux_root), settings.host_mount_linux_root)
    return None


def _map_windows_path(client_path: PureWindowsPath) -> Path | None:
    root = PureWindowsPath(settings.client_windows_root)
    try:
        relative = client_path.relative_to(root)
    except ValueError:
        return None
    return settings.host_mount_windows_root.joinpath(*relative.parts)


def _map_posix_root(client_path: PurePosixPath, root: PurePosixPath, mount_root: Path) -> Path | None:
    try:
        relative = client_path.relative_to(root)
    except ValueError:
        return None
    return mount_root.joinpath(*relative.parts)


def _normalize_relative_path(relative_path: PurePosixPath) -> str:
    normalized_parts = [part for part in relative_path.parts if part not in {"", "."}]
    if any(part == ".." for part in normalized_parts):
        raise ValueError("Relative paths cannot contain '..'")
    if not normalized_parts:
        raise ValueError("Relative paths cannot be empty")
    return PurePosixPath(*normalized_parts).as_posix()


def _ensure_pdf_path(path: Path, default_filename: str) -> Path:
    if path.suffix.lower() == ".pdf":
        return path
    return path / default_filename


def _ensure_pdf_relative_path(path: PurePosixPath, default_filename: str) -> str:
    normalized = _normalize_relative_path(path)
    pure_path = PurePosixPath(normalized)
    if pure_path.suffix.lower() == ".pdf":
        return pure_path.as_posix()
    return (pure_path / default_filename).as_posix()


def _build_external_logical_path(client_path: str, filename: str) -> str:
    if WINDOWS_PATH_PATTERN.match(client_path):
        relative = PureWindowsPath(client_path).relative_to(PureWindowsPath(settings.client_windows_root))
        return PurePosixPath("external", "windows", *relative.parts[:-1], filename).as_posix()

    posix_path = PurePosixPath(client_path)
    if client_path.startswith(settings.client_wsl_windows_root):
        relative = posix_path.relative_to(PurePosixPath(settings.client_wsl_windows_root))
        return PurePosixPath("external", "windows", *relative.parts[:-1], filename).as_posix()

    relative = posix_path.relative_to(PurePosixPath(settings.client_linux_root))
    return PurePosixPath("external", "linux", *relative.parts[:-1], filename).as_posix()


def _format_display_path(client_path: str, filename: str) -> str:
    if WINDOWS_PATH_PATTERN.match(client_path):
        pure_path = PureWindowsPath(client_path)
        return str(pure_path if pure_path.suffix.lower() == ".pdf" else pure_path / filename)

    pure_path = PurePosixPath(client_path)
    return str(pure_path if pure_path.suffix.lower() == ".pdf" else pure_path / filename)
