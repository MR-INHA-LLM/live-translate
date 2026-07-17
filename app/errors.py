"""예외 계층.

도메인 예외는 HTTP 상태코드를 모른다 — 매핑은 api/errors.py 핸들러에만 있다.
인프라 예외(UpstreamEngineError)는 유스케이스가 degradation으로 처리하거나
경계에서 5xx로 매핑된다.
"""

from __future__ import annotations


class DomainError(Exception):
    """도메인 규칙 위반의 최상위."""


class SessionNotFoundError(DomainError):
    """존재하지 않는 세션 접근 → 404."""


class UnsupportedLanguageError(DomainError):
    """지원하지 않는 언어/언어쌍 → 422."""


class UpstreamEngineError(Exception):
    """엔진(vLLM) 호출 실패 — 전송/타임아웃 등. degradation 또는 5xx 대상."""
