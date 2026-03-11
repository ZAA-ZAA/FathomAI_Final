from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float | None = None
    end: float | None = None
    text: str = Field(min_length=1)


class TranscriptChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class TranscriptChatRequest(BaseModel):
    transcript: str = Field(min_length=1)
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    question: str = Field(min_length=1)
    chat_history: list[TranscriptChatMessage] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    video_title: str | None = None
    source_language: str | None = None
    summary: str | None = None
    sentiment: str | None = None
    action_items: list[str] = Field(default_factory=list)


class TranscriptChatResponse(BaseModel):
    answer: str
    suggested_questions: list[str] = Field(default_factory=list)


class TranscriptSuggestionRequest(BaseModel):
    transcript: str = Field(min_length=1)
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)
    video_title: str | None = None
    source_language: str | None = None
    summary: str | None = None
    sentiment: str | None = None
    action_items: list[str] = Field(default_factory=list)


class TranscriptSuggestionResponse(BaseModel):
    suggested_questions: list[str] = Field(default_factory=list)
