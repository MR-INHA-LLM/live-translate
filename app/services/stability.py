"""StabilityPolicy — 초벌 안정화 판단 (순수, I/O 없음).

목표문 접두어 확정(commit_prefix)은 어순 유사 쌍에서만 의미가 있다(decisions.md D3).
기본은 off — ko↔id 같은 어순 비대응 쌍은 접두어가 거의 보존되지 않기 때문.
"""

from __future__ import annotations

# 접두어 확정을 켤 만한 어순 유사 쌍(예: ko↔ja). M1에서 실측으로 확정.
_COMMIT_PREFIX_PAIRS: frozenset[tuple[str, str]] = frozenset()


class StabilityPolicy:
    """언어쌍에 따라 접두어 확정 여부를 결정한다."""

    def should_commit(self, src: str, tgt: str) -> bool:
        """어순 유사 쌍만 True. 기본 정책은 접두어 freeze 미사용."""
        return (src, tgt) in _COMMIT_PREFIX_PAIRS
