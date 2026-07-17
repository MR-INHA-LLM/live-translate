"""HY-MT1.5 prompt templates.

Source of truth: tencent/HY-MT1.5-1.8B model card, section "Prompts".
The template BRANCHES on whether Chinese is source or target:

- ZH<=>XX  -> Chinese instruction
- XX<=>XX  -> English instruction  (all of ko/en/id pairs land here)

The model has NO default system prompt: every instruction goes in the user turn.
"""

from __future__ import annotations

# English display names required by the {target_language} slot.
LANG_NAMES: dict[str, str] = {
    "ko": "Korean",
    "en": "English",
    "id": "Indonesian",
    "zh": "Chinese",
    "vi": "Vietnamese",
    "th": "Thai",
    "ja": "Japanese",
}

# Chinese display names for the ZH-branch template.
LANG_NAMES_ZH: dict[str, str] = {
    "ko": "韩语",
    "en": "英语",
    "id": "印尼语",
    "zh": "中文",
}


def build_user_prompt(src_lang: str, tgt_lang: str, source_text: str) -> str:
    """Return the raw user-turn content for a plain (non-contextual) translation."""
    if src_lang == "zh" or tgt_lang == "zh":
        target = LANG_NAMES_ZH.get(tgt_lang, tgt_lang)
        return (
            f"将以下文本翻译为{target}，注意只需要输出翻译后的结果，不要额外解释：\n\n"
            f"{source_text}"
        )
    target = LANG_NAMES.get(tgt_lang, tgt_lang)
    return (
        f"Translate the following segment into {target}, without additional explanation.\n\n"
        f"{source_text}"
    )


def build_contextual_prompt(
    src_lang: str, tgt_lang: str, source_text: str, context: str
) -> str:
    """Contextual-translation template (Chinese instruction form, per model card)."""
    target = LANG_NAMES_ZH.get(tgt_lang, LANG_NAMES.get(tgt_lang, tgt_lang))
    return (
        f"{context}\n"
        f"参考上面的信息，把下面的文本翻译成{target}，注意不需要翻译上文，也不要额外解释：\n"
        f"{source_text}\n"
    )
