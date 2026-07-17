"""프롬프트 포트 (Protocol, Strategy).

모델 계열마다 프롬프트 규약이 다르다(HY-MT는 언어쌍별 분기 — decisions.md D0).
계열 추가 = Strategy 구현 하나 추가.
"""

from __future__ import annotations

from typing import Protocol

from app.domain import ChatMessage, Conversation, TranslationTask


class PromptBuilder(Protocol):
    """번역 태스크 → chat 메시지 목록."""

    def build(self, task: TranslationTask) -> list[ChatMessage]:
        """맥락 없는 단발 번역 프롬프트."""
        ...

    def build_contextual(
        self, task: TranslationTask, ctx: Conversation
    ) -> list[ChatMessage]:
        """직전 턴 컨텍스트를 포함한 최종 번역 프롬프트."""
        ...
