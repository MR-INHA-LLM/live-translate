"""초벌 WS 메시지 스키마 (`/api/v1/sessions/{id}/stream`).

세션은 경로에 있으므로 메시지 본문에 session_id를 넣지 않는다.
"""

from __future__ import annotations

from pydantic import BaseModel


class DraftRequest(BaseModel):
    """client → server: 타이핑 중 부분 입력."""

    revision_id: int
    partial_text: str
    is_final: bool = False


class DraftResponse(BaseModel):
    """server → client: revision별 다중 타겟 렌더."""

    revision_id: int
    renderings: dict[str, str]  # lang → 번역
    committed_prefix_len: dict[str, int] = {}  # commit_prefix=false면 모두 0
    latency_ms: dict[str, float] = {}  # {"ttft","total"}


class DraftError(BaseModel):
    """server → client: 업스트림 오류(해당 revision)."""

    revision_id: int
    error: str
