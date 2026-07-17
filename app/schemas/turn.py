"""최종 번역(턴) 스키마 (`POST /api/v1/sessions/{id}/turns`, SSE)."""

from __future__ import annotations

from pydantic import BaseModel


class TurnRequest(BaseModel):
    """턴 생성 요청 = 최종 번역 트리거."""

    text: str
    rerank: bool = False


class TurnTokenEvent(BaseModel):
    """SSE `event: token`."""

    delta: str


class TurnDoneEvent(BaseModel):
    """SSE `event: done`."""

    turn_id: int
    translation: str
    candidates_scored: int = 0
    degraded: bool = False
    latency_ms: dict[str, float] = {}


class TurnErrorEvent(BaseModel):
    """SSE `event: error`."""

    code: str
    degraded_to_draft: bool = False


class TurnRead(BaseModel):
    """턴 이력 조회 항목."""

    turn_id: int
    source: str
    draft: dict[str, str]
    final: str | None = None
    latency_ms: dict[str, float] = {}
