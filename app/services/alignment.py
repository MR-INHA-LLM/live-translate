"""정렬 클라이언트 포트 + HTTP 구현.

정렬 서비스(별도 프로세스 :8003, awesome-align)를 호출한다. 도달 불가/타임아웃 시
빈 목록으로 **graceful degrade**한다 — 정렬은 보조 시각 장치라 없어도 번역은 성립.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.schemas.common import AlignmentSpan

logger = logging.getLogger(__name__)


class AlignerPort(Protocol):
    """소스·번역 → 구 정렬 스팬."""

    async def align(self, source: str, translation: str) -> list[AlignmentSpan]:
        """정렬 스팬을 반환한다. 실패 시 빈 목록."""
        ...


class HttpAligner:
    """정렬 서비스(:8003)의 HTTP 클라이언트."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self._url = base_url.rstrip("/") + "/align"
        self._client = httpx.AsyncClient(timeout=timeout)

    async def align(self, source: str, translation: str) -> list[AlignmentSpan]:
        try:
            r = await self._client.post(
                self._url, json={"source": source, "translation": translation}
            )
            r.raise_for_status()
            return [AlignmentSpan(**s) for s in r.json().get("spans", [])]
        except (httpx.HTTPError, ValueError) as e:
            logger.debug("alignment unavailable: %s", e)
            return []

    async def aclose(self) -> None:
        await self._client.aclose()
