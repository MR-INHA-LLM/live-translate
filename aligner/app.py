"""정렬 서비스 — awesome-align(사전학습) 기반 구 정렬 (별도 프로세스).

vLLM·COMET과 transformers/torch 버전이 충돌하므로(decisions.md D7) 게이트웨이와
분리된 프로세스로 띄운다(:8003, 호스트). 소스·번역을 어절 단위로 토큰화해 simalign
(`aneuraz/awesome-align-with-co`)으로 정렬하고 **문자 오프셋 스팬**으로 돌려준다.

턴 확정 시 1회만 호출된다(초벌 핫패스 아님, decisions.md D13).
"""

from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

logger = logging.getLogger("aligner")

_WORD = re.compile(r"\S+")
_PUNCT = re.compile(r"^[^\w가-힣]+$")  # 구두점만인 토큰(정렬 노이즈) 제거용

_state: dict[str, Any] = {}


def _words(text: str) -> list[tuple[str, int, int]]:
    """어절 + 문자 오프셋."""
    return [(m.group(), m.start(), m.end()) for m in _WORD.finditer(text)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """SentenceAligner를 1회 로드(가중치 로드 ~수초)."""
    from simalign import SentenceAligner

    logger.info("loading awesome-align model…")
    _state["aligner"] = SentenceAligner(
        model="aneuraz/awesome-align-with-co", token_type="bpe", matching_methods="i"
    )
    logger.info("aligner ready")
    yield
    _state.clear()


app = FastAPI(title="live-translate-aligner", lifespan=lifespan)


class AlignRequest(BaseModel):
    """정렬 요청 — 소스 원문 + 번역."""

    source: str = Field(min_length=1)
    translation: str = Field(min_length=1)


class Span(BaseModel):
    """소스 구 ↔ 번역 구 대응(문자 오프셋)."""

    src_start: int
    src_end: int
    tgt_start: int
    tgt_end: int


class AlignResponse(BaseModel):
    spans: list[Span]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok" if "aligner" in _state else "loading"}


@app.post("/align", response_model=AlignResponse)
async def align(req: AlignRequest) -> AlignResponse:
    """어절 정렬 → 문자 오프셋 스팬. 구두점만인 대응은 제외."""
    aligner = _state.get("aligner")
    if aligner is None:
        return AlignResponse(spans=[])
    src, tgt = _words(req.source), _words(req.translation)
    if not src or not tgt:
        return AlignResponse(spans=[])
    pairs = aligner.get_word_aligns([w for w, _, _ in src], [w for w, _, _ in tgt])["itermax"]
    spans: list[Span] = []
    for i, j in pairs:
        sw, ss, se = src[i]
        tw, ts, te = tgt[j]
        if _PUNCT.match(sw) or _PUNCT.match(tw):
            continue
        spans.append(Span(src_start=ss, src_end=se, tgt_start=ts, tgt_end=te))
    return AlignResponse(spans=spans)
