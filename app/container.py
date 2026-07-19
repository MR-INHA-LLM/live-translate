"""의존성 컨테이너 — 조립된 서비스·어댑터 묶음.

main.py(lifespan)에서 한 번 생성해 `app.state.container`에 둔다. 라우터는
api/deps.py를 통해 여기서 서비스를 받는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.engines.registry import ModelRegistry
from app.repositories.base import ConversationRepository, SessionRepository
from app.repositories.cache import RenderingCache
from app.services.alignment import AlignerPort
from app.services.conversation import ConversationService
from app.services.draft import DraftService
from app.services.language import LanguageService
from app.services.quality import QualityService
from app.services.session import SessionService


@dataclass
class Container:
    """조립된 애플리케이션 의존성."""

    registry: ModelRegistry
    session_repo: SessionRepository
    conversation_repo: ConversationRepository
    aligner: AlignerPort
    cache: RenderingCache
    draft_service: DraftService
    quality_service: QualityService
    session_service: SessionService
    conversation_service: ConversationService
    language_service: LanguageService
