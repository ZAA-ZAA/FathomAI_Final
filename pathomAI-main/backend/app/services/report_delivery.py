from __future__ import annotations

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.models import VideoJob
from app.services.host_paths import normalize_requested_export_path, resolve_export_destination
from app.services.object_storage import is_remote_storage_enabled, upload_report_bytes

REPORT_TARGETS = {"summary", "transcript"}


def is_email_delivery_configured() -> bool:
    return bool(settings.gmail_from and settings.gmail_app_password)


def validate_requested_pdf_path(requested_path: str) -> str:
    return normalize_requested_export_path(requested_path)


def generate_and_store_report(
    job: VideoJob,
    target: str,
    requested_path: str | None = None,
    *,
    show_timestamps: bool = True,
    source: str = "manual",
    use_custom_summary: bool | None = None,
) -> dict[str, object]:
    report_record, _ = _build_report_record(
        job,
        target,
        requested_path,
        show_timestamps=show_timestamps,
        source=source,
        use_custom_summary=use_custom_summary,
    )
    return report_record


def generate_store_and_email_report(
    recipient: str,
    job: VideoJob,
    target: str,
    requested_path: str | None = None,
    *,
    show_timestamps: bool = True,
    source: str = "manual",
    use_custom_summary: bool | None = None,
) -> dict[str, object]:
    report_record, pdf_bytes = _build_report_record(
        job,
        target,
        requested_path,
        show_timestamps=show_timestamps,
        source=source,
        use_custom_summary=use_custom_summary,
    )
    try:
        send_report_email(recipient, job, target, str(report_record["filename"]), pdf_bytes, use_custom_summary=use_custom_summary)
        report_record["email_status"] = "sent"
        report_record["email_error"] = None
        report_record["emailed_to"] = recipient
        report_record["emailed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        report_record["email_status"] = "failed"
        report_record["email_error"] = str(exc)
        report_record["emailed_to"] = recipient
    return report_record


def send_report_email(
    recipient: str,
    job: VideoJob,
    target: str,
    filename: str,
    attachment_bytes: bytes,
    *,
    use_custom_summary: bool | None = None,
) -> None:
    if not is_email_delivery_configured():
        raise RuntimeError("Email delivery is not configured on the server")

    message = EmailMessage()
    message["From"] = settings.gmail_from
    message["To"] = recipient
    message["Subject"] = f"PathomAI {target.title()} Report: {job.original_filename}"
    message.set_content(_build_email_body(job, target, use_custom_summary=use_custom_summary))
    message.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(settings.gmail_from, settings.gmail_app_password)
            smtp.send_message(message)
    except Exception as exc:
        raise RuntimeError(f"Unable to send {target} email: {exc}") from exc


def get_report_filename(job: VideoJob, target: str) -> str:
    _ensure_target(target)
    suffix = "summary" if target == "summary" else "transcript"
    stem = Path(job.original_filename).stem or job.id
    return f"{stem}-{suffix}.pdf"


def get_report_record(job: VideoJob, target: str) -> dict[str, object] | None:
    reports = job.video_metadata.get("reports", {}) if isinstance(job.video_metadata, dict) else {}
    report = reports.get(target)
    return report if isinstance(report, dict) else None


def get_report_storage_path(job: VideoJob, target: str) -> str | None:
    report = get_report_record(job, target)
    if not report:
        return None
    storage_path = report.get("storage_path")
    if not isinstance(storage_path, str) or not storage_path.strip():
        return None
    return storage_path.strip()


def get_report_media_type() -> str:
    return "application/pdf"


def get_report_download_name(job: VideoJob, target: str) -> str:
    report = get_report_record(job, target)
    filename = report.get("filename") if report else None
    if isinstance(filename, str) and filename.strip():
        return filename.strip()
    return get_report_filename(job, target)


def _build_report_record(
    job: VideoJob,
    target: str,
    requested_path: str | None,
    *,
    show_timestamps: bool,
    source: str,
    use_custom_summary: bool | None,
) -> tuple[dict[str, object], bytes]:
    _ensure_target(target)
    pdf_bytes = _generate_pdf_bytes(job, target, show_timestamps=show_timestamps, use_custom_summary=use_custom_summary)
    filename = get_report_filename(job, target)
    destination = resolve_export_destination(requested_path, filename)
    storage_path = _store_report_bytes(job, destination, pdf_bytes)
    return (
        {
            "target": target,
            "status": "saved",
            "saved_path": destination.display_path,
            "storage_path": storage_path,
            "filename": filename,
            "content_type": get_report_media_type(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "show_timestamps": show_timestamps if target == "transcript" else None,
            "use_custom_summary": use_custom_summary if target == "summary" else None,
            "source": source,
            "error": None,
        },
        pdf_bytes,
    )


def _generate_pdf_bytes(job: VideoJob, target: str, *, show_timestamps: bool, use_custom_summary: bool | None) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 48
    y = height - 56

    def ensure_space(minimum_height: float = 60) -> None:
        nonlocal y
        if y < minimum_height:
            pdf.showPage()
            y = height - 56

    def draw_line(text: str, font_name: str = "Helvetica", font_size: int = 11, leading: int = 16) -> None:
        nonlocal y
        ensure_space()
        pdf.setFont(font_name, font_size)
        pdf.drawString(margin_x, y, text)
        y -= leading

    def draw_wrapped(text: str, font_name: str = "Helvetica", font_size: int = 11, leading: int = 16) -> None:
        max_width = width - (margin_x * 2)
        avg_char_width = max(stringWidth("M", font_name, font_size), 1)
        line_length = max(int(max_width / avg_char_width), 24)
        for paragraph in (text or "").splitlines() or [""]:
            for line in wrap(paragraph, width=line_length) or [""]:
                draw_line(line, font_name=font_name, font_size=font_size, leading=leading)

    pdf.setTitle(f"{job.original_filename} {target.title()}")
    draw_line(f"PathomAI {target.title()} Report", font_name="Helvetica-Bold", font_size=18, leading=24)
    draw_line(job.original_filename, font_name="Helvetica-Bold", font_size=14, leading=22)
    draw_line(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", font_size=10, leading=18)
    if job.source_type == "url" and job.source_url:
        draw_wrapped(f"Source URL: {job.source_url}", font_size=10, leading=14)
    y -= 8

    if target == "summary":
        draw_line("Summary", font_name="Helvetica-Bold", font_size=13, leading=20)
        draw_wrapped(_get_summary_text(job, use_custom_summary) or "No summary available.")
        y -= 8

        draw_line("Sentiment", font_name="Helvetica-Bold", font_size=13, leading=20)
        draw_wrapped(job.sentiment or "Not available.")
        y -= 8

        draw_line("Action Items", font_name="Helvetica-Bold", font_size=13, leading=20)
        action_items = _get_summary_action_items(job, use_custom_summary)
        if action_items:
            for item in action_items:
                draw_wrapped(f"- {item}")
        else:
            draw_wrapped("No action items available.")
    else:
        draw_line("Transcript", font_name="Helvetica-Bold", font_size=13, leading=20)
        entries = _get_transcript_entries(job)
        if not entries:
            draw_wrapped("No transcript content available.")
        for index, entry in enumerate(entries, start=1):
            if show_timestamps:
                draw_line(entry["label"], font_name="Helvetica-Bold", font_size=10, leading=14)
            else:
                draw_line(f"Segment {index}", font_name="Helvetica-Bold", font_size=10, leading=14)
            draw_wrapped(entry["text"], leading=15)
            y -= 4

    pdf.save()
    return buffer.getvalue()


def _build_email_body(job: VideoJob, target: str, *, use_custom_summary: bool | None) -> str:
    lines = [
        f"Video: {job.original_filename}",
        f"Status: {job.status}",
        "",
    ]

    if target == "summary":
        lines.extend(
            [
                "Summary:",
                _get_summary_text(job, use_custom_summary) or "No summary available.",
                "",
                f"Sentiment: {job.sentiment or 'Not available'}",
                "",
                "Action Items:",
            ]
        )
        action_items = _get_summary_action_items(job, use_custom_summary)
        if action_items:
            lines.extend(f"- {item}" for item in action_items)
        else:
            lines.append("- No action items available.")
    else:
        lines.extend(
            [
                "Transcript excerpt:",
                (job.transcript or "No transcript available.")[:4000],
            ]
        )

    if job.source_type == "url" and job.source_url:
        lines.extend(["", f"Source URL: {job.source_url}"])

    return "\n".join(lines)


def _get_summary_text(job: VideoJob, use_custom_summary: bool | None) -> str:
    use_custom = bool(use_custom_summary)
    if use_custom and job.custom_summary_text:
        return job.custom_summary_text
    return job.summary or ""


def _get_summary_action_items(job: VideoJob, use_custom_summary: bool | None) -> list[str]:
    metadata = job.video_metadata if isinstance(job.video_metadata, dict) else {}
    custom_items = metadata.get("custom_summary_action_items")
    if use_custom_summary and job.custom_summary_text and isinstance(custom_items, list):
        normalized = [str(item).strip() for item in custom_items if str(item).strip()]
        if normalized:
            return normalized
    return [item for item in (job.action_items or []) if str(item).strip()]


def _get_transcript_entries(job: VideoJob) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for index, segment in enumerate(job.transcript_segments or [], start=1):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = segment.get("start")
        end = segment.get("end")
        if isinstance(start, (int, float)) or isinstance(end, (int, float)):
            label = f"{_format_timestamp(start)} - {_format_timestamp(end)}"
        else:
            label = f"Segment {index}"
        entries.append({"label": label, "text": text})

    if entries:
        return entries

    transcript = (job.transcript or "").strip()
    if not transcript:
        return []
    return [{"label": f"Segment {index}", "text": line.strip()} for index, line in enumerate(transcript.splitlines(), start=1) if line.strip()]


def _format_timestamp(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "--:--"
    total_seconds = max(0, int(value))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _store_report_bytes(job: VideoJob, destination, pdf_bytes: bytes) -> str:
    if is_remote_storage_enabled():
        storage_path = upload_report_bytes(pdf_bytes, job.tenant_id, job.id, destination.logical_path)
    else:
        managed_destination = settings.export_dir / job.tenant_id / job.id / Path(destination.logical_path)
        managed_destination.parent.mkdir(parents=True, exist_ok=True)
        managed_destination.write_bytes(pdf_bytes)
        storage_path = str(managed_destination)

    if destination.local_mirror_path is not None:
        destination.local_mirror_path.parent.mkdir(parents=True, exist_ok=True)
        destination.local_mirror_path.write_bytes(pdf_bytes)

    return storage_path


def _ensure_target(target: str) -> None:
    if target not in REPORT_TARGETS:
        raise ValueError("Unsupported report target")
