"""SQLite 세션 저장소 (SQLAlchemy async + aiosqlite).

DB=SQLite (decisions.md D9). Protocol 뒤라 URL 교체로 Postgres 승격 가능.
여기서만 SQLAlchemy를 import한다.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain import Session, Turn


class SqlSessionRepository:
    """SessionRepository의 SQLAlchemy 구현."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        """
        Args:
            session_factory: async DB 세션 팩토리(엔진에 바인딩됨).
        """
        self._sf = session_factory

    async def create(self, session: Session) -> Session:
        """세션 행을 INSERT한다. (TODO: M1)"""
        raise NotImplementedError("M1")

    async def get(self, session_id: str) -> Session | None:
        """세션 행을 조회해 도메인 객체로 매핑한다. (TODO: M1)"""
        raise NotImplementedError("M1")

    async def append_turn(self, session_id: str, turn: Turn) -> None:
        """턴 행을 INSERT한다. (TODO: M1)"""
        raise NotImplementedError("M1")

    async def recent_turns(self, session_id: str, n: int) -> list[Turn]:
        """최근 n턴을 turn_id 역순으로 조회한다. (TODO: M1)"""
        raise NotImplementedError("M1")
