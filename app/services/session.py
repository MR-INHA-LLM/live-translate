"""SessionService — 세션 생성/조회."""

from __future__ import annotations

from uuid import uuid4

from app.domain import Session
from app.errors import SessionNotFoundError, UnsupportedLanguageError
from app.repositories.base import SessionRepository
from app.schemas.session import SessionConfig
from app.services.language import LanguageService


class SessionService:
    """세션 유스케이스."""

    def __init__(self, repo: SessionRepository, languages: LanguageService) -> None:
        self._repo = repo
        self._languages = languages

    async def create(self, config: SessionConfig) -> Session:
        """세션을 생성한다.

        언어쌍 검증(지원 언어인지) 후 id 생성 → 도메인 Session 매핑 → 저장.
        tgt==src는 거부하지 않는다(FE UI/UX 처리).

        Raises:
            UnsupportedLanguageError: 미지원 언어.
        """
        for code in {config.src_lang, config.tgt_lang, *config.witness_langs}:
            if not self._languages.is_supported(code):
                raise UnsupportedLanguageError(f"unsupported language: {code}")
        session = Session(
            id=uuid4().hex,
            src_lang=config.src_lang,
            tgt_lang=config.tgt_lang,
            witness_langs=config.witness_langs,
            draft_model=config.draft_model,
            quality_model=config.quality_model,
        )
        return await self._repo.create(session)

    async def get(self, session_id: str) -> Session:
        """세션을 조회한다.

        Raises:
            SessionNotFoundError: 없을 때.
        """
        session = await self._repo.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session
