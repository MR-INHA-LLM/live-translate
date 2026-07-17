"""턴(최종 번역) 라우터 — `/api/v1/sessions/{id}/turns` (SSE).

턴 생성이 곧 최종 번역 트리거. 응답은 `text/event-stream`(POST라 브라우저
EventSource 대신 FE는 fetch+ReadableStream으로 소비 — frontend-architecture.md §4.3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_quality_service, get_session_service
from app.schemas.turn import TurnRead, TurnRequest
from app.services.quality import QualityService
from app.services.session import SessionService

router = APIRouter(prefix="/sessions/{session_id}/turns", tags=["turns"])


@router.post("")
async def create_turn(
    session_id: str,
    req: TurnRequest,
    sessions: SessionService = Depends(get_session_service),
    quality: QualityService = Depends(get_quality_service),
) -> StreamingResponse:
    """최종 번역을 SSE로 스트리밍한다."""
    await sessions.get(session_id)  # 존재 검증(없으면 SessionNotFoundError → 404)

    async def event_stream():
        # TODO(M1): quality.translate_turn(session, req.text, req.rerank)를 순회하며
        # `event: token`/`event: done`/`event: error`(SSE) 프레임으로 직렬화.
        raise NotImplementedError("M1")
        yield  # pragma: no cover

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("", response_model=list[TurnRead])
async def list_turns(
    session_id: str,
    sessions: SessionService = Depends(get_session_service),
) -> list[TurnRead]:
    """턴 이력을 반환한다. (TODO: M1)"""
    raise NotImplementedError("M1")
