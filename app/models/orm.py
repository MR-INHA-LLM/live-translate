"""SQLAlchemy ORM 테이블 정의.

SQLite 대상(decisions.md D9). 스키마 변경은 Alembic(SQLite ALTER 제약은
`render_as_batch=True`). JSON 컬럼으로 언어 목록·렌더 dict를 저장한다.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """ORM 베이스."""


class SessionRow(Base):
    """세션 레코드."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    src_lang: Mapped[str] = mapped_column(String(8))
    tgt_lang: Mapped[str] = mapped_column(String(8))
    witness_langs: Mapped[list[str]] = mapped_column(JSON, default=list)
    draft_model: Mapped[str] = mapped_column(String(64))
    quality_model: Mapped[str] = mapped_column(String(64))

    turns: Mapped[list["TurnRow"]] = relationship(back_populates="session")


class TurnRow(Base):
    """턴 레코드 (세션 하위)."""

    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    turn_id: Mapped[int] = mapped_column()
    source: Mapped[str] = mapped_column(Text)
    draft: Mapped[dict] = mapped_column(JSON, default=dict)
    final: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[SessionRow] = relationship(back_populates="turns")


class ConversationRow(Base):
    """저장된 대화(사용자에게 보이는 이력).

    번역 파이프라인용 `sessions`/`turns`와 분리한다(decisions.md D14): 이쪽은 UI가
    보여준 최종 메시지를 그대로 담아 목록·복원에 쓰는 뷰 모델이다.
    """

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    src_lang: Mapped[str] = mapped_column(String(8))
    tgt_lang: Mapped[str] = mapped_column(String(8))
    witness_lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["MessageRow"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageRow(Base):
    """대화 메시지 한 건 (대화 하위). UI가 렌더한 최종 형태 그대로."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    seq: Mapped[int] = mapped_column()
    side: Mapped[str] = mapped_column(String(8))  # "mine" | "theirs"
    source: Mapped[str] = mapped_column(Text)
    draft: Mapped[str | None] = mapped_column(Text, nullable=True)  # 초벌(빠른) 번역
    translation: Mapped[str] = mapped_column(Text)  # LLM(최종) 번역
    witness: Mapped[str | None] = mapped_column(Text, nullable=True)  # 검증(확인용 언어)
    round_trip: Mapped[str | None] = mapped_column(Text, nullable=True)  # 역번역(tgt→src)
    confidence: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 단어 QE 스팬
    alignment: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 구 정렬 스팬
    draft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)  # 초벌·검증 소요(ms)
    final_ms: Mapped[float | None] = mapped_column(Float, nullable=True)  # LLM 소요(ms)
    round_trip_ms: Mapped[float | None] = mapped_column(Float, nullable=True)  # 역번역 소요(ms)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[ConversationRow] = relationship(back_populates="messages")
