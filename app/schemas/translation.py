"""무상태 번역 API 스키마 (`POST /api/v1/translations`).

외부 공개용 RESTful 표면 — 세션 없이 한 번의 번역을 수행하고, `verify=true`면 품질을
확인할 수 있는 검증 데이터(초벌·역번역·신뢰도·정렬·확인)를 함께 반환한다.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import AlignmentSpan, ApiModel, ApiRequest, ConfidenceSpan, LatencyInfo

LangCode = str


class TranslateRequest(ApiRequest):
    """번역 요청. 무상태 — 필요한 맥락은 `context`로 직접 전달."""

    text: str = Field(min_length=1, description="번역할 원문")
    src_lang: LangCode = Field(min_length=2, max_length=8)
    tgt_lang: LangCode = Field(min_length=2, max_length=8)
    context: list[str] = Field(
        default_factory=list, description="직전 대화 원문열(문맥 번역, 오래된→최근)"
    )
    witness_langs: list[LangCode] = Field(
        default_factory=list, description="확인용 제3 언어(verify=true일 때 함께 렌더)"
    )
    verify: bool = Field(False, description="검증 데이터(초벌·역번역·신뢰도·정렬·확인) 포함")


class WitnessOut(ApiModel):
    """확인용 제3 언어 렌더."""

    lang: str
    text: str


class Verification(ApiModel):
    """번역 품질 확인 데이터 (verify=true일 때)."""

    draft: str | None = None  # 초벌(빠른 tier) 번역
    round_trip: str | None = None  # 역번역(tgt→src)
    confidence: list[ConfidenceSpan] = []  # 단어 신뢰도(QE)
    alignment: list[AlignmentSpan] = []  # 구 정렬
    witness: list[WitnessOut] = []  # 확인용 언어


class TranslationResult(ApiModel):
    """번역 응답."""

    translation: str  # 최종 번역
    degraded: bool = False  # quality 미가용 → draft로 대체
    latency: LatencyInfo = LatencyInfo()
    verification: Verification | None = None
