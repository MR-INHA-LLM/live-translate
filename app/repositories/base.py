"""저장소 포트 (Protocol). 세션이 Turn의 애그리거트 루트."""

from __future__ import annotations

from typing import Protocol

from app.domain import Session, Turn


class SessionRepository(Protocol):
    """세션·턴 영속 (SQLite 구현은 sql.py)."""

    async def create(self, session: Session) -> Session:
        """세션을 저장한다(id는 서비스가 생성)."""
        ...

    async def get(self, session_id: str) -> Session | None:
        """세션을 조회한다. 없으면 None."""
        ...

    async def append_turn(self, session_id: str, turn: Turn) -> None:
        """턴을 세션에 추가한다(이력 일관성 단일 지점)."""
        ...

    async def recent_turns(self, session_id: str, n: int) -> list[Turn]:
        """최근 n턴을 반환한다(컨텍스트 조립용)."""
        ...
