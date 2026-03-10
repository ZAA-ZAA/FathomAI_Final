from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptAnalysisRequest(BaseModel):
    transcript: str = Field(min_length=1)
    video_title: str | None = None
    source_language: str | None = None


class TranscriptAnalysisResponse(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)
    sentiment: str
