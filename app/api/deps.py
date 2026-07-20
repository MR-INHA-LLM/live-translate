"""DI 프로바이더 — `app.state.container`에서 서비스를 꺼내 라우터에 주입한다.

전역 상태 대신 요청 스코프의 `request.app.state`를 통해 접근한다.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.container import Container
from app.services.conversation import ConversationService
from app.services.language import LanguageService
from app.services.quality import QualityService
from app.services.session import SessionService


def get_container(request: Request) -> Container:
    """컴포지션 루트에서 만든 컨테이너를 반환한다."""
    return request.app.state.container


def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """공개 API 키 검증. 설정된 키가 없으면(개발/데모) 통과, 있으면 X-API-Key 요구.

    Raises:
        HTTPException(401): 키 미제공 또는 불일치.
    """
    keys: set[str] = getattr(request.app.state, "api_keys", set())
    if not keys:
        return
    if x_api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"},
        )


def get_session_service(request: Request) -> SessionService:
    return get_container(request).session_service


def get_conversation_service(request: Request) -> ConversationService:
    return get_container(request).conversation_service


def get_quality_service(request: Request) -> QualityService:
    return get_container(request).quality_service


def get_language_service(request: Request) -> LanguageService:
    return get_container(request).language_service
