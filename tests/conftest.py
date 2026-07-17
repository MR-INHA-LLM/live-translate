"""E2E 픽스처 — 게이트웨이를 실제 HTTP 포트에 띄운다.

vLLM draft 서버(:8001)가 떠 있어야 한다. 게이트웨이는 미사용 포트 18080에서 기동.
"""

from __future__ import annotations

import subprocess
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
    proc = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(ROOT),
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
