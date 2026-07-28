"""API 키 인증 단위 테스트 — ApiKeyService(가짜 repo) + admin 의존성. DB·서버 불필요."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import verify_admin_key
from app.domain import ApiKey
from app.services.api_key import ApiKeyService, hash_key

_FIXED = datetime(2026, 1, 1, tzinfo=UTC)


class FakeApiKeyRepo:
    """인메모리 ApiKeyRepository 구현(테스트용)."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    async def add(self, key_id: str, key_hash: str, prefix: str, label: str) -> ApiKey:
        self.rows[key_id] = {"key_hash": key_hash, "prefix": prefix, "label": label, "enabled": True}
        return ApiKey(id=key_id, label=label, prefix=prefix, enabled=True, created_at=_FIXED)

    async def list(self) -> list[ApiKey]:
        return [
            ApiKey(id=i, label=r["label"], prefix=r["prefix"], enabled=r["enabled"], created_at=_FIXED)
            for i, r in self.rows.items()
        ]

    async def enabled_hashes(self) -> set[str]:
        return {r["key_hash"] for r in self.rows.values() if r["enabled"]}

    async def has_any(self) -> bool:
        return bool(self.rows)

    async def exists(self, key_hash: str) -> bool:
        return any(r["key_hash"] == key_hash for r in self.rows.values())

    async def set_enabled(self, key_id: str, enabled: bool) -> bool:
        if key_id not in self.rows:
            return False
        self.rows[key_id]["enabled"] = enabled
        return True

    async def touch(self, key_hash: str) -> None:
        pass


def _svc() -> ApiKeyService:
    return ApiKeyService(FakeApiKeyRepo())


def test_open_when_no_keys() -> None:
    # 활성 키가 하나도 없으면 인증 비활성(개발/데모) — 아무 값이나 통과.
    svc = _svc()
    assert asyncio.run(svc.verify("anything")) is True
    assert asyncio.run(svc.verify(None)) is True


def test_issue_then_verify() -> None:
    svc = _svc()

    async def flow() -> None:
        rec, key = await svc.issue("acme")
        assert key.startswith("lt_ext_")
        assert rec.prefix == key[:16]
        assert await svc.verify(key) is True       # 발급 즉시 유효(캐시 무효화)
        assert await svc.verify("wrong") is False   # 불일치 거부
        assert await svc.verify(None) is False      # 미제공 거부

    asyncio.run(flow())


def test_revoke_disables_key() -> None:
    svc = _svc()

    async def flow() -> None:
        rec, key = await svc.issue("acme")
        assert await svc.verify(key) is True
        assert await svc.revoke(rec.id) is True
        assert await svc.verify(key) is False       # 폐기 후 거부
        assert await svc.revoke("missing") is False  # 없는 id

    asyncio.run(flow())


def test_seed_is_idempotent_and_not_reviving() -> None:
    repo = FakeApiKeyRepo()
    svc = ApiKeyService(repo)

    async def flow() -> None:
        await svc.seed("lt_console_seedkey", "console")
        await svc.seed("lt_console_seedkey", "console")  # 두 번째는 무시
        assert len(repo.rows) == 1
        # 폐기 후 재-seed 해도 되살아나지 않는다.
        [key_id] = list(repo.rows)
        await svc.revoke(key_id)
        await svc.seed("lt_console_seedkey", "console")
        assert repo.rows[key_id]["enabled"] is False

    asyncio.run(flow())


def _admin_req(admin_key: str) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(admin_api_key=admin_key)))


def test_admin_disabled_without_key() -> None:
    with pytest.raises(HTTPException) as e:
        verify_admin_key(_admin_req(""), "whatever")
    assert e.value.status_code == 503


def test_admin_rejects_wrong_key() -> None:
    with pytest.raises(HTTPException) as e:
        verify_admin_key(_admin_req("s3cret"), "nope")
    assert e.value.status_code == 401


def test_admin_accepts_correct_key() -> None:
    verify_admin_key(_admin_req("s3cret"), "s3cret")  # no raise


def test_hash_key_is_sha256_hex() -> None:
    assert len(hash_key("x")) == 64
    assert hash_key("x") == hash_key("x")
    assert hash_key("x") != hash_key("y")
