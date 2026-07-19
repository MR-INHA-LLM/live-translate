"""최종 번역(턴) 스키마 (`POST /api/v1/sessions/{id}/turns`, SSE).

최종 턴은 데모 검증 데이터(정렬 스팬 + 단어 신뢰도)를 함께 싣는다. 둘 다 턴당 1회
계산이라 여기 둔다(초벌 핫패스에는 없음).
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import AlignmentSpan, ApiModel, ApiRequest, ConfidenceSpan, LatencyInfo


class TurnRequest(ApiRequest):
    """턴 생성 요청 = 최종 번역 트리거."""

    text: str = Field(min_length=1)
    rerank: bool = False
    context: list[str] = Field(
        default_factory=list,
        description="직전 턴들의 원문 순서열(양측, 오래된→최근). Pombal TACL 2026 컨텍스트.",
    )
    idempotency_key: str | None = Field(None, description="재시도 중복 방지 (decisions.md D12)")


class TurnTokenEvent(ApiModel):
    """SSE `event: token`."""

    delta: str


class TurnDoneEvent(ApiModel):
    """SSE `event: done` — 최종 번역 + 검증 데이터."""

    turn_id: int
    translation: str
    candidates_scored: int = 0
    degraded: bool = False
    latency: LatencyInfo = LatencyInfo()
    alignment: list[AlignmentSpan] = []  # awesome-align, 턴당 1회
    confidence: list[ConfidenceSpan] = []  # token logprob 파생 QE


class TurnErrorEvent(ApiModel):
    """SSE `event: error`."""

    code: str
    degraded_to_draft: bool = False


class TurnRead(ApiModel):
    """턴 이력 조회 항목."""

    turn_id: int
    source: str
    draft: dict[str, str]
    final: str | None = None
    latency: LatencyInfo = LatencyInfo()
