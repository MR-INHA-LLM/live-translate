"""ApiKeyService — 공개 API 키 발급·검증·폐기 (유스케이스).

키는 DB(api_keys)에서 관리한다: 평문 대신 SHA-256 해시만 저장하고, 검증은 해시
집합 대조로 한다. 핫패스(초벌 WS·REST 매 요청)를 위해 활성 해시를 짧은 TTL로
인메모리 캐시하고, 발급·폐기 시 무효화해 즉시 반영한다.

키가 하나도 없으면(테이블 비었으면) 인증 비활성 — 개발/데모 편의를 위한 열림 모드.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
import uuid

from app.domain import ApiKey
from app.repositories.base import ApiKeyRepository

logger = logging.getLogger(__name__)

_TOUCH_THROTTLE_S = 60.0  # last_used_at 갱신 최소 간격(쓰기 증폭 억제)
_PREFIX_LEN = 16


def hash_key(key: str) -> str:
    """키의 SHA-256 16진 해시(저장·대조용)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ApiKeyService:
    """API 키 유스케이스 — 발급/검증/폐기 + 활성 해시 캐시."""

    def __init__(self, repo: ApiKeyRepository, cache_ttl_s: float = 30.0) -> None:
        self._repo = repo
        self._ttl = cache_ttl_s
        self._hashes: set[str] = set()
        self._has_any = False  # 키 레코드 존재 여부(폐기 포함) — 열림 모드 판정
        self._loaded_at = -1.0  # 아직 로드 안 됨
        self._lock = asyncio.Lock()
        self._touched: dict[str, float] = {}

    async def _ensure_fresh(self) -> None:
        """캐시가 오래됐으면 활성 해시를 DB에서 다시 읽는다(스탬피드 방지)."""
        if self._loaded_at >= 0 and time.monotonic() - self._loaded_at <= self._ttl:
            return
        async with self._lock:
            if self._loaded_at < 0 or time.monotonic() - self._loaded_at > self._ttl:
                self._hashes = await self._repo.enabled_hashes()
                self._has_any = await self._repo.has_any()
                self._loaded_at = time.monotonic()

    def _invalidate(self) -> None:
        self._loaded_at = -1.0

    async def verify(self, key: str | None) -> bool:
        """키 유효성. 키 레코드가 한 개도 없으면(한 번도 설정 안 함) 열림(인증 비활성).

        키가 하나라도 존재하면(전부 폐기됐더라도) 인증을 강제한다 — '전부 폐기'가
        의도치 않게 인증을 여는 footgun 방지.
        """
        await self._ensure_fresh()
        if not self._has_any:
            return True  # 키 미설정 → 인증 비활성(개발/데모)
        if not key:
            return False
        h = hash_key(key)
        if h not in self._hashes:
            return False
        await self._maybe_touch(h)
        return True

    async def _maybe_touch(self, key_hash: str) -> None:
        """last_used_at 갱신(스로틀·best-effort)."""
        now = time.monotonic()
        if now - self._touched.get(key_hash, 0.0) < _TOUCH_THROTTLE_S:
            return
        self._touched[key_hash] = now
        try:
            await self._repo.touch(key_hash)
        except Exception:
            logger.exception("api key last_used 갱신 실패")

    async def issue(self, label: str) -> tuple[ApiKey, str]:
        """외부 키를 발급한다. (공개 메타, 평문 키) 반환 — 평문은 여기서만 노출."""
        key = f"lt_ext_{secrets.token_urlsafe(24)}"
        rec = await self._repo.add(uuid.uuid4().hex, hash_key(key), key[:_PREFIX_LEN], label)
        self._invalidate()
        return rec, key

    async def seed(self, key: str, label: str) -> None:
        """부트스트랩 키를 insert-if-absent 로 seed 한다.

        이미 존재하면(폐기됐더라도) 건드리지 않는다 — 재시작 때 폐기된 키가
        되살아나지 않도록.
        """
        h = hash_key(key)
        if await self._repo.exists(h):
            return
        await self._repo.add(uuid.uuid4().hex, h, key[:_PREFIX_LEN], label)
        self._invalidate()

    async def list(self) -> list[ApiKey]:
        """전체 키 목록(폐기 포함)."""
        return await self._repo.list()

    async def revoke(self, key_id: str) -> bool:
        """키를 폐기(비활성)한다. 존재했으면 True."""
        ok = await self._repo.set_enabled(key_id, False)
        if ok:
            self._invalidate()
        return ok
