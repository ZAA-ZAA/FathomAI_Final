from __future__ import annotations

from pydantic import BaseModel, Field


class CustomSummaryRequest(BaseModel):
    transcript: str = Field(min_length=1)
    instruction: str = Field(min_length=5, max_length=2000)
    video_title: str | None = None
    source_language: str | None = None


class CustomSummaryResponse(BaseModel):
    summary: str
