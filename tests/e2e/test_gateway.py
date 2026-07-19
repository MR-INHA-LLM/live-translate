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


async def test_conversation_store_crud(server: str) -> None:
    """대화 저장소: 생성→메시지 추가→목록→복원→404. (vLLM 불필요, 순수 DB)"""
    async with httpx.AsyncClient(base_url=server, timeout=30) as c:
        r = await c.post("/api/v1/conversations",
                         json={"src_lang": "ko", "tgt_lang": "en", "witness_lang": "en"})
        assert r.status_code == 201
        cid = r.json()["conversation_id"]

        # 양측 메시지 추가 — seq 자동 부여. 초벌·검증·소요시간까지 왕복 보존.
        r = await c.post(f"/api/v1/conversations/{cid}/messages",
                         json={"side": "mine", "source": "안녕하세요", "translation": "Hello",
                               "draft": "Hi", "witness": "Halo", "round_trip": "안녕",
                               "confidence": [{"tgt_start": 0, "tgt_end": 5, "prob": 0.9, "low": False}],
                               "draft_ms": 210.5, "final_ms": 1850.0, "round_trip_ms": 90.0})
        assert r.status_code == 201 and r.json()["seq"] == 0
        assert r.json()["draft"] == "Hi" and r.json()["draft_ms"] == 210.5
        assert r.json()["round_trip"] == "안녕" and r.json()["confidence"][0]["prob"] == 0.9
        r = await c.post(f"/api/v1/conversations/{cid}/messages",
                         json={"side": "theirs", "source": "Can you help?",
                               "translation": "도와주실 수 있나요?"})
        assert r.status_code == 201 and r.json()["seq"] == 1

        # 목록: 제목=첫 메시지, 카운트=2
        r = await c.get("/api/v1/conversations")
        assert r.status_code == 200
        mine = next(x for x in r.json() if x["conversation_id"] == cid)
        assert mine["message_count"] == 2 and mine["title"] == "안녕하세요"

        # 복원: 순서·측면·번역 보존
        r = await c.get(f"/api/v1/conversations/{cid}")
        assert r.status_code == 200
        msgs = r.json()["messages"]
        assert [m["side"] for m in msgs] == ["mine", "theirs"]
        assert msgs[1]["translation"] == "도와주실 수 있나요?"
        assert msgs[0]["draft"] == "Hi" and msgs[0]["witness"] == "Halo"
        assert msgs[0]["draft_ms"] == 210.5 and msgs[0]["final_ms"] == 1850.0
        assert msgs[0]["round_trip"] == "안녕" and msgs[0]["round_trip_ms"] == 90.0
        assert msgs[0]["confidence"][0]["low"] is False

        # 삭제 → 목록에서 사라지고, 재조회 404
        assert (await c.delete(f"/api/v1/conversations/{cid}")).status_code == 204
        assert (await c.get(f"/api/v1/conversations/{cid}")).status_code == 404
        assert all(x["conversation_id"] != cid for x in (await c.get("/api/v1/conversations")).json())

        # 없는 대화 → 404 (조회·삭제 모두)
        assert (await c.get("/api/v1/conversations/nope")).status_code == 404
        assert (await c.delete("/api/v1/conversations/nope")).status_code == 404


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
