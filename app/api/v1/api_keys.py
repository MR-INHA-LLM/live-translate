"""API 키 관리(Admin) 라우터 — `/api/v1/api-keys`.

외부 기업 키를 런타임에 발급·조회·폐기한다. 전 엔드포인트는 `X-Admin-Key`(관리자
키)로 보호한다 — 일반 소비자 키(X-API-Key)와 다른 상위 자격이다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_api_key_service, verify_admin_key
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_key import ApiKeyService

router = APIRouter(
    prefix="/api-keys", tags=["api-keys"], dependencies=[Depends(verify_admin_key)]
)


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def issue_api_key(
    body: ApiKeyCreate,
    svc: ApiKeyService = Depends(get_api_key_service),
) -> ApiKeyCreated:
    """외부 키를 발급한다. 평문 키는 이 응답에서만 확인 가능."""
    rec, key = await svc.issue(body.label)
    return ApiKeyCreated(id=rec.id, label=rec.label, prefix=rec.prefix, key=key)


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(
    svc: ApiKeyService = Depends(get_api_key_service),
) -> list[ApiKeyRead]:
    """키 목록(폐기 포함), 최근 생성 순."""
    return [
        ApiKeyRead(
            id=k.id, label=k.label, prefix=k.prefix, enabled=k.enabled,
            created_at=k.created_at, last_used_at=k.last_used_at,
        )
        for k in await svc.list()
    ]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    svc: ApiKeyService = Depends(get_api_key_service),
) -> None:
    """키를 폐기(비활성)한다. 감사를 위해 레코드는 남긴다."""
    if not await svc.revoke(key_id):
        raise HTTPException(status_code=404, detail="api key not found")
