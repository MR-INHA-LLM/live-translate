"""E2E 픽스처 — 게이트웨이를 실제 HTTP 포트에 띄운다.

vLLM draft 서버(:8001)가 떠 있어야 한다. 게이트웨이는 미사용 포트 18080에서 기동.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
PORT = 18080
BASE = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="session")
def server() -> str:
    """uvicorn 게이트웨이를 서브프로세스로 띄우고 /health 준비를 기다린다."""
    # E2E는 번역·저장 플로우를 검증한다(인증은 별도 단위 테스트 담당) → 서브프로세스에서
    # 인증을 끈다. 빈 env 변수가 .env의 API_KEYS/ADMIN_API_KEY 를 오버라이드(auth 비활성).
    # DB도 임시 파일로 격리 — 공유 ./data/app.db에 seed된 키가 auth를 켜지 않도록.
    tmp_db = Path(tempfile.mkdtemp()) / "e2e.db"
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(ROOT),
        env={
            **os.environ,
            "API_KEYS": "",
            "ADMIN_API_KEY": "",
            "DB_URL": f"sqlite+aiosqlite:///{tmp_db}",
        },
    )
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("gateway exited during startup")
            try:
                if httpx.get(f"{BASE}/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise RuntimeError("gateway did not become healthy")
        yield BASE
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
