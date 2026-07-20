"""예외 핸들러 — 도메인 예외를 HTTP + ErrorResponse로 매핑.

HTTP 상태코드 지식은 여기 한 곳에만 둔다(도메인은 모른다).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import (
    ConversationNotFoundError,
    SessionNotFoundError,
    UnsupportedLanguageError,
    UpstreamEngineError,
)
from app.schemas.errors import ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    """앱에 도메인 예외 핸들러를 등록한다."""

    @app.exception_handler(SessionNotFoundError)
    async def _session_not_found(_: Request, exc: SessionNotFoundError) -> JSONResponse:
        body = ErrorResponse(detail=str(exc) or "session not found",
                             error_code="session_not_found")
        return JSONResponse(status_code=404, content=body.model_dump())

    @app.exception_handler(ConversationNotFoundError)
    async def _conversation_not_found(_: Request, exc: ConversationNotFoundError) -> JSONResponse:
        body = ErrorResponse(detail=str(exc) or "conversation not found",
                             error_code="conversation_not_found")
        return JSONResponse(status_code=404, content=body.model_dump())

    @app.exception_handler(UnsupportedLanguageError)
    async def _unsupported_language(_: Request, exc: UnsupportedLanguageError) -> JSONResponse:
        body = ErrorResponse(detail=str(exc) or "unsupported language",
                             error_code="unsupported_language")
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(UpstreamEngineError)
    async def _upstream_engine(_: Request, exc: UpstreamEngineError) -> JSONResponse:
        body = ErrorResponse(detail=str(exc) or "translation engine unavailable",
                             error_code="upstream_engine_error")
        return JSONResponse(status_code=503, content=body.model_dump())
