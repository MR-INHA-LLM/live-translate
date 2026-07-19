"""SQLite 세션 저장소 (SQLAlchemy async + aiosqlite).

DB=SQLite (decisions.md D9). Protocol 뒤라 URL 교체로 Postgres 승격 가능.
"""

from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain import (
    ConversationDetail,
    ConversationSummary,
    Session,
    StoredMessage,
    Turn,
)
from app.models.orm import ConversationRow, MessageRow, SessionRow, TurnRow

_TITLE_MAX = 60


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


class SqlConversationRepository:
    """ConversationRepository의 SQLAlchemy 구현."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory

    async def create(
        self, conv_id: str, src_lang: str, tgt_lang: str, witness_lang: str | None
    ) -> None:
        async with self._sf() as s:
            s.add(ConversationRow(
                id=conv_id, src_lang=src_lang, tgt_lang=tgt_lang, witness_lang=witness_lang,
            ))
            await s.commit()

    async def list_summaries(self, limit: int) -> list[ConversationSummary]:
        # 최근 활동(마지막 메시지 시각) 순. 메시지 없는 대화는 생성 시각으로 정렬.
        last_at = func.max(MessageRow.created_at)
        async with self._sf() as s:
            res = await s.execute(
                select(
                    ConversationRow,
                    func.count(MessageRow.id).label("cnt"),
                    last_at.label("last_at"),
                )
                .outerjoin(MessageRow, MessageRow.conversation_id == ConversationRow.id)
                .group_by(ConversationRow.id)
                .order_by(func.coalesce(last_at, ConversationRow.created_at).desc())
                .limit(limit)
            )
            return [
                ConversationSummary(
                    id=row.id, src_lang=row.src_lang, tgt_lang=row.tgt_lang,
                    witness_lang=row.witness_lang, title=row.title,
                    message_count=cnt, updated_at=last_at_val or row.created_at,
                )
                for row, cnt, last_at_val in res.all()
            ]

    async def get_detail(self, conv_id: str) -> ConversationDetail | None:
        async with self._sf() as s:
            row = await s.get(ConversationRow, conv_id)
            if row is None:
                return None
            res = await s.execute(
                select(MessageRow).where(MessageRow.conversation_id == conv_id)
                .order_by(MessageRow.seq.asc())
            )
            messages = [
                StoredMessage(side=m.side, source=m.source, translation=m.translation,
                              draft=m.draft, witness=m.witness, round_trip=m.round_trip,
                              confidence=m.confidence, alignment=m.alignment,
                              draft_ms=m.draft_ms, final_ms=m.final_ms,
                              round_trip_ms=m.round_trip_ms, seq=m.seq)
                for m in res.scalars().all()
            ]
            return ConversationDetail(
                id=row.id, src_lang=row.src_lang, tgt_lang=row.tgt_lang,
                witness_lang=row.witness_lang, messages=messages,
            )

    async def append_message(self, conv_id: str, message: StoredMessage) -> StoredMessage:
        async with self._sf() as s:
            conv = await s.get(ConversationRow, conv_id)
            if conv is None:
                raise KeyError(conv_id)
            count = await s.scalar(
                select(func.count(MessageRow.id)).where(MessageRow.conversation_id == conv_id)
            )
            seq = int(count or 0)
            if conv.title is None and message.source.strip():
                conv.title = message.source.strip()[:_TITLE_MAX]
            s.add(MessageRow(
                conversation_id=conv_id, seq=seq, side=message.side,
                source=message.source, draft=message.draft, translation=message.translation,
                witness=message.witness, round_trip=message.round_trip,
                confidence=message.confidence, alignment=message.alignment,
                draft_ms=message.draft_ms, final_ms=message.final_ms,
                round_trip_ms=message.round_trip_ms,
            ))
            await s.commit()
            return StoredMessage(
                side=message.side, source=message.source, translation=message.translation,
                draft=message.draft, witness=message.witness, round_trip=message.round_trip,
                confidence=message.confidence, alignment=message.alignment,
                draft_ms=message.draft_ms, final_ms=message.final_ms,
                round_trip_ms=message.round_trip_ms, seq=seq,
            )

    async def delete(self, conv_id: str) -> bool:
        async with self._sf() as s:
            if await s.get(ConversationRow, conv_id) is None:
                return False
            await s.execute(sa_delete(MessageRow).where(MessageRow.conversation_id == conv_id))
            await s.execute(sa_delete(ConversationRow).where(ConversationRow.id == conv_id))
            await s.commit()
            return True
