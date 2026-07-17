"""세션 관련 요청/응답 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiModel, ApiRequest

# 언어 코드: 2~8자(iso 계열 + 방언 접미), 소문자·숫자·언더스코어.
LangCode = str


class RerankConfig(ApiRequest):
    """QAD 리랭킹 설정 (M4)."""

    enabled: bool = False
    n_candidates: int = Field(4, ge=2, le=8, description="생성·스코어링할 후보 수")
    metric: Literal["cometkiwi"] = "cometkiwi"


class StabilityConfig(ApiRequest):
    """초벌 안정화 설정."""

    debounce_ms: int = Field(200, ge=0, le=1000, description="발사 전 대기(ms)")
    commit_prefix: bool = False  # 어순 유사 쌍에서만 (decisions.md D3)


class SessionConfig(ApiRequest):
    """세션 생성 요청 본문.

    언어는 양방향 선택(UI ⇄ 스왑). 기본 쌍 ko⇄en. witness는 target을 못 읽는
    조합(예: id)에서 확인용으로 병렬 렌더된다(decisions.md D8).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "src_lang": "ko",
                "tgt_lang": "id",
                "witness_langs": ["en"],
                "domain": "customer_support",
                "formality": "polite",
            }
        },
    )

    src_lang: LangCode = Field("ko", min_length=2, max_length=8)
    tgt_lang: LangCode = Field("en", min_length=2, max_length=8)
    witness_langs: list[LangCode] = Field(default_factory=lambda: ["en"])
    domain: str = "general"
    formality: Literal["polite", "casual", "neutral"] = "neutral"
    draft_model: str = "hy-mt1.5-1.8b"
    quality_model: str = "gemma-4-e2b"
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    stability: StabilityConfig = Field(default_factory=StabilityConfig)

    @model_validator(mode="after")
    def _validate_langs(self) -> SessionConfig:
        """tgt≠src 강제, witness에서 src/tgt·중복 제거."""
        if self.tgt_lang == self.src_lang:
            raise ValueError("tgt_lang must differ from src_lang")
        exclude = {self.src_lang, self.tgt_lang}
        self.witness_langs = [w for w in dict.fromkeys(self.witness_langs) if w not in exclude]
        return self


class SessionCreated(ApiModel):
    """세션 생성 응답."""

    session_id: str


class SessionRead(ApiModel):
    """세션 조회 응답."""

    session_id: str
    config: SessionConfig
