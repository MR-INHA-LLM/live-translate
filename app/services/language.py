"""LanguageService — 지원 언어·검증쌍 카탈로그.

카탈로그 소스는 draft 모델(HY-MT1.5) 카드의 언어 태그. 검증쌍 COMET은 M0 실측
(bench/RESULTS_M0.md).
"""

from __future__ import annotations

from app.schemas.language import LanguageCatalogResponse, LanguageInfo, LanguagePair

# (code, name_en, name_native). HY-MT1.5 지원 언어(부분 — 데모 핵심 + 대표).
_LANGS: list[tuple[str, str, str]] = [
    ("ko", "Korean", "한국어"), ("en", "English", "English"),
    ("id", "Indonesian", "Bahasa Indonesia"), ("zh", "Chinese", "中文"),
    ("ja", "Japanese", "日本語"), ("vi", "Vietnamese", "Tiếng Việt"),
    ("th", "Thai", "ไทย"), ("ms", "Malay", "Bahasa Melayu"),
    ("fr", "French", "Français"), ("de", "German", "Deutsch"),
    ("es", "Spanish", "Español"), ("pt", "Portuguese", "Português"),
    ("ru", "Russian", "Русский"), ("ar", "Arabic", "العربية"),
    ("hi", "Hindi", "हिन्दी"), ("tl", "Tagalog", "Tagalog"),
]

# M0 FLORES-200 devtest COMET 실측.
_VALIDATED: list[tuple[str, str, float]] = [
    ("ko", "en", 87.12), ("en", "ko", 90.25), ("ko", "id", 87.90),
    ("id", "ko", 87.80), ("en", "id", 90.67), ("id", "en", 87.81),
]


class LanguageService:
    """지원 언어 조회 + 언어쌍 검증."""

    def __init__(self) -> None:
        self._codes = {c for c, _, _ in _LANGS}

    def catalog(self) -> LanguageCatalogResponse:
        """지원 언어 목록 + 검증쌍을 반환한다."""
        return LanguageCatalogResponse(
            languages=[LanguageInfo(code=c, name_en=en, name_native=nat) for c, en, nat in _LANGS],
            validated_pairs=[LanguagePair(src=s, tgt=t, comet=cm) for s, t, cm in _VALIDATED],
            default_witness="en",
        )

    def is_supported(self, code: str) -> bool:
        return code in self._codes
