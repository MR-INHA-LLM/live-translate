"""도메인 값객체 (@dataclass, frozen).

직렬화·전송 관심사가 없는 순수 객체. API 경계 스키마(schemas/)와 분리한다
(python-standards §7.3). 서비스·어댑터 사이에서 오간다.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum


class Tier(str, Enum):
    """번역 tier 구분."""

    DRAFT = "draft"
    QUALITY = "quality"


@dataclass(frozen=True)
class ChatMessage:
    """OpenAI 호환 chat 메시지 (role/content)."""

    role: str
    content: str


@dataclass(frozen=True)
class TranslationTask:
    """한 번역 단위 — 소스 텍스트를 한 언어쌍으로."""

    src_lang: str
    tgt_lang: str
    source: str


@dataclass(frozen=True)
class EngineRequest:
    """엔진(vLLM)에 보내는 스트리밍 번역 요청."""

    model: str
    messages: list[ChatMessage]
    temperature: float = 0.0
    max_tokens: int = 256


@dataclass(frozen=True)
class TokenChunk:
    """스트림에서 오는 토큰 조각. 첫 조각만 ttft_ms를 채운다."""

    text: str
    logprob: float | None = None  # 모델 신뢰도(QE 색상 파생). logprobs=true 요청 시 채움.
    ttft_ms: float | None = None


@dataclass(frozen=True)
class EngineHealth:
    """엔진 도달성·로드 상태."""

    tier: Tier
    reachable: bool
    loaded_model: str | None = None


@dataclass(frozen=True)
class Rendering:
    """한 타겟 언어의 번역 결과 (초벌/최종 공통 값객체)."""

    lang: str
    text: str
    committed_prefix_len: int = 0


@dataclass(frozen=True)
class Revision:
    """타이핑 중 부분 입력 한 건."""

    id: int
    partial_text: str
    is_final: bool = False


@dataclass(frozen=True)
class RevisionUpdate:
    """한 revision에 대한 초벌 결과 — 여러 타겟 렌더 + 지연."""

    revision_id: int
    renderings: dict[str, Rendering]
    ttft_ms: float | None = None
    total_ms: float | None = None
    cached: bool = False


@dataclass(frozen=True)
class ConversationTurn:
    """컨텍스트 조립용 과거 턴 (이중언어)."""

    source: str
    translation: str


@dataclass(frozen=True)
class Conversation:
    """직전 N턴 컨텍스트."""

    turns: list[ConversationTurn] = field(default_factory=list)


@dataclass(frozen=True)
class Session:
    """세션 애그리거트 루트 — 라우팅에 필요한 확정 필드만 담는다.

    API의 SessionConfig(schemas)를 서비스가 이 순수 도메인 객체로 매핑한다
    (도메인은 스키마·프레임워크를 import하지 않는다).
    """

    id: str
    src_lang: str
    tgt_lang: str
    witness_langs: list[str]
    draft_model: str
    quality_model: str

    def target_langs(self) -> list[str]:
        """tgt + witness (중복·src 제거, 순서 유지)."""
        out: list[str] = []
        for lang in [self.tgt_lang, *self.witness_langs]:
            if lang != self.src_lang and lang not in out:
                out.append(lang)
        return out


@dataclass(frozen=True)
class Turn:
    """확정 문장 한 턴 (엔티티). 세션을 통해서만 추가된다."""

    turn_id: int
    source: str
    draft: dict[str, str]
    final: str | None = None


# 코디네이터가 초벌 업데이트를 밖으로 흘려보내는 콜백 타입.
UpdateSink = Callable[[RevisionUpdate], Awaitable[None]]
