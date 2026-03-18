from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, StringConstraints, model_validator
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


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key_preview: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreateRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class ApiKeyCreateResponse(BaseModel):
    api_key: str
    api_key_record: ApiKeyRead


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
    notify_email: EmailStr | None = None
    export_pdf: bool = False
    export_pdf_path: str | None = None


class VideoUrlUploadRequest(BaseModel):
    video_url: HttpUrl
    language_hint: str = "auto"
    notify_email: EmailStr | None = None
    export_pdf: bool = False
    export_pdf_path: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=500)] = None

    @model_validator(mode="after")
    def validate_pdf_options(self):
        if self.export_pdf_path and not self.export_pdf:
            raise ValueError("export_pdf must be true when export_pdf_path is provided")
        return self


class VideoJobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    source_type: str
    source_url: str | None
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
    transcript_segments: list[dict] = Field(default_factory=list)
    custom_summary_prompt: str | None = None
    custom_summary_text: str | None = None
    custom_summary_updated_at: datetime | None = None
    video_metadata: dict = Field(default_factory=dict)


class AgentAnalysisResult(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)
    sentiment: str


class AgentCustomSummaryResult(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)


class ChatMessageInput(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class VideoChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    chat_history: list[ChatMessageInput] = Field(default_factory=list)
    asked_questions: list[str] = Field(default_factory=list)


class VideoChatResponse(BaseModel):
    answer: str
    suggested_questions: list[str] = Field(default_factory=list)


class VideoChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class VideoChatSuggestionRequest(BaseModel):
    asked_questions: list[str] = Field(default_factory=list)


class VideoChatSuggestionResponse(BaseModel):
    suggested_questions: list[str] = Field(default_factory=list)


class CustomSummaryRequest(BaseModel):
    instruction: str = Field(min_length=5, max_length=2000)


class CustomSummaryResponse(BaseModel):
    summary: str
    action_items: list[str] = Field(default_factory=list)
    instruction: str
    updated_at: datetime


class VideoReportRequest(BaseModel):
    export_pdf_path: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=500)] = None
    show_timestamps: bool = True
    use_custom_summary: bool | None = None


class VideoReportEmailRequest(VideoReportRequest):
    recipient_email: EmailStr


class VideoReportResponse(BaseModel):
    target: str
    message: str
    saved_path: str | None = None
    storage_path: str | None = None
    filename: str | None = None
    email_status: str | None = None
    emailed_to: EmailStr | None = None
    generated_at: datetime | None = None


class TranscriptionResult(BaseModel):
    transcript: str
    detected_language: str | None = None
    transcript_segments: list[dict] = Field(default_factory=list)
