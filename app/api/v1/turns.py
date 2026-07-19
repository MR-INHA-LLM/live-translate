"""턴(최종 번역) 라우터 — `/api/v1/sessions/{id}/turns` (SSE).

턴 생성이 곧 최종 번역 트리거. 응답은 `text/event-stream`(POST라 브라우저
EventSource 대신 FE는 fetch+ReadableStream으로 소비 — frontend-architecture.md §4.3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_quality_service, get_session_service
from app.schemas.turn import TurnDoneEvent, TurnRead, TurnRequest, TurnTokenEvent
from app.services.quality import QualityService
from app.services.session import SessionService

router = APIRouter(prefix="/sessions/{session_id}/turns", tags=["turns"])


def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {data}\n\n"


@router.post("")
async def create_turn(
    session_id: str,
    req: TurnRequest,
    sessions: SessionService = Depends(get_session_service),
    quality: QualityService = Depends(get_quality_service),
) -> StreamingResponse:
    """최종 번역을 SSE로 스트리밍한다."""
    session = await sessions.get(session_id)  # 없으면 SessionNotFoundError → 404

    async def event_stream() -> AsyncIterator[str]:
        async for ev in quality.translate_turn(session, req.text, req.rerank, req.context):
            if isinstance(ev, TurnTokenEvent):
                yield _sse("token", ev.model_dump_json())
            elif isinstance(ev, TurnDoneEvent):
                yield _sse("done", ev.model_dump_json())
            else:
                yield _sse("error", ev.model_dump_json())

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("", response_model=list[TurnRead])
async def list_turns(
    session_id: str,
    sessions: SessionService = Depends(get_session_service),
) -> list[TurnRead]:
    """턴 이력을 반환한다."""
    await sessions.get(session_id)  # 존재 검증
    # M1: 이력은 quality 저장 경로에서 채워짐. 별도 조회 서비스는 후속.
    return []
