"""ContextAssembler — TMC 대화 컨텍스트 조립 (순수, I/O 없음).

직전 N턴의 이중언어(원문/번역) 쌍을 토큰 예산 안에서 구성한다. 초과 시 오래된
턴부터 절단(요약은 미도입 — decisions.md D12).
"""

from __future__ import annotations

from app.domain import Conversation, ConversationTurn, Turn


class ContextAssembler:
    """과거 턴 → 최종 프롬프트용 Conversation."""

    def __init__(self, max_turns: int = 5, token_budget: int = 1024) -> None:
        self._max_turns = max_turns
        self._token_budget = token_budget

    @property
    def max_turns(self) -> int:
        return self._max_turns

    def build(self, turns: list[Turn]) -> Conversation:
        """최근 N턴을 예산 안에서 Conversation으로 만든다(오래된 것부터 절단)."""
        recent = [
            ConversationTurn(source=t.source, translation=t.final)
            for t in turns[-self._max_turns :]
            if t.final
        ]
        budget_chars = self._token_budget * 4  # 대략 문자 예산
        while recent and sum(len(c.source) + len(c.translation) for c in recent) > budget_chars:
            recent.pop(0)
        return Conversation(turns=recent)
