"""TranslationService — 무상태 번역 + 검증 (공개 API 유스케이스).

세션/DB 없이 한 번의 번역을 수행한다. quality tier로 최종을 만들고(도달 불가 시 draft
degrade), `verify=True`면 초벌·역번역·신뢰도(QE)·정렬·확인(witness)을 함께 계산한다.
스트리밍(SSE)과 단발(JSON) 둘 다 지원한다.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.domain import EngineRequest, TranslationTask
from app.engines.registry import EngineBinding, ModelRegistry
from app.errors import UpstreamEngineError
from app.schemas.common import LatencyInfo
from app.schemas.translation import TranslateRequest, TranslationResult, Verification, WitnessOut
from app.services.alignment import AlignerPort
from app.services.context import ContextAssembler
from app.services.quality_estimation import build_confidence_spans


@dataclass
class _Acc:
    text: str = ""
    ttft: float | None = None
    tokens: list[tuple[int, int, float | None]] = field(default_factory=list)


class TranslationService:
    """무상태 번역 + 검증."""

    def __init__(
        self,
        registry: ModelRegistry,
        context: ContextAssembler,
        aligner: AlignerPort | None,
        draft_model: str,
        quality_model: str,
    ) -> None:
        self._registry = registry
        self._context = context
        self._aligner = aligner
        self._draft_model = draft_model
        self._quality_model = quality_model

    def _messages(self, binding: EngineBinding, task: TranslationTask, context: list[str]):
        trimmed = self._context.trim(context)
        if trimmed:
            return binding.prompt_builder.build_contextual(task, trimmed)
        return binding.prompt_builder.build(task)

    async def _stream(self, binding: EngineBinding, req: EngineRequest, acc: _Acc) -> AsyncIterator[str]:
        async for chunk in binding.engine.stream(req):
            if acc.ttft is None and chunk.ttft_ms is not None:
                acc.ttft = chunk.ttft_ms
            start = len(acc.text)
            acc.text += chunk.text
            acc.tokens.append((start, len(acc.text), chunk.logprob))
            yield chunk.text

    async def _simple(self, src: str, tgt: str, text: str) -> str:
        """draft 모델로 단발 번역(초벌·역번역·확인용). 실패 시 빈 문자열."""
        try:
            binding = self._registry.resolve(self._draft_model)
        except KeyError:
            return ""
        task = TranslationTask(src, tgt, text)
        req = EngineRequest(
            model=self._draft_model, messages=binding.prompt_builder.build(task),
            temperature=0.0, max_tokens=len(text) * 3 + 32,
        )
        acc = _Acc()
        try:
            async for _ in self._stream(binding, req, acc):
                pass
        except UpstreamEngineError:
            return ""
        return acc.text.strip()

    def _resolve(self, req: TranslateRequest) -> tuple[EngineBinding, str, bool]:
        try:
            return self._registry.resolve(self._quality_model), self._quality_model, False
        except KeyError:
            return self._registry.resolve(self._draft_model), self._draft_model, True

    async def _run_final(self, req: TranslateRequest, acc: _Acc) -> tuple[str, bool]:
        """최종 번역 스트림을 acc에 채운다(quality→draft degrade). 사용된 모델·degraded 반환."""
        binding, model, degraded = self._resolve(req)
        task = TranslationTask(req.src_lang, req.tgt_lang, req.text)
        ereq = EngineRequest(
            model=model, messages=self._messages(binding, task, req.context),
            temperature=0.0, max_tokens=len(req.text) * 3 + 32,
        )
        try:
            async for _ in self._stream(binding, ereq, acc):
                pass
            return model, degraded
        except UpstreamEngineError:
            if degraded:
                raise
            draft = self._registry.resolve(self._draft_model)
            acc.text, acc.ttft, acc.tokens = "", None, []
            dreq = EngineRequest(
                model=self._draft_model, messages=self._messages(draft, task, req.context),
                temperature=0.0, max_tokens=len(req.text) * 3 + 32,
            )
            async for _ in self._stream(draft, dreq, acc):
                pass
            return self._draft_model, True

    def _finalize(self, acc: _Acc):
        lead = len(acc.text) - len(acc.text.lstrip())
        final = acc.text.strip()
        tokens = [(max(0, s - lead), max(0, e - lead), lp) for s, e, lp in acc.tokens]
        return final, build_confidence_spans(tokens, final)

    async def _verify(self, req: TranslateRequest, final, confidence) -> Verification:
        draft = await self._simple(req.src_lang, req.tgt_lang, req.text)
        round_trip = await self._simple(req.tgt_lang, req.src_lang, final)
        alignment = await self._aligner.align(req.text, final) if self._aligner else []
        witness = [
            WitnessOut(lang=w, text=await self._simple(req.src_lang, w, req.text))
            for w in dict.fromkeys(req.witness_langs)
            if w not in (req.src_lang, req.tgt_lang)
        ]
        return Verification(
            draft=draft or None, round_trip=round_trip or None,
            confidence=confidence, alignment=alignment, witness=witness,
        )

    async def translate(self, req: TranslateRequest) -> TranslationResult:
        """단발(JSON) 번역 + 선택적 검증."""
        acc = _Acc()
        t0 = time.perf_counter()
        _, degraded = await self._run_final(req, acc)
        llm_ms = (time.perf_counter() - t0) * 1000
        final, confidence = self._finalize(acc)
        verification = await self._verify(req, final, confidence) if req.verify else None
        return TranslationResult(
            translation=final, degraded=degraded,
            latency=LatencyInfo(ttft_ms=acc.ttft, total_ms=llm_ms),
            verification=verification,
        )
