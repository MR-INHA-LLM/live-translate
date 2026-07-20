"""API 키 인증 의존성 단위 테스트 (서버·vLLM 불필요)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import verify_api_key


def _req(keys: set[str]) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(api_keys=keys)))


def test_disabled_when_no_keys() -> None:
    # 설정된 키가 없으면 인증 비활성 — 통과.
    verify_api_key(_req(set()), None)


def test_requires_key_when_configured() -> None:
    with pytest.raises(HTTPException) as e:
        verify_api_key(_req({"k1"}), None)
    assert e.value.status_code == 401


def test_rejects_wrong_key() -> None:
    with pytest.raises(HTTPException) as e:
        verify_api_key(_req({"k1", "k2"}), "nope")
    assert e.value.status_code == 401


def test_accepts_valid_key() -> None:
    verify_api_key(_req({"k1", "k2"}), "k2")  # no raise
