"""OpenAI 호환 vLLM 엔진 어댑터 (TranslationEngine 구현).

모델은 vLLM의 OpenAI 호환 서버로 뜨고, 이 어댑터는 그 API의 클라이언트다.
공식 `openai` async SDK(AsyncOpenAI)를 vLLM base_url에 물려 `/chat/completions`
스트림을 소비하고, 도메인 `TokenChunk`로 변환한다. 실패는 `UpstreamEngineError`로 감싼다.
게이트웨이는 모델을 직접 로드하지 않는다.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.domain import EngineHealth, EngineRequest, Tier, TokenChunk


class VllmEngine:
    """tier별 vLLM(OpenAI 호환) 인스턴스에 붙는 어댑터."""

    def __init__(
        self, base_url: str, tier: Tier, max_concurrency: int = 8, api_key: str = "EMPTY"
    ) -> None:
        """
        Args:
            base_url: vLLM OpenAI 호환 베이스 URL (예: http://127.0.0.1:8001/v1).
            tier: 이 엔진의 tier.
            max_concurrency: 백프레셔 — 동시 요청 상한(decisions.md D12). stream()이
                이 세마포어를 획득한 뒤 호출한다.
            api_key: vLLM은 키 검증을 안 하므로 placeholder.
        """
        self._tier = tier
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self._sem = asyncio.Semaphore(max_concurrency)

    async def stream(self, req: EngineRequest) -> AsyncIterator[TokenChunk]:
        """`chat.completions.create(stream=True)`를 TokenChunk로 변환한다. (TODO: M1)

        취소(스트림 close) 시 클라이언트 연결이 끊겨 vLLM 생성이 abort된다.
        """
        raise NotImplementedError("M1")
        yield  # pragma: no cover — async generator 표식

    async def health(self) -> EngineHealth:
        """`models.list()` 도달성으로 헬스를 판정한다. (TODO: M1)"""
        raise NotImplementedError("M1")

    async def aclose(self) -> None:
        """OpenAI 클라이언트를 닫는다."""
        await self._client.close()
