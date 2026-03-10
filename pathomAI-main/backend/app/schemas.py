from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from typing_extensions import Annotated


DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
PasswordText = Annotated[str, StringConstraints(min_length=8, max_length=128)]
WorkspaceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class ApiMessage(BaseModel):
    message: str


class AuthUserRead(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    tenant_id: str
    tenant_name: str


class AuthResponse(BaseModel):
    access_token: str
    user: AuthUserRead


class SignUpRequest(BaseModel):
    full_name: DisplayName
    email: EmailStr
    password: PasswordText
    tenant_name: WorkspaceName


class LoginRequest(BaseModel):
    email: EmailStr
    password: PasswordText


class ProfileUpdateRequest(BaseModel):
    full_name: DisplayName
    email: EmailStr
    tenant_name: WorkspaceName


class PasswordChangeRequest(BaseModel):
    current_password: PasswordText
    new_password: PasswordText


class VideoUploadResponse(BaseModel):
    id: str
    status: str
    message: str


class VideoJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
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
