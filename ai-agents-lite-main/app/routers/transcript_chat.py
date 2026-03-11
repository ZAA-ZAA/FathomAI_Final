from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.transcript_chat import (
    TranscriptChatRequest,
    TranscriptChatResponse,
    TranscriptSuggestionRequest,
    TranscriptSuggestionResponse,
)
from app.services.transcript_chat import TranscriptChatService

router = APIRouter(tags=["internal-chat"])


@router.post("/internal/transcript-chat", response_model=TranscriptChatResponse)
def chat_with_transcript(request: TranscriptChatRequest) -> TranscriptChatResponse:
    try:
        service = TranscriptChatService()
        return service.answer_question(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/internal/transcript-chat/suggestions", response_model=TranscriptSuggestionResponse)
def suggest_transcript_questions(request: TranscriptSuggestionRequest) -> TranscriptSuggestionResponse:
    try:
        service = TranscriptChatService()
        return service.suggest_questions(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
