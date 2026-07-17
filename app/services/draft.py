"""DraftService — 타이핑 중 소스를 다중 타겟으로 번역 (유스케이스)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.domain import Revision, RevisionUpdate, Session
from app.engines.registry import ModelRegistry
from app.repositories.cache import RenderingCache


class DraftService:
    """초벌 렌더링 유스케이스."""

    def __init__(self, registry: ModelRegistry, cache: RenderingCache) -> None:
        self._registry = registry
        self._cache = cache

    async def render(
        self, session: Session, rev: Revision
    ) -> AsyncIterator[RevisionUpdate]:
        """revision을 tgt + witness로 병렬 번역해 스트리밍한다.

        흐름(TODO: M1): 소스 정규화(IME 잔여 제거) → 결정성 캐시 조회(D3) →
        미스 시 `session.target_langs()`로 fan-out(asyncio.gather, D8) →
        타겟별 스트림 병합 → RevisionUpdate yield.
        """
        raise NotImplementedError("M1")
        yield  # pragma: no cover — async generator 표식
