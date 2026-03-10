from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.transcript_analysis import (
    TranscriptAnalysisRequest,
    TranscriptAnalysisResponse,
)
from app.services.transcript_analysis import TranscriptAnalysisService

router = APIRouter(tags=["internal-analysis"])


@router.post("/internal/transcript-analysis", response_model=TranscriptAnalysisResponse)
def analyze_transcript(request: TranscriptAnalysisRequest) -> TranscriptAnalysisResponse:
    try:
        service = TranscriptAnalysisService()
        return service.analyze(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
