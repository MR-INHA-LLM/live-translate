"""언어 라우터 — `/api/v1/languages`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_language_service
from app.schemas.language import LanguageCatalogResponse
from app.services.language import LanguageService

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("", response_model=LanguageCatalogResponse)
async def list_languages(
    svc: LanguageService = Depends(get_language_service),
) -> LanguageCatalogResponse:
    """지원 언어·검증쌍을 반환한다."""
    return svc.catalog()
