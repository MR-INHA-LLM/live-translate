"""DraftSessionCoordinator — WS 연결 1개의 초벌 순서·취소 (single-flight).

취소 관심사를 여기 가둬 서비스·엔진을 순수하게 유지한다
(docs/backend-architecture.md §8). 제어 흐름은 확정, 실제 번역은 DraftService.
"""

from __future__ import annotations

import asyncio
import logging

from app.domain import Revision, Session, UpdateSink
from app.services.draft import DraftService

logger = logging.getLogger(__name__)


class DraftSessionCoordinator:
    """연결당 하나. 새 revision이 이전 것을 취소한다."""

    def __init__(self, service: DraftService, session: Session) -> None:
        self._svc = service
        self._session = session
        self._task: asyncio.Task[None] | None = None
        self._latest = -1

    async def submit(self, rev: Revision, sink: UpdateSink) -> None:
        """새 revision을 받는다. stale는 버리고, 진행 중이면 취소한다."""
        if rev.id <= self._latest:  # 순서 역전/중복 → 폐기
            return
        self._latest = rev.id
        if self._task and not self._task.done():
            self._task.cancel()  # 이전 요청 abort → 업스트림 생성 중단
        self._task = asyncio.create_task(self._run(rev, sink))

    async def _run(self, rev: Revision, sink: UpdateSink) -> None:
        """DraftService.render를 흘리되, 도중 더 최신 revision이 오면 폐기."""
        try:
            async for update in self._svc.render(self._session, rev):
                if rev.id != self._latest:
                    return
                await sink(update)
        except asyncio.CancelledError:
            raise  # 정상 취소
        except Exception:  # noqa: BLE001 — 연결을 죽이지 않기 위해 로깅 후 삼킴
            logger.exception("draft render failed (rev=%s)", rev.id)

    async def aclose(self) -> None:
        """연결 종료 시 진행 중 task 취소."""
        if self._task and not self._task.done():
            self._task.cancel()
