"""대화 저장소 요청/응답 스키마 (`/api/v1/conversations`).

번역 파이프라인 세션과 분리된, UI가 보여준 대화 이력의 저장·복원용
(decisions.md D14). 메시지는 UI가 렌더한 최종 형태 그대로 담는다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, ApiRequest

LangCode = str


class ConversationCreate(ApiRequest):
    """대화 생성 요청."""

    src_lang: LangCode = Field(min_length=2, max_length=8)
    tgt_lang: LangCode = Field(min_length=2, max_length=8)
    witness_lang: LangCode | None = Field(None, min_length=2, max_length=8)


class MessageCreate(ApiRequest):
    """대화에 메시지 추가 요청 (UI가 확정한 메시지)."""

    side: Literal["mine", "theirs"]
    source: str = Field(min_length=1)
    translation: str = Field(min_length=1)
    witness: str | None = None


class MessageRead(ApiModel):
    """대화 메시지 응답."""

    seq: int
    side: Literal["mine", "theirs"]
    source: str
    translation: str
    witness: str | None = None


class ConversationCreated(ApiModel):
    """대화 생성 응답."""

    conversation_id: str


class ConversationSummaryRead(ApiModel):
    """대화 목록 항목."""

    conversation_id: str
    src_lang: str
    tgt_lang: str
    witness_lang: str | None = None
    title: str | None = None
    message_count: int
    updated_at: datetime


class ConversationDetailRead(ApiModel):
    """대화 상세(메시지 포함) — 복원용."""

    conversation_id: str
    src_lang: str
    tgt_lang: str
    witness_lang: str | None = None
    messages: list[MessageRead]
