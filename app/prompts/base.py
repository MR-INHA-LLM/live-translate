"""프롬프트 포트 (Protocol, Strategy).

모델 계열마다 프롬프트 규약이 다르다(HY-MT는 언어쌍별 분기 — decisions.md D0).
계열 추가 = Strategy 구현 하나 추가.
"""

from __future__ import annotations

from typing import Protocol

from app.domain import ChatMessage, TranslationTask


class PromptBuilder(Protocol):
    """번역 태스크 → chat 메시지 목록."""

    def build(self, task: TranslationTask) -> list[ChatMessage]:
        """맥락 없는 단발 번역 프롬프트."""
        ...

    def build_contextual(
        self, task: TranslationTask, context: list[str]
    ) -> list[ChatMessage]:
        """대화 맥락(직전 턴들의 **원문** 순서열)을 포함한 최종 번역 프롬프트.

        Pombal et al.(TACL 2026)의 context-aware 프레임워크를 따른다: 번역문이 아닌
        각 참가자의 원문(x_<t)을 순서대로 주입해 대명사·생략·모호성을 해소한다.
        """
        ...
