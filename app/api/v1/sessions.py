"""세션 라우터 — `/api/v1/sessions`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_session_service
from app.schemas.session import SessionConfig, SessionCreated, SessionRead
from app.services.session import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreated, status_code=201)
async def create_session(
    config: SessionConfig,
    svc: SessionService = Depends(get_session_service),
) -> SessionCreated:
    """세션을 생성한다."""
    session = await svc.create(config)
    return SessionCreated(session_id=session.id)


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    svc: SessionService = Depends(get_session_service),
) -> SessionRead:
    """세션을 조회한다."""
    await svc.get(session_id)  # 존재 검증(없으면 404)
    # TODO(M1): 도메인 Session → SessionRead(config) 매핑.
    raise NotImplementedError("M1")
