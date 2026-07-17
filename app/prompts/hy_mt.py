"""HY-MT1.5 프롬프트 전략.

언어쌍별로 지시문이 갈린다: zh가 source/target이면 중문 지시, 그 외는 영문 지시
(모델 카드 근거). 실동작 참조 구현은 bench/prompts.py에 있다 — M1에서 여기로 승격.
"""

from __future__ import annotations

from app.domain import ChatMessage, Conversation, TranslationTask


class HyMtPromptBuilder:
    """HY-MT 계열 PromptBuilder 구현."""

    def build(self, task: TranslationTask) -> list[ChatMessage]:
        """언어쌍 분기(zh↔ 중문 / 그 외 영문) 적용. (TODO: M1 — bench/prompts.py 이식)"""
        raise NotImplementedError("M1")

    def build_contextual(
        self, task: TranslationTask, ctx: Conversation
    ) -> list[ChatMessage]:
        """contextual template에 직전 턴 주입. (TODO: M1)"""
        raise NotImplementedError("M1")
