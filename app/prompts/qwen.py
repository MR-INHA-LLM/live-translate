"""Qwen 계열 프롬프트 전략 (quality tier — Qwen3-4B-Instruct).

Pombal et al.(TACL 2026) *A Context-aware Framework for Translation-mediated
Conversations* 의 context-augmented 방식을 따른다:

- 컨텍스트는 직전 턴들의 **원문**(x_<t)을 순서대로 프롬프트 앞에 prepend한다.
  번역문이 아닌 원문을 넣어 대화의 holistic view를 유지하고 대명사·생략·모호성을
  해소한다(논문 §3.1). 화자 역할·메타데이터는 넣지 않는 미니멀 구성.
- 현재 세그먼트만 target 언어로 번역하고 설명은 출력하지 않는다.
"""

from __future__ import annotations

from app.domain import ChatMessage, TranslationTask

_LANG_EN: dict[str, str] = {
    "ko": "Korean", "en": "English", "id": "Indonesian", "zh": "Chinese",
    "vi": "Vietnamese", "th": "Thai", "ja": "Japanese", "ms": "Malay",
}


def _name(code: str) -> str:
    return _LANG_EN.get(code, code)


class QwenPromptBuilder:
    """Qwen 계열 PromptBuilder — context-aware(Pombal) 최종 번역."""

    def _system(self, task: TranslationTask) -> ChatMessage:
        return ChatMessage(
            role="system",
            content=(
                f"You are a professional translator for a live, two-party conversation "
                f"between a {_name(task.src_lang)} speaker and a {_name(task.tgt_lang)} speaker. "
                f"Translate the user's latest message from {_name(task.src_lang)} into "
                f"{_name(task.tgt_lang)}. Use the conversation so far to resolve pronouns, "
                f"ellipsis, honorifics, and domain terms so the translation is natural and "
                f"context-appropriate. Output only the translation — no explanations, no quotes, "
                f"no source text."
            ),
        )

    def build(self, task: TranslationTask) -> list[ChatMessage]:
        """맥락 없는 단발 번역 프롬프트."""
        return [self._system(task), ChatMessage(role="user", content=task.source)]

    def build_contextual(self, task: TranslationTask, context: list[str]) -> list[ChatMessage]:
        """직전 턴 원문 순서열을 컨텍스트로 prepend한 최종 번역 프롬프트."""
        history = "\n".join(context)
        user = (
            "Conversation so far (each line is one message, in its original language):\n"
            f"{history}\n\n"
            f"Now translate only this latest message into {_name(task.tgt_lang)}:\n"
            f"{task.source}"
        )
        return [self._system(task), ChatMessage(role="user", content=user)]
