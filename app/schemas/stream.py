"""초벌 WS 메시지 스키마 (`/api/v1/sessions/{id}/stream`).

세션은 경로에 있으므로 메시지 본문에 session_id를 넣지 않는다. 초벌은 저지연 핫패스라
정렬·QE는 싣지 않는다(그건 최종 턴에서 — turn.py). 여기선 렌더·레이턴시만.
"""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import ApiModel, ApiRequest, LatencyInfo


class DraftRequest(ApiRequest):
    """client → server: 타이핑 중 부분 입력."""

    revision_id: int = Field(ge=0, description="단조 증가. 서버는 stale를 drop")
    partial_text: str
    is_final: bool = False


class DraftResponse(ApiModel):
    """server → client: revision별 다중 타겟 렌더."""

    revision_id: int
    renderings: dict[str, str]  # lang → 번역
    committed_prefix_len: dict[str, int] = {}  # commit_prefix=false면 모두 0
    latency: LatencyInfo = LatencyInfo()


class DraftError(ApiModel):
    """server → client: 업스트림 오류(해당 revision)."""

    revision_id: int
    error: str
