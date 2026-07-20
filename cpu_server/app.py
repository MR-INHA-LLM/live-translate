"""CPU draft 서버 — OpenAI 호환 최소 서버 (transformers). GPU 없는 환경용.

vLLM CUDA 이미지는 CPU 서빙이 안 되므로, GPU-less 배포에서는 초벌(draft) tier만 이
경량 서버로 CPU에서 돌린다. quality tier는 미가용 → 게이트웨이가 자동 degrade한다
(버블은 단일 "번역" 줄). 게이트웨이의 OpenAI 클라이언트가 쓰는 최소 엔드포인트만 구현:
`GET /v1/models`, `POST /v1/chat/completions`(SSE 스트림). logprobs는 draft에 불필요.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("cpu_draft")

MODEL_PATH = os.environ.get("DRAFT_MODEL_PATH", "models/HY-MT1.5-1.8B")
SERVED = os.environ.get("SERVED_MODEL_NAME", "hy-mt1.5-1.8b")
MAX_NEW_CAP = int(os.environ.get("MAX_NEW_TOKENS", "256"))

_state: dict[str, Any] = {}
# CPU 단일 모델은 동시 generate가 서로 충돌하므로 한 번에 하나만 생성(직렬화).
_gen_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("loading draft model on CPU: %s", MODEL_PATH)
    tok = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH, trust_remote_code=True, dtype=torch.float32
    ).to("cpu").eval()
    _state.update(tok=tok, model=model, torch=torch)
    logger.info("cpu draft ready (served as %s)", SERVED)
    yield
    _state.clear()


app = FastAPI(title="live-translate-cpu-draft", lifespan=lifespan)


class ChatRequest(BaseModel):
    """OpenAI chat/completions 요청(필요한 필드만, 나머지는 무시)."""

    model_config = {"extra": "ignore"}
    model: str
    messages: list[dict]
    max_tokens: int = 256
    temperature: float = 0.0
    stream: bool = False


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok" if "model" in _state else "loading"}


@app.get("/v1/models")
async def models() -> dict[str, Any]:
    return {"object": "list", "data": [{"id": SERVED, "object": "model"}]}


def _chunk(delta: dict, finish: str | None) -> str:
    payload = {"object": "chat.completion.chunk", "model": SERVED,
               "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest) -> StreamingResponse:
    """chat 메시지를 CPU에서 번역 생성해 OpenAI SSE로 스트리밍한다.

    sse()는 **sync 제너레이터**라 Starlette가 threadpool에서 돌린다(이벤트 루프
    블로킹 방지). 생성은 `_gen_lock`으로 직렬화(CPU 단일 모델 동시성 충돌 방지).
    """
    from transformers import TextIteratorStreamer

    tok, model = _state["tok"], _state["model"]
    enc = tok.apply_chat_template(req.messages, add_generation_prompt=True, return_tensors="pt")
    ids = enc["input_ids"] if hasattr(enc, "keys") else enc
    max_new = min(req.max_tokens, MAX_NEW_CAP)

    def sse():
        with _gen_lock:  # 한 번에 하나만 생성(요청은 큐잉)
            streamer = TextIteratorStreamer(tok, skip_prompt=True, skip_special_tokens=True)
            kwargs = dict(
                input_ids=ids, max_new_tokens=max_new, do_sample=False,
                streamer=streamer, pad_token_id=tok.eos_token_id,
            )

            def _generate() -> None:
                # 예외로 죽어도 streamer를 반드시 끝내야 for-loop가 풀린다(데드락 방지).
                try:
                    model.generate(**kwargs)
                except Exception:
                    logger.exception("generate failed")
                    streamer.end()

            threading.Thread(target=_generate, daemon=True).start()
            yield _chunk({"role": "assistant"}, None)
            for text in streamer:
                if text:
                    yield _chunk({"content": text}, None)
            yield _chunk({}, "stop")
            yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
