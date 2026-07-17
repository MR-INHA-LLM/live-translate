"""SQLite 세션 저장소 (SQLAlchemy async + aiosqlite).

DB=SQLite (decisions.md D9). Protocol 뒤라 URL 교체로 Postgres 승격 가능.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain import Session, Turn
from app.models.orm import SessionRow, TurnRow


class SqlSessionRepository:
    """SessionRepository의 SQLAlchemy 구현."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def create(self, session: Session) -> Session:
        async with self._sf() as s:
            s.add(SessionRow(
                id=session.id, src_lang=session.src_lang, tgt_lang=session.tgt_lang,
                witness_langs=session.witness_langs, draft_model=session.draft_model,
                quality_model=session.quality_model,
            ))
            await s.commit()
        return session

    async def get(self, session_id: str) -> Session | None:
        async with self._sf() as s:
            row = await s.get(SessionRow, session_id)
            if row is None:
                return None
            return Session(
                id=row.id, src_lang=row.src_lang, tgt_lang=row.tgt_lang,
                witness_langs=list(row.witness_langs), draft_model=row.draft_model,
                quality_model=row.quality_model,
            )

    async def append_turn(self, session_id: str, turn: Turn) -> None:
        async with self._sf() as s:
            s.add(TurnRow(
                session_id=session_id, turn_id=turn.turn_id, source=turn.source,
                draft=turn.draft, final=turn.final,
            ))
            await s.commit()

    async def recent_turns(self, session_id: str, n: int) -> list[Turn]:
        async with self._sf() as s:
            res = await s.execute(
                select(TurnRow).where(TurnRow.session_id == session_id)
                .order_by(TurnRow.turn_id.desc()).limit(n)
            )
            rows = list(res.scalars().all())
            return [Turn(turn_id=r.turn_id, source=r.source, draft=r.draft, final=r.final)
                    for r in reversed(rows)]
