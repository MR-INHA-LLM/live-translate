"""QualityService — 확정 문장을 최종 번역 (유스케이스).

quality tier(Qwen3-4B-Instruct)로 context-aware 최종 번역을 만든다. 컨텍스트는
FE가 전달한 직전 턴 **원문 순서열**(양측)을 쓴다(Pombal et al. TACL 2026). quality
엔진이 도달 불가하면 draft 모델로 **graceful degrade**해 데모가 끊기지 않게 한다.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.domain import EngineRequest, Session, TranslationTask, Turn
from app.engines.registry import EngineBinding, ModelRegistry
from app.errors import UpstreamEngineError
from app.repositories.base import SessionRepository
from app.schemas.common import LatencyInfo
from app.schemas.turn import TurnDoneEvent, TurnErrorEvent, TurnTokenEvent
from app.services.context import ContextAssembler


class QualityService:
    """최종 번역 + graceful degradation 유스케이스."""

    def __init__(
        self, registry: ModelRegistry, repo: SessionRepository, context: ContextAssembler
    ) -> None:
        self._registry = registry
        self._repo = repo
        self._context = context

    def _messages(self, binding: EngineBinding, task: TranslationTask, context: list[str]):
        trimmed = self._context.trim(context)
        if trimmed:
            return binding.prompt_builder.build_contextual(task, trimmed)
        return binding.prompt_builder.build(task)

    async def translate_turn(
        self, session: Session, text: str, rerank: bool, context: list[str] | None = None
    ) -> AsyncIterator[TurnTokenEvent | TurnDoneEvent | TurnErrorEvent]:
        """최종 번역 이벤트(token→done)를 스트리밍하고 턴을 저장한다.

        context: 직전 턴들의 원문 순서열(양측, 오래된→최근). 없으면 단발 번역.
        """
        prior = await self._repo.recent_turns(session.id, self._context.max_turns)
        turn_id = max((t.turn_id for t in prior), default=0) + 1
        task = TranslationTask(session.src_lang, session.tgt_lang, text)
        ctx = context or []

        # quality tier 우선, 도달 불가 시 draft로 degrade.
        model = session.quality_model
        degraded = False
        try:
            binding = self._registry.resolve(model)
        except KeyError:
            binding, model, degraded = self._registry.resolve(session.draft_model), session.draft_model, True

        req = EngineRequest(
            model=model,
            messages=self._messages(binding, task, ctx),
            temperature=0.0,
            max_tokens=len(text) * 3 + 32,
        )
        t0, ttft, acc = time.perf_counter(), None, ""
        try:
            async for chunk in binding.engine.stream(req):
                if ttft is None and chunk.ttft_ms is not None:
                    ttft = chunk.ttft_ms
                acc += chunk.text
                yield TurnTokenEvent(delta=chunk.text)
        except UpstreamEngineError:
            if degraded:  # 이미 draft였는데도 실패 → 진짜 에러
                yield TurnErrorEvent(code="upstream_quality_error", degraded_to_draft=True)
                return
            # quality 실패 → draft로 재시도(degrade)
            draft = self._registry.resolve(session.draft_model)
            req = EngineRequest(
                model=session.draft_model,
                messages=self._messages(draft, task, ctx),
                temperature=0.0,
                max_tokens=len(text) * 3 + 32,
            )
            t0, ttft, acc, degraded = time.perf_counter(), None, "", True
            try:
                async for chunk in draft.engine.stream(req):
                    if ttft is None and chunk.ttft_ms is not None:
                        ttft = chunk.ttft_ms
                    acc += chunk.text
                    yield TurnTokenEvent(delta=chunk.text)
            except UpstreamEngineError:
                yield TurnErrorEvent(code="upstream_quality_error", degraded_to_draft=True)
                return

        final = acc.strip()
        await self._repo.append_turn(
            session.id, Turn(turn_id=turn_id, source=text, draft={session.tgt_lang: final}, final=final)
        )
        yield TurnDoneEvent(
            turn_id=turn_id, translation=final, degraded=degraded,
            latency=LatencyInfo(ttft_ms=ttft, total_ms=(time.perf_counter() - t0) * 1000),
        )
