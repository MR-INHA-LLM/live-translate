"""공통 스키마 베이스·값 타입.

- `ApiRequest`: 요청 스키마 베이스. 알 수 없는 필드를 거부(오타·오용 조기 차단).
- `ApiModel`: 응답/이벤트 스키마 베이스. 불변(frozen).
전송 관심사(레이턴시·정렬·신뢰도 스팬)를 dict가 아니라 타입으로 고정한다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiRequest(BaseModel):
    """요청 베이스 — strict(알 수 없는 필드 거부)."""

    model_config = ConfigDict(extra="forbid")


class ApiModel(BaseModel):
    """응답/이벤트 베이스 — 불변."""

    model_config = ConfigDict(frozen=True)


class LatencyInfo(ApiModel):
    """tier 응답 지연."""

    ttft_ms: float | None = Field(None, description="첫 토큰까지(ms)")
    total_ms: float | None = Field(None, description="완료까지(ms)")


class AlignmentSpan(ApiModel):
    """소스 구 ↔ 번역 구 대응(문자 오프셋). 정렬 하이라이팅용(decisions.md D13)."""

    src_start: int = Field(ge=0)
    src_end: int = Field(ge=0)
    tgt_start: int = Field(ge=0)
    tgt_end: int = Field(ge=0)


class ConfidenceSpan(ApiModel):
    """번역 단어 구간의 모델 신뢰도(token logprob 파생). QE 색상용.

    `prob`는 구간 토큰 확률의 기하평균, `low`는 임계 미만(amber). 품질이 아니라
    모델 자신의 확신도다.
    """

    tgt_start: int = Field(ge=0)
    tgt_end: int = Field(ge=0)
    prob: float = Field(ge=0.0, le=1.0)
    low: bool = False
