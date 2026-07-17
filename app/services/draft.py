"""DraftService — 타이핑 중 소스를 다중 타겟으로 번역 (유스케이스)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from app.domain import EngineRequest, Rendering, Revision, RevisionUpdate, Session, TranslationTask
from app.engines.registry import ModelRegistry
from app.repositories.cache import RenderingCache, cache_key


class DraftService:
    """초벌 렌더링 유스케이스."""

    def __init__(self, registry: ModelRegistry, cache: RenderingCache) -> None:
        self._registry = registry
        self._cache = cache

    async def render(
        self, session: Session, rev: Revision
    ) -> AsyncIterator[RevisionUpdate]:
        """revision을 tgt + witness로 병렬 번역해 결과를 낸다.

        정규화 → 결정성 캐시(D3) → 미스 시 target_langs로 fan-out(D8).
        """
        norm = rev.partial_text.strip()
        if not norm:
            return
        targets = session.target_langs()
        key = cache_key(session.draft_model, session.src_lang, ",".join(targets), norm)
        if (hit := self._cache.get(key)) is not None:
            yield RevisionUpdate(rev.id, hit, cached=True)
            return

        binding = self._registry.resolve(session.draft_model)
        t0 = time.perf_counter()

        async def one(lang: str) -> tuple[str, Rendering, float | None]:
            task = TranslationTask(session.src_lang, lang, norm)
            req = EngineRequest(
                model=session.draft_model,
                messages=binding.prompt_builder.build(task),
                temperature=0.0,
                max_tokens=len(norm) * 3 + 16,
            )
            text, ttft = "", None
            async for chunk in binding.engine.stream(req):
                text += chunk.text
                if ttft is None and chunk.ttft_ms is not None:
                    ttft = chunk.ttft_ms
            return lang, Rendering(lang=lang, text=text.strip()), ttft

        results = await asyncio.gather(*(one(lang) for lang in targets))
        renderings = {lang: r for lang, r, _ in results}
        ttft = next((t for _, _, t in results if t is not None), None)
        self._cache.put(key, renderings)
        yield RevisionUpdate(
            rev.id, renderings, ttft_ms=ttft, total_ms=(time.perf_counter() - t0) * 1000
        )
