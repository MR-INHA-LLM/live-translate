"""지원 언어·검증쌍 스키마 (`GET /api/v1/languages`)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel


class LanguageInfo(ApiModel):
    """지원 언어 하나."""

    code: str  # "ko"
    name_en: str  # "Korean"
    name_native: str  # "한국어"
    is_dialect: bool = False


class LanguagePair(ApiModel):
    """검증된 언어쌍 + COMET(측정된 쌍만)."""

    src: str
    tgt: str
    comet: float | None = Field(None, ge=0.0, le=100.0)


class LanguageCatalogResponse(ApiModel):
    """언어 목록 + 검증쌍 + 기본 witness."""

    languages: list[LanguageInfo]
    validated_pairs: list[LanguagePair]
    default_witness: str = "en"
