"""엔진 포트 (Protocol). 서비스는 이 인터페이스에만 의존한다(DIP)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.domain import EngineHealth, EngineRequest, TokenChunk


class TranslationEngine(Protocol):
    """번역 엔진 추상 — 스트리밍 생성 + 헬스.

    구현체는 취소 시 스트림 close가 업스트림 생성을 abort하도록 만든다
    (docs/backend-architecture.md §5).
    """

    def stream(self, req: EngineRequest) -> AsyncIterator[TokenChunk]:
        """토큰을 스트리밍한다. 첫 청크만 ttft_ms를 담는다."""
        ...

    async def health(self) -> EngineHealth:
        """엔진 도달성·로드 상태를 반환한다."""
        ...
