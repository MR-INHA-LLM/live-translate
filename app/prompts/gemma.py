"""Gemma 계열 프롬프트 전략 (quality tier 기준 gemma-4-E2B).

대화 맥락을 system + few-shot 형태로 구성한다.
"""

from __future__ import annotations

from app.domain import ChatMessage, Conversation, TranslationTask


class GemmaPromptBuilder:
    """Gemma 계열 PromptBuilder 구현."""

    def build(self, task: TranslationTask) -> list[ChatMessage]:
        """단발 번역 프롬프트. (TODO: M1)"""
        raise NotImplementedError("M1")

    def build_contextual(
        self, task: TranslationTask, ctx: Conversation
    ) -> list[ChatMessage]:
        """대화 맥락 포함 최종 프롬프트. (TODO: M1)"""
        raise NotImplementedError("M1")
