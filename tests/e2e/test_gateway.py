"""E2E — 게이트웨이를 실제 HTTP로 구동해 REST·WS·SSE가 진짜 번역을 내는지 검증.

실제 vLLM draft(:8001)에 붙어 실번역을 확인한다(모킹 아님). 살아있는 명세.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import websockets

pytestmark = pytest.mark.asyncio


async def test_health(server: str) -> None:
    async with httpx.AsyncClient(base_url=server) as c:
        r = await c.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


async def test_languages_catalog(server: str) -> None:
    async with httpx.AsyncClient(base_url=server) as c:
        r = await c.get("/api/v1/languages")
        assert r.status_code == 200
        data = r.json()
        assert any(x["code"] == "ko" for x in data["languages"])
        assert any(p["src"] == "ko" and p["tgt"] == "id" and p["comet"] for p in data["validated_pairs"])


async def test_session_lifecycle_and_translation(server: str) -> None:
    async with httpx.AsyncClient(base_url=server, timeout=90) as c:
        # 1) 세션 생성 (ko → id, witness en)
        r = await c.post("/api/v1/sessions",
                         json={"src_lang": "ko", "tgt_lang": "id", "witness_langs": ["en"]})
        assert r.status_code == 201
        sid = r.json()["session_id"]

        # 2) 세션 조회
        r = await c.get(f"/api/v1/sessions/{sid}")
        assert r.status_code == 200
        assert r.json()["config"]["tgt_lang"] == "id"

        # 3) WS 초벌 — 실제 번역이 id·en 둘 다 오는지
        ws_url = server.replace("http", "ws") + f"/api/v1/sessions/{sid}/stream"
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "revision_id": 1,
                "partial_text": "내일 오후 회의를 금요일로 옮겨 주세요",
                "is_final": False,
            }))
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            assert msg["revision_id"] == 1
            assert len(msg["renderings"]["id"]) > 0
            assert len(msg["renderings"]["en"]) > 0
            print("\n  [WS draft] id:", msg["renderings"]["id"])
            print("  [WS draft] en:", msg["renderings"]["en"])

        # 4) SSE 최종 — token들 + done(실제 번역)
        final_translation = ""
        done_seen = False
        async with c.stream("POST", f"/api/v1/sessions/{sid}/turns",
                            json={"text": "주문번호는 A-2231이에요."}) as resp:
            assert resp.status_code == 200
            event = None
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: ") and event == "done":
                    final_translation = json.loads(line[6:])["translation"]
                    done_seen = True
        assert done_seen and len(final_translation) > 0
        print("  [SSE final]:", final_translation)
