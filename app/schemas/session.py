"""세션 관련 요청/응답 스키마."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RerankConfig(BaseModel):
    """QAD 리랭킹 설정 (M4)."""

    enabled: bool = False
    n_candidates: int = Field(4, ge=2, le=8)
    metric: Literal["cometkiwi"] = "cometkiwi"


class StabilityConfig(BaseModel):
    """초벌 안정화 설정."""

    debounce_ms: int = Field(200, ge=0, le=1000)
    commit_prefix: bool = False  # 어순 유사 쌍에서만 (decisions.md D3)


class SessionConfig(BaseModel):
    """세션 생성 요청 본문.

    언어는 양방향 선택(UI ⇄ 스왑). 기본 쌍 ko⇄en. witness는 target을 못 읽는
    조합(예: id)에서 확인용으로 병렬 렌더된다(decisions.md D8).
    """

    src_lang: str = "ko"
    tgt_lang: str = "en"
    witness_langs: list[str] = ["en"]
    domain: str = "general"
    formality: Literal["polite", "casual", "neutral"] = "neutral"
    draft_model: str = "hy-mt1.5-1.8b"
    quality_model: str = "gemma-4-e2b"
    rerank: RerankConfig = RerankConfig()
    stability: StabilityConfig = StabilityConfig()


class SessionCreated(BaseModel):
    """세션 생성 응답."""

    session_id: str


class SessionRead(BaseModel):
    """세션 조회 응답."""

    session_id: str
    config: SessionConfig
