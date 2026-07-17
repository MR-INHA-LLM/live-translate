"""ContextAssembler — TMC 대화 컨텍스트 조립 (순수, I/O 없음).

직전 N턴의 이중언어(원문/번역) 쌍을 토큰 예산 안에서 구성한다. 초과 시 오래된
턴부터 절단(요약은 후속 과제 — design.md §11).
"""

from __future__ import annotations

from app.domain import Conversation, Turn


class ContextAssembler:
    """과거 턴 → 최종 프롬프트용 Conversation."""

    def __init__(self, max_turns: int = 5, token_budget: int = 1024) -> None:
        self._max_turns = max_turns
        self._token_budget = token_budget

    def build(self, turns: list[Turn], tgt_lang: str) -> Conversation:
        """직전 N턴을 예산 안에서 Conversation으로 만든다. (TODO: M1)"""
        raise NotImplementedError("M1")
