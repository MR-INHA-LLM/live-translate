"""API 키 관리(Admin) 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, ApiRequest


class ApiKeyCreate(ApiRequest):
    """키 발급 요청."""

    label: str = Field(min_length=1, max_length=120, description="소유자/용도 라벨(예: 회사명)")


class ApiKeyRead(ApiModel):
    """키 공개 메타(평문 키는 포함하지 않음)."""

    id: str
    label: str
    prefix: str = Field(description="식별용 앞부분(예: lt_ext_9fK2…)")
    enabled: bool
    created_at: datetime
    last_used_at: datetime | None = None


class ApiKeyCreated(ApiModel):
    """발급 응답 — 평문 키는 이 응답에서만 확인 가능(서버는 해시만 저장)."""

    id: str
    label: str
    prefix: str
    key: str = Field(description="발급된 평문 키. 지금만 노출되니 안전히 전달할 것.")
