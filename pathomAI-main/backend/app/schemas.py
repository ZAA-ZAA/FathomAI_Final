from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VideoUploadResponse(BaseModel):
    id: str
    status: str
    message: str


class VideoJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    content_type: str | None
    file_size_bytes: int
    duration_seconds: float | None
    language_hint: str
    detected_language: str | None
    status: str
    summary: str | None
    sentiment: str | None
    action_items: list[str] = Field(default_factory=list)
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class VideoJobRead(VideoJobSummary):
    transcript: str | None = None
    video_metadata: dict = Field(default_factory=dict)


class AgentAnalysisResult(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)
    sentiment: str


class TranscriptionResult(BaseModel):
    transcript: str
    detected_language: str | None = None
