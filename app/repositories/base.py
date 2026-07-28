"""저장소 포트 (Protocol). 세션이 Turn의 애그리거트 루트."""

from __future__ import annotations

from typing import Protocol

from app.domain import (
    ApiKey,
    ConversationDetail,
    ConversationSummary,
    Session,
    StoredMessage,
    Turn,
)


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


class ConversationRepository(Protocol):
    """저장된 대화(이력) 영속 — 번역 파이프라인과 분리(decisions.md D14)."""

    async def create(
        self, conv_id: str, src_lang: str, tgt_lang: str, witness_lang: str | None
    ) -> None:
        """빈 대화를 생성한다(id는 서비스가 생성)."""
        ...

    async def list_summaries(self, limit: int) -> list[ConversationSummary]:
        """최근 활동 순 대화 요약 목록."""
        ...

    async def get_detail(self, conv_id: str) -> ConversationDetail | None:
        """대화 상세(메시지 포함). 없으면 None."""
        ...

    async def append_message(self, conv_id: str, message: StoredMessage) -> StoredMessage:
        """메시지를 대화에 추가한다(seq 자동 부여, 첫 메시지로 제목 설정)."""
        ...

    async def delete(self, conv_id: str) -> bool:
        """대화와 그 메시지를 삭제한다. 존재했으면 True, 없었으면 False."""
        ...


class ApiKeyRepository(Protocol):
    """발급된 API 키 영속 (SQLite 구현은 sql.py). 평문 대신 해시만 저장."""

    async def add(self, key_id: str, key_hash: str, prefix: str, label: str) -> ApiKey:
        """키를 저장하고 공개 메타(ApiKey)를 반환한다."""
        ...

    async def list(self) -> list[ApiKey]:
        """전체 키 목록(폐기 포함), 최근 생성 순."""
        ...

    async def enabled_hashes(self) -> set[str]:
        """활성 키의 해시 집합(검증 캐시 소스)."""
        ...

    async def has_any(self) -> bool:
        """키 레코드가 하나라도 있는지(폐기 포함). '열림 모드' 판정용."""
        ...

    async def exists(self, key_hash: str) -> bool:
        """해시 존재 여부(seed 멱등성 — 폐기된 키를 되살리지 않도록)."""
        ...

    async def set_enabled(self, key_id: str, enabled: bool) -> bool:
        """활성/폐기 토글. 존재했으면 True."""
        ...

    async def touch(self, key_hash: str) -> None:
        """last_used_at 갱신(best-effort)."""
        ...
