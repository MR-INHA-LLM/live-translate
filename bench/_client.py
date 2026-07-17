"""Minimal OpenAI-compatible client for the vLLM draft endpoint.

Uses the chat/completions API so the server applies HY-MT's chat_template.jinja
(the special <｜hy_User｜> / <｜hy_Assistant｜> markers) for us.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import requests

BASE_URL = "http://127.0.0.1:8001/v1"
MODEL = "hy-mt1.5-1.8b"


@dataclass
class Timed:
    text: str
    ttft_ms: float | None
    total_ms: float
    n_tokens: int


def translate(user_prompt: str, *, max_tokens: int = 256, temperature: float = 0.0) -> str:
    """Non-streaming translate — greedy by default (draft-tier stability)."""
    r = requests.post(
        f"{BASE_URL}/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def translate_streaming(
    user_prompt: str, *, max_tokens: int = 256, temperature: float = 0.0
) -> Timed:
    """Streaming translate — measures TTFT (first token) and total wall time."""
    start = time.perf_counter()
    ttft_ms: float | None = None
    chunks: list[str] = []
    n = 0
    with requests.post(
        f"{BASE_URL}/chat/completions",
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        },
        stream=True,
        timeout=120,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break
            delta = json.loads(payload)["choices"][0]["delta"].get("content")
            if delta:
                if ttft_ms is None:
                    ttft_ms = (time.perf_counter() - start) * 1000
                chunks.append(delta)
                n += 1
    total_ms = (time.perf_counter() - start) * 1000
    return Timed("".join(chunks).strip(), ttft_ms, total_ms, n)


def wait_until_ready(timeout_s: float = 300.0) -> bool:
    """Poll /v1/models until the server answers."""
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            if requests.get(f"{BASE_URL}/models", timeout=3).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(2)
    return False
