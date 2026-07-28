"""DI 프로바이더 — `app.state.container`에서 서비스를 꺼내 라우터에 주입한다.

전역 상태 대신 요청 스코프의 `request.app.state`를 통해 접근한다.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status

from app.container import Container
from app.services.api_key import ApiKeyService
from app.services.conversation import ConversationService
from app.services.language import LanguageService
from app.services.quality import QualityService
from app.services.session import SessionService


def get_container(request: Request) -> Container:
    """컴포지션 루트에서 만든 컨테이너를 반환한다."""
    return request.app.state.container


def get_api_key_service(request: Request) -> ApiKeyService:
    return get_container(request).api_key_service


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """공개 API 키 검증(DB 기반). 활성 키가 없으면(개발/데모) 통과, 있으면 X-API-Key 요구.

    Raises:
        HTTPException(401): 키 미제공 또는 불일치.
    """
    if not await get_container(request).api_key_service.verify(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"},
        )


def verify_admin_key(
    request: Request,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """Admin API(키 관리) 보호. 관리자 키 미설정이면 비활성(503).

    Raises:
        HTTPException(503): ADMIN_API_KEY 미설정.
        HTTPException(401): 관리자 키 불일치.
    """
    admin: str = getattr(request.app.state, "admin_api_key", "")
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin API disabled (set ADMIN_API_KEY)",
        )
    if not secrets.compare_digest(x_admin_key or "", admin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid admin key",
            headers={"WWW-Authenticate": "Admin-Key"},
        )


def get_session_service(request: Request) -> SessionService:
    return get_container(request).session_service


def get_conversation_service(request: Request) -> ConversationService:
    return get_container(request).conversation_service


def get_quality_service(request: Request) -> QualityService:
    return get_container(request).quality_service


def get_language_service(request: Request) -> LanguageService:
    return get_container(request).language_service
