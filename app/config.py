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

    # 공개 API 키 인증 — 쉼표구분 목록. 비우면 인증 비활성(개발/데모).
    # 외부 공개 시 `API_KEYS=key1,key2`로 설정하면 /api/v1/* 에 X-API-Key 요구.
    api_keys: str = ""

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    # tier별 vLLM (OpenAI 호환) 엔드포인트
    draft_url: str = "http://127.0.0.1:8001/v1"
    quality_url: str = "http://127.0.0.1:8002/v1"
    align_url: str = "http://127.0.0.1:8003"  # awesome-align 정렬 서비스(별도 프로세스)
    draft_model: str = "hy-mt1.5-1.8b"
    quality_model: str = "qwen3-4b-instruct"
    # HY-MT1.5 공식 generation_config/README가 명시하는 기본 반복 페널티.
    # 실측(A/B): 지연 오버헤드 ≈0, 충실한 반복 번역 무손상 통과, 1.5/2.0은 문법 왜곡 →
    # 1.05가 공식이 고른 안전 기본값임을 확인. 관측된 루프 수정이 아니라 tail-risk 보험 +
    # 공식 config 정합. draft(HY-MT) 엔진에만 적용(Qwen quality는 자체 권장값), extra_body 전달.
    draft_repetition_penalty: float = 1.05
    # CPU 배포 등에서 quality tier를 끈다 → 최종을 draft로 처리(degraded), 버블 단일 줄.
    quality_enabled: bool = True

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
