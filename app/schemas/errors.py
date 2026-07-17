"""에러 응답 스키마 (fastapi-standards §3.2)."""

from __future__ import annotations

from app.schemas.common import ApiModel


class ErrorResponse(ApiModel):
    """일관된 에러 응답 형식."""

    detail: str
    error_code: str | None = None
