"""애플리케이션 진입점 + 컴포지션 루트.

구체 어댑터는 lifespan에서 한 번만 생성해 Container로 묶고 `app.state`에 둔다.
서비스는 Protocol만 받으므로 테스트에서 대체 가능(DIP).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.deps import verify_api_key
from app.api.errors import register_exception_handlers
from app.api.v1 import conversations, languages, sessions, stream, translations, turns
from app.config import Settings
from app.container import Container
from app.core.logging import setup_logging
from app.domain import Tier
from app.engines.openai import VllmEngine
from app.engines.registry import ModelRegistry
from app.models.orm import Base
from app.prompts.hy_mt import HyMtPromptBuilder
from app.prompts.qwen import QwenPromptBuilder
from app.repositories.cache import InProcessRenderingCache
from app.repositories.sql import SqlConversationRepository, SqlSessionRepository
from app.services.alignment import HttpAligner
from app.services.context import ContextAssembler
from app.services.conversation import ConversationService
from app.services.draft import DraftService
from app.services.language import LanguageService
from app.services.quality import QualityService
from app.services.session import SessionService
from app.services.translation import TranslationService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """구체 의존성을 조립해 컨테이너를 만든다(컴포지션 루트)."""
    settings = Settings()

    # 엔진(vLLM OpenAI 호환 클라이언트) + 프롬프트 전략 → 레지스트리
    draft = VllmEngine(settings.draft_url, Tier.DRAFT, settings.engine_max_concurrency)
    registry = ModelRegistry()
    registry.register(settings.draft_model, draft, HyMtPromptBuilder(), Tier.DRAFT)
    # quality tier: 꺼져 있으면 미등록 → 최종 번역이 draft로 degrade(CPU 배포 등).
    quality = None
    if settings.quality_enabled:
        quality = VllmEngine(settings.quality_url, Tier.QUALITY, settings.engine_max_concurrency)
        registry.register(settings.quality_model, quality, QwenPromptBuilder(), Tier.QUALITY)

    # 저장(SQLite) + 캐시(인메모리)
    db_engine = create_async_engine(settings.db_url)
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    repo = SqlSessionRepository(session_factory)
    conversation_repo = SqlConversationRepository(session_factory)
    aligner = HttpAligner(settings.align_url)
    cache = InProcessRenderingCache(settings.cache_max_entries)

    # 서비스
    languages_svc = LanguageService()
    context = ContextAssembler(settings.context_turns, settings.context_token_budget)
    app.state.api_keys = settings.api_key_set  # 공개 API 키(비면 인증 비활성)
    app.state.container = Container(
        registry=registry,
        session_repo=repo,
        conversation_repo=conversation_repo,
        aligner=aligner,
        cache=cache,
        draft_service=DraftService(registry, cache),
        quality_service=QualityService(registry, repo, context, aligner),
        session_service=SessionService(repo, languages_svc),
        conversation_service=ConversationService(conversation_repo),
        translation_service=TranslationService(
            registry, context, aligner, settings.draft_model, settings.quality_model
        ),
        language_service=languages_svc,
    )
    try:
        yield
    finally:
        await draft.aclose()
        if quality is not None:
            await quality.aclose()
        await aligner.aclose()
        await db_engine.dispose()


def create_app() -> FastAPI:
    """FastAPI 앱을 구성해 반환한다."""
    settings = Settings()
    setup_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    # API 키 인증(설정 시). 전 API에 적용 — WS(stream)는 헤더 불가라 쿼리 파라미터로
    # 자체 검증(stream.py), /health(라이브니스 프로브)만 공개로 남긴다.
    auth = [Depends(verify_api_key)]
    app.include_router(sessions.router, prefix="/api/v1", dependencies=auth)
    app.include_router(conversations.router, prefix="/api/v1", dependencies=auth)
    app.include_router(turns.router, prefix="/api/v1", dependencies=auth)
    app.include_router(translations.router, prefix="/api/v1", dependencies=auth)
    app.include_router(languages.router, prefix="/api/v1", dependencies=auth)
    app.include_router(stream.router, prefix="/api/v1")

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        """라이브니스. (모델 로드 상태 상세는 M1)"""
        return {"status": "ok"}

    return app


app = create_app()
