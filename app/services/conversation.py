"""ConversationService — 저장된 대화 이력의 생성/목록/복원/추가.

번역 파이프라인(SessionService/QualityService)과 분리된 뷰 모델 유스케이스
(decisions.md D14). 언어쌍 검증은 세션 생성에서 이미 수행되므로 여기서는
저장·조회 책임만 진다.
"""

from __future__ import annotations

from uuid import uuid4

from app.domain import ConversationDetail, ConversationSummary, StoredMessage
from app.errors import ConversationNotFoundError
from app.repositories.base import ConversationRepository


class ConversationService:
    """대화 이력 유스케이스."""

    def __init__(self, repo: ConversationRepository, list_limit: int = 50) -> None:
        self._repo = repo
        self._list_limit = list_limit

    async def create(
        self, src_lang: str, tgt_lang: str, witness_lang: str | None
    ) -> str:
        """빈 대화를 만들고 id를 반환한다."""
        conv_id = uuid4().hex
        await self._repo.create(conv_id, src_lang, tgt_lang, witness_lang)
        return conv_id

    async def list(self) -> list[ConversationSummary]:
        """최근 활동 순 대화 목록."""
        return await self._repo.list_summaries(self._list_limit)

    async def get(self, conv_id: str) -> ConversationDetail:
        """대화 상세를 반환한다.

        Raises:
            ConversationNotFoundError: 없을 때.
        """
        detail = await self._repo.get_detail(conv_id)
        if detail is None:
            raise ConversationNotFoundError(conv_id)
        return detail

    async def add_message(self, conv_id: str, message: StoredMessage) -> StoredMessage:
        """대화에 메시지를 추가한다.

        Raises:
            ConversationNotFoundError: 대화가 없을 때.
        """
        try:
            return await self._repo.append_message(conv_id, message)
        except KeyError as exc:
            raise ConversationNotFoundError(conv_id) from exc

    async def delete(self, conv_id: str) -> None:
        """대화를 삭제한다.

        Raises:
            ConversationNotFoundError: 없을 때.
        """
        if not await self._repo.delete(conv_id):
            raise ConversationNotFoundError(conv_id)
