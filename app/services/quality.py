"""QualityService — 확정 문장을 대화 맥락 기반으로 최종 번역 (유스케이스)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.domain import Session, TokenChunk
from app.engines.registry import ModelRegistry
from app.repositories.base import SessionRepository
from app.services.context import ContextAssembler


class QualityService:
    """최종 번역 + graceful degradation 유스케이스."""

    def __init__(
        self,
        registry: ModelRegistry,
        repo: SessionRepository,
        context: ContextAssembler,
    ) -> None:
        self._registry = registry
        self._repo = repo
        self._context = context

    async def translate_turn(
        self, session: Session, text: str, rerank: bool
    ) -> AsyncIterator[TokenChunk]:
        """최종 번역 토큰을 스트리밍한다.

        흐름(TODO: M1): 직전 N턴 컨텍스트 조립(ContextAssembler) → quality 엔진
        스트리밍. `UpstreamEngineError`를 잡아 draft 결과로 승격(degradation),
        `degraded=True` 전달. 완료 후 Turn 저장.
        """
        raise NotImplementedError("M1")
        yield  # pragma: no cover
