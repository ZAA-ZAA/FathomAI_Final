from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.custom_summary import CustomSummaryRequest, CustomSummaryResponse
from app.services.custom_summary import CustomSummaryService

router = APIRouter(tags=["internal-custom-summary"])


@router.post("/internal/custom-summary", response_model=CustomSummaryResponse)
def generate_custom_summary(request: CustomSummaryRequest) -> CustomSummaryResponse:
    try:
        service = CustomSummaryService()
        return service.generate(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
