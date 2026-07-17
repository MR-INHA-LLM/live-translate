"""SessionService — 세션 생성/조회 + 워밍업."""

from __future__ import annotations

from app.domain import Session
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

        흐름(TODO: M1): 언어쌍 검증(UnsupportedLanguageError) → id 생성 →
        SessionConfig를 도메인 Session으로 매핑 → repo.create → 워밍업 1회
        백그라운드 발사(콜드 TTFT 제거, D4).
        """
        raise NotImplementedError("M1")

    async def get(self, session_id: str) -> Session:
        """세션을 조회한다.

        Raises:
            SessionNotFoundError: 없을 때.
        """
        raise NotImplementedError("M1")
