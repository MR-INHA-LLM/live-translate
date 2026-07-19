"""ContextAssembler — 대화 맥락(원문 순서열) 트리밍 (순수, I/O 없음).

Pombal et al.(TACL 2026)에 따라 컨텍스트는 직전 턴들의 **원문**을 순서대로 담는다
(번역문 아님). 최근 N턴으로 자르고, 토큰 예산 초과 시 오래된 턴부터 절단한다
(요약 미도입 — decisions.md D12). 논문 §6.1: 6~10턴이면 대부분 언어쌍에서 충분.
"""

from __future__ import annotations


class ContextAssembler:
    """FE가 전달한 대화 원문열 → 프롬프트용 컨텍스트(원문 리스트)."""

    def __init__(self, max_turns: int = 10, token_budget: int = 1024) -> None:
        self._max_turns = max_turns
        self._token_budget = token_budget

    @property
    def max_turns(self) -> int:
        return self._max_turns

    def trim(self, originals: list[str]) -> list[str]:
        """최근 N턴을 예산 안에서 반환한다(오래된 것부터 절단, 순서 유지)."""
        recent = [t for t in originals[-self._max_turns :] if t.strip()]
        budget_chars = self._token_budget * 4  # 대략 문자 예산
        while recent and sum(len(t) for t in recent) > budget_chars:
            recent.pop(0)
        return recent
