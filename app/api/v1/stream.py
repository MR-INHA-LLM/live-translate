"""초벌 WS 라우터 — `WS /api/v1/sessions/{id}/stream`.

연결당 DraftSessionCoordinator 1개(single-flight). 라우터는 파싱·전송만,
순서·취소는 코디네이터, 번역은 서비스 — 책임 분리(backend-architecture.md §8).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.domain import Revision, RevisionUpdate
from app.schemas.common import LatencyInfo
from app.schemas.stream import DraftRequest, DraftResponse
from app.services.coordinator import DraftSessionCoordinator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/sessions/{session_id}/stream")
async def draft_stream(ws: WebSocket, session_id: str) -> None:
    """초벌 스트리밍 WS 연결을 처리한다."""
    await ws.accept()
    container = ws.app.state.container
    session = await container.session_service.get(session_id)
    coordinator = DraftSessionCoordinator(container.draft_service, session)

    async def sink(update: RevisionUpdate) -> None:
        """RevisionUpdate → DraftResponse로 클라이언트에 전송."""
        payload = DraftResponse(
            revision_id=update.revision_id,
            renderings={lang: r.text for lang, r in update.renderings.items()},
            committed_prefix_len={
                lang: r.committed_prefix_len for lang, r in update.renderings.items()
            },
            latency=LatencyInfo(ttft_ms=update.ttft_ms, total_ms=update.total_ms),
        )
        await ws.send_json(payload.model_dump())

    try:
        while True:
            msg = await ws.receive_json()
            req = DraftRequest(**msg)
            rev = Revision(
                id=req.revision_id,
                partial_text=req.partial_text,
                is_final=req.is_final,
            )
            await coordinator.submit(rev, sink)
    except WebSocketDisconnect:
        await coordinator.aclose()
