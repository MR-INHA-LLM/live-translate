"""애플리케이션 설정 (pydantic-settings).

시크릿·환경 의존 값은 전부 여기로 모으고 .env에서 바인딩한다(하드코딩 금지).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수로 주입되는 게이트웨이 설정.

    `.env` 또는 프로세스 환경에서 읽는다. 필드명 대문자가 env 키.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "live-translate"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    # tier별 vLLM (OpenAI 호환) 엔드포인트
    draft_url: str = "http://127.0.0.1:8001/v1"
    quality_url: str = "http://127.0.0.1:8002/v1"
    draft_model: str = "hy-mt1.5-1.8b"
    quality_model: str = "qwen3-4b-instruct"

    # 저장 (SQLite 영속 — decisions.md D9)
    db_url: str = "sqlite+aiosqlite:///./data/app.db"

    # 결정성 캐시 (인메모리 LRU — decisions.md D10)
    cache_max_entries: int = 2048

    # 백프레셔: tier당 게이트웨이→vLLM 동시 요청 상한 (decisions.md D12)
    engine_max_concurrency: int = 8

    # 세션 기본값 (양방향 선택기 기본 쌍: ko ⇄ en)
    default_src_lang: str = "ko"
    default_tgt_lang: str = "en"
    default_witness_langs: list[str] = ["en"]
    default_debounce_ms: int = 200

    # 최종 컨텍스트(Pombal TACL 2026) 예산 — 6~10턴이면 대부분 충분(논문 §6.1)
    context_turns: int = 10
    context_token_budget: int = 1024
