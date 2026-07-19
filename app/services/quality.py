"""QualityService — 확정 문장을 최종 번역 + 검증 데이터 (유스케이스).

quality tier(Qwen3-4B)로 context-aware 최종 번역을 만들고, 턴당 1회 검증 데이터를
함께 싣는다:
- **QE(단어 신뢰도)**: 최종 스트림의 토큰 logprob → 단어 단위 신뢰도 스팬.
- **역번역(round-trip)**: 최종을 draft 엔진으로 원문 언어로 되돌려(tgt→src) 대조.

컨텍스트는 FE가 전달한 직전 턴 **원문 순서열**(Pombal TACL 2026). quality 엔진이
도달 불가하면 draft로 graceful degrade한다.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.domain import EngineRequest, Session, TranslationTask, Turn
from app.engines.registry import EngineBinding, ModelRegistry
from app.errors import UpstreamEngineError
from app.repositories.base import SessionRepository
from app.schemas.common import LatencyInfo
from app.schemas.turn import TurnDoneEvent, TurnErrorEvent, TurnTokenEvent
from app.services.alignment import AlignerPort
from app.services.context import ContextAssembler
from app.services.quality_estimation import build_confidence_spans


@dataclass
class _Acc:
    """스트림 누적기 — 텍스트 + ttft + 토큰 (문자시작, 끝, logprob)."""

    text: str = ""
    ttft: float | None = None
    tokens: list[tuple[int, int, float | None]] = field(default_factory=list)


class QualityService:
    """최종 번역 + 검증(QE·역번역) + graceful degradation 유스케이스."""

    def __init__(
        self, registry: ModelRegistry, repo: SessionRepository, context: ContextAssembler,
        aligner: AlignerPort | None = None,
    ) -> None:
        self._registry = registry
        self._repo = repo
        self._context = context
        self._aligner = aligner

    def _messages(self, binding: EngineBinding, task: TranslationTask, context: list[str]):
        trimmed = self._context.trim(context)
        if trimmed:
            return binding.prompt_builder.build_contextual(task, trimmed)
        return binding.prompt_builder.build(task)

    async def _stream(
        self, binding: EngineBinding, req: EngineRequest, acc: _Acc
    ) -> AsyncIterator[TurnTokenEvent]:
        """엔진 토큰을 yield하며 acc에 텍스트·ttft·토큰 스팬을 누적한다."""
        async for chunk in binding.engine.stream(req):
            if acc.ttft is None and chunk.ttft_ms is not None:
                acc.ttft = chunk.ttft_ms
            start = len(acc.text)
            acc.text += chunk.text
            acc.tokens.append((start, len(acc.text), chunk.logprob))
            yield TurnTokenEvent(delta=chunk.text)

    async def _round_trip(self, session: Session, final: str) -> tuple[str | None, float | None]:
        """최종 번역을 draft 엔진으로 원문 언어로 되돌린다(tgt→src). 실패 시 (None, None)."""
        try:
            binding = self._registry.resolve(session.draft_model)
        except KeyError:
            return None, None
        task = TranslationTask(session.tgt_lang, session.src_lang, final)
        req = EngineRequest(
            model=session.draft_model,
            messages=binding.prompt_builder.build(task),
            temperature=0.0,
            max_tokens=len(final) * 3 + 32,
        )
        t0, acc = time.perf_counter(), _Acc()
        try:
            async for _ in self._stream(binding, req, acc):
                pass
        except UpstreamEngineError:
            return None, None
        return acc.text.strip(), (time.perf_counter() - t0) * 1000

    async def translate_turn(
        self, session: Session, text: str, rerank: bool, context: list[str] | None = None
    ) -> AsyncIterator[TurnTokenEvent | TurnDoneEvent | TurnErrorEvent]:
        """최종 번역 이벤트(token→done)를 스트리밍하고 턴을 저장한다.

        done 이벤트에 QE(confidence)·역번역(round_trip)을 함께 싣는다.
        """
        prior = await self._repo.recent_turns(session.id, self._context.max_turns)
        turn_id = max((t.turn_id for t in prior), default=0) + 1
        task = TranslationTask(session.src_lang, session.tgt_lang, text)
        ctx = context or []

        model, degraded = session.quality_model, False
        try:
            binding = self._registry.resolve(model)
        except KeyError:
            binding, model, degraded = self._registry.resolve(session.draft_model), session.draft_model, True

        req = EngineRequest(
            model=model, messages=self._messages(binding, task, ctx),
            temperature=0.0, max_tokens=len(text) * 3 + 32,
        )
        t0, acc = time.perf_counter(), _Acc()
        try:
            async for ev in self._stream(binding, req, acc):
                yield ev
        except UpstreamEngineError:
            if degraded:
                yield TurnErrorEvent(code="upstream_quality_error", degraded_to_draft=True)
                return
            draft = self._registry.resolve(session.draft_model)
            req = EngineRequest(
                model=session.draft_model, messages=self._messages(draft, task, ctx),
                temperature=0.0, max_tokens=len(text) * 3 + 32,
            )
            t0, acc, degraded = time.perf_counter(), _Acc(), True
            try:
                async for ev in self._stream(draft, req, acc):
                    yield ev
            except UpstreamEngineError:
                yield TurnErrorEvent(code="upstream_quality_error", degraded_to_draft=True)
                return

        llm_ms = (time.perf_counter() - t0) * 1000  # 역번역 전에 LLM 소요만 측정

        # 최종 문자열 + 오프셋 정렬(선행 공백 보정) → 단어 신뢰도(QE).
        lead = len(acc.text) - len(acc.text.lstrip())
        final = acc.text.strip()
        tokens = [(max(0, s - lead), max(0, e - lead), lp) for s, e, lp in acc.tokens]
        confidence = build_confidence_spans(tokens, final)

        round_trip, round_trip_ms = await self._round_trip(session, final)
        alignment = await self._aligner.align(text, final) if self._aligner else []

        await self._repo.append_turn(
            session.id, Turn(turn_id=turn_id, source=text, draft={session.tgt_lang: final}, final=final)
        )
        yield TurnDoneEvent(
            turn_id=turn_id, translation=final, degraded=degraded,
            latency=LatencyInfo(ttft_ms=acc.ttft, total_ms=llm_ms),
            confidence=confidence, alignment=alignment,
            round_trip=round_trip, round_trip_ms=round_trip_ms,
        )
