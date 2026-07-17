"""OpenAI 호환 vLLM 엔진 어댑터 (TranslationEngine 구현).

모델은 vLLM의 OpenAI 호환 서버로 뜨고, 이 어댑터는 그 API의 클라이언트다.
공식 `openai` async SDK로 `/chat/completions` 스트림을 소비해 도메인 `TokenChunk`
(logprob 포함)로 변환한다. 실패는 `UpstreamEngineError`로 감싼다.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from openai import APIError, AsyncOpenAI

from app.domain import EngineHealth, EngineRequest, Tier, TokenChunk
from app.errors import UpstreamEngineError


class VllmEngine:
    """tier별 vLLM(OpenAI 호환) 인스턴스에 붙는 어댑터."""

    def __init__(
        self, base_url: str, tier: Tier, max_concurrency: int = 8, api_key: str = "EMPTY"
    ) -> None:
        self._tier = tier
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._sem = asyncio.Semaphore(max_concurrency)

    async def stream(self, req: EngineRequest) -> AsyncIterator[TokenChunk]:
        """토큰을 스트리밍한다. 첫 청크만 ttft_ms, 각 청크에 logprob."""
        async with self._sem:
            t0 = time.perf_counter()
            first = True
            try:
                stream = await self._client.chat.completions.create(
                    model=req.model,
                    messages=[{"role": m.role, "content": m.content} for m in req.messages],
                    temperature=req.temperature,
                    max_tokens=req.max_tokens,
                    stream=True,
                    logprobs=True,
                    top_logprobs=1,
                )
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    ch = chunk.choices[0]
                    delta = ch.delta.content
                    if not delta:
                        continue
                    lp = None
                    if ch.logprobs and ch.logprobs.content:
                        lp = ch.logprobs.content[0].logprob
                    ttft = (time.perf_counter() - t0) * 1000 if first else None
                    first = False
                    yield TokenChunk(text=delta, logprob=lp, ttft_ms=ttft)
            except APIError as e:
                raise UpstreamEngineError(f"{self._tier.value} engine: {e}") from e

    async def health(self) -> EngineHealth:
        """`models.list()` 도달성으로 헬스를 판정한다."""
        try:
            models = await self._client.models.list()
            loaded = models.data[0].id if models.data else None
            return EngineHealth(tier=self._tier, reachable=True, loaded_model=loaded)
        except APIError:
            return EngineHealth(tier=self._tier, reachable=False)

    async def aclose(self) -> None:
        await self._client.close()
