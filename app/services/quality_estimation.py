"""단어 수준 품질추정(QE) — 토큰 logprob → 신뢰도 스팬 (순수, I/O 없음).

모델이 스스로 낸 토큰 확률(logprob)을 단어 단위로 묶어 신뢰도를 만든다. 품질의
증명이 아니라 **모델 자신의 확신도**다(decisions.md D11/D13). 불확실 구간만 amber로
칠하도록 `low` 플래그를 둔다 — 다 초록으로 칠하면 거짓 신뢰(정직성 가드).
"""

from __future__ import annotations

import math
import re

from app.schemas.common import ConfidenceSpan

# 이 확률 미만이면 불확실(amber). MT 토큰은 보통 0.8~0.99라 0.40이면 눈에 띄는 것만.
LOW_PROB_THRESHOLD = 0.40

_WORD = re.compile(r"\S+")


def build_confidence_spans(
    tokens: list[tuple[int, int, float | None]], text: str, threshold: float = LOW_PROB_THRESHOLD
) -> list[ConfidenceSpan]:
    """토큰 (start, end, logprob) 목록 → 단어 단위 신뢰도 스팬.

    각 단어(공백 구분)에 걸치는 토큰들의 확률 기하평균을 신뢰도로 삼는다. logprob가
    없는 토큰은 건너뛴다. 단어에 확률 정보가 하나도 없으면 스팬을 만들지 않는다.

    Args:
        tokens: 최종 번역 문자열 기준 (문자 시작, 끝, logprob) 목록.
        text: 최종 번역 문자열.
        threshold: 이 확률 미만이면 low=True.
    """
    spans: list[ConfidenceSpan] = []
    for m in _WORD.finditer(text):
        ws, we = m.start(), m.end()
        probs = [
            math.exp(lp)
            for (ts, te, lp) in tokens
            if lp is not None and ts < we and te > ws  # 단어와 겹치는 토큰
        ]
        if not probs:
            continue
        geo = math.exp(sum(math.log(p) for p in probs) / len(probs))
        geo = max(0.0, min(1.0, geo))
        spans.append(ConfidenceSpan(tgt_start=ws, tgt_end=we, prob=geo, low=geo < threshold))
    return spans
