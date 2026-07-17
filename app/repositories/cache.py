"""결정성 렌더 캐시 (인메모리 LRU — decisions.md D10).

키는 `(draft_model, src_lang, tgt_lang, 정규화_소스)`. temp=0 결정성이라 동일 키는
동일 렌더(D3). Protocol 뒤라 다중 노드 시 RedisRenderingCache로 교체 가능.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Protocol

from app.domain import Rendering


def cache_key(model: str, src: str, tgt: str, normalized_source: str) -> str:
    """캐시 키를 구성한다."""
    return f"{model}|{src}|{tgt}|{normalized_source}"


class RenderingCache(Protocol):
    """정규화 소스 → 타겟별 렌더 캐시."""

    def get(self, key: str) -> dict[str, Rendering] | None: ...

    def put(self, key: str, renderings: dict[str, Rendering]) -> None: ...


class InProcessRenderingCache:
    """bounded LRU 구현 (plumbing)."""

    def __init__(self, max_entries: int = 2048) -> None:
        self._max = max_entries
        self._store: OrderedDict[str, dict[str, Rendering]] = OrderedDict()

    def get(self, key: str) -> dict[str, Rendering] | None:
        """조회 시 최근 사용으로 갱신."""
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key: str, renderings: dict[str, Rendering]) -> None:
        """저장하고 초과 시 가장 오래된 항목을 축출."""
        self._store[key] = renderings
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)
