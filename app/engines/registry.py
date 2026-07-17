"""모델 레지스트리 — served-model-name → 엔진·프롬프트·tier 바인딩.

모델 교체는 컴포지션 루트에서 등록 변경만으로 끝난다(OCP).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain import Tier
from app.engines.base import TranslationEngine
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class EngineBinding:
    """한 모델에 묶인 엔진 + 프롬프트 전략 + tier."""

    engine: TranslationEngine
    prompt_builder: PromptBuilder
    tier: Tier


class ModelRegistry:
    """모델 이름으로 바인딩을 찾는다 (plumbing)."""

    def __init__(self) -> None:
        self._bindings: dict[str, EngineBinding] = {}

    def register(
        self,
        model: str,
        engine: TranslationEngine,
        prompt_builder: PromptBuilder,
        tier: Tier,
    ) -> None:
        """모델 → 바인딩을 등록한다."""
        self._bindings[model] = EngineBinding(engine, prompt_builder, tier)

    def resolve(self, model: str) -> EngineBinding:
        """등록된 바인딩을 반환한다.

        Raises:
            KeyError: 미등록 모델.
        """
        return self._bindings[model]
