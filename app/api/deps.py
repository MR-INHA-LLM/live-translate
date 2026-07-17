"""DI 프로바이더 — `app.state.container`에서 서비스를 꺼내 라우터에 주입한다.

전역 상태 대신 요청 스코프의 `request.app.state`를 통해 접근한다.
"""

from __future__ import annotations

from fastapi import Request

from app.container import Container
from app.services.language import LanguageService
from app.services.quality import QualityService
from app.services.session import SessionService


def get_container(request: Request) -> Container:
    """컴포지션 루트에서 만든 컨테이너를 반환한다."""
    return request.app.state.container


def get_session_service(request: Request) -> SessionService:
    return get_container(request).session_service


def get_quality_service(request: Request) -> QualityService:
    return get_container(request).quality_service


def get_language_service(request: Request) -> LanguageService:
    return get_container(request).language_service
