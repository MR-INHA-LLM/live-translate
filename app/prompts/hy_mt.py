"""HY-MT1.5 프롬프트 전략.

언어쌍별로 지시문이 갈린다: zh가 source/target이면 중문 지시, 그 외는 영문 지시
(모델 카드 근거). 참조 구현 bench/prompts.py에서 이식.
"""

from __future__ import annotations

from app.domain import ChatMessage, Conversation, TranslationTask

# 타겟 언어의 영문 표기 ({target_language} 슬롯).
_LANG_EN: dict[str, str] = {
    "ko": "Korean", "en": "English", "id": "Indonesian", "zh": "Chinese",
    "vi": "Vietnamese", "th": "Thai", "ja": "Japanese", "ms": "Malay",
}
# 타겟 언어의 중문 표기 (zh 분기용).
_LANG_ZH: dict[str, str] = {"ko": "韩语", "en": "英语", "id": "印尼语", "zh": "中文"}


def _user_prompt(src: str, tgt: str, source: str) -> str:
    if src == "zh" or tgt == "zh":
        target = _LANG_ZH.get(tgt, tgt)
        return f"将以下文本翻译为{target}，注意只需要输出翻译后的结果，不要额外解释：\n\n{source}"
    target = _LANG_EN.get(tgt, tgt)
    return f"Translate the following segment into {target}, without additional explanation.\n\n{source}"


class HyMtPromptBuilder:
    """HY-MT 계열 PromptBuilder 구현. 기본 system prompt 없음 — user 메시지만."""

    def build(self, task: TranslationTask) -> list[ChatMessage]:
        """맥락 없는 단발 번역 프롬프트."""
        return [ChatMessage(role="user", content=_user_prompt(task.src_lang, task.tgt_lang, task.source))]

    def build_contextual(self, task: TranslationTask, ctx: Conversation) -> list[ChatMessage]:
        """직전 턴 컨텍스트를 중문 contextual template로 주입."""
        lines = [f"{t.source} → {t.translation}" for t in ctx.turns]
        context = "\n".join(lines)
        target = _LANG_ZH.get(task.tgt_lang, _LANG_EN.get(task.tgt_lang, task.tgt_lang))
        content = (
            f"{context}\n参考上面的信息，把下面的文本翻译成{target}，"
            f"注意不需要翻译上文，也不要额外解释：\n{task.source}\n"
        )
        return [ChatMessage(role="user", content=content)]
