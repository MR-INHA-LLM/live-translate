"""무상태 번역 라우터 — `POST /api/v1/translations` (공개 RESTful API).

세션 없이 한 번의 번역을 수행한다. `verify=true`면 품질 확인 데이터(초벌·역번역·
신뢰도·정렬·확인)를 함께 반환한다. API 키 인증은 라우터 include에서 적용(main).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.container import Container
from app.schemas.translation import TranslateRequest, TranslationResult

router = APIRouter(prefix="/translations", tags=["translations"])


@router.post("", response_model=TranslationResult, status_code=201)
async def create_translation(
    req: TranslateRequest,
    container: Container = Depends(get_container),
) -> TranslationResult:
    """텍스트를 번역한다(무상태). context로 문맥, verify로 검증 데이터 포함."""
    return await container.translation_service.translate(req)
