"""LanguageService — 지원 언어·검증쌍 카탈로그.

카탈로그 소스는 draft 모델 카드의 언어 태그. 검증쌍 COMET은 M0 실측(RESULTS_M0).
"""

from __future__ import annotations

from app.schemas.language import LanguageCatalogResponse


class LanguageService:
    """지원 언어 조회 + 언어쌍 검증."""

    def catalog(self) -> LanguageCatalogResponse:
        """지원 언어 목록 + 검증쌍을 반환한다. (TODO: M1 — 정적 카탈로그 로드)"""
        raise NotImplementedError("M1")

    def is_supported(self, code: str) -> bool:
        """지원 언어인지. (TODO: M1)"""
        raise NotImplementedError("M1")
