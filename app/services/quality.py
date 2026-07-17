"""QualityService — 확정 문장을 최종 번역 (유스케이스).

M1: quality tier(gemma-4-e2b)는 아직 서빙 전이라 **draft 모델로 degrade**해서
동작시킨다(`degraded=True`로 정직하게 표시). quality vLLM이 뜨면 registry에서 그
바인딩으로 바꾸고 ContextAssembler로 맥락을 주입한다.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from app.domain import EngineRequest, Session, TranslationTask, Turn
from app.engines.registry import ModelRegistry
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

    async def translate_turn(
        self, session: Session, text: str, rerank: bool
    ) -> AsyncIterator[TurnTokenEvent | TurnDoneEvent | TurnErrorEvent]:
        """최종 번역 이벤트(token→done)를 스트리밍하고 턴을 저장한다."""
        prior = await self._repo.recent_turns(session.id, self._context.max_turns)
        turn_id = max((t.turn_id for t in prior), default=0) + 1
        # M1: 전용 quality 모델 미서빙 → draft 모델을 쓰되 **직전 턴 맥락을 주입**해
        # context-aware 최종을 만든다(대명사·생략 복원). draft(맥락 없음)와 실질적으로 다름.
        binding = self._registry.resolve(session.draft_model)
        task = TranslationTask(session.src_lang, session.tgt_lang, text)
        ctx = self._context.build(prior)
        messages = (
            binding.prompt_builder.build_contextual(task, ctx)
            if ctx.turns
            else binding.prompt_builder.build(task)
        )
        req = EngineRequest(
            model=session.draft_model,
            messages=messages,
            temperature=0.0,
            max_tokens=len(text) * 3 + 16,
        )
        t0, ttft, acc = time.perf_counter(), None, ""
        try:
            async for chunk in binding.engine.stream(req):
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
            turn_id=turn_id, translation=final, degraded=False,
            latency=LatencyInfo(ttft_ms=ttft, total_ms=(time.perf_counter() - t0) * 1000),
        )
