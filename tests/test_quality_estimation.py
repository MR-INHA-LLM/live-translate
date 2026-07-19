"""build_confidence_spans 단위 테스트 (순수 함수, 서버 불필요)."""

from __future__ import annotations

import math

from app.services.quality_estimation import build_confidence_spans


def test_word_level_spans_and_low_flag() -> None:
    text = "Hi there"
    # "Hi"(0-2) 고신뢰, "there"(3-8) 저신뢰
    tokens = [(0, 2, math.log(0.95)), (2, 3, math.log(0.99)), (3, 8, math.log(0.20))]
    spans = build_confidence_spans(tokens, text, threshold=0.40)
    assert len(spans) == 2
    hi, there = spans
    assert (hi.tgt_start, hi.tgt_end) == (0, 2) and not hi.low
    assert (there.tgt_start, there.tgt_end) == (3, 8) and there.low
    assert abs(there.prob - 0.20) < 1e-6


def test_tokens_without_logprob_skipped() -> None:
    # logprob 없는 단어는 스팬을 만들지 않는다.
    spans = build_confidence_spans([(0, 4, None)], "word")
    assert spans == []


def test_geometric_mean_over_subwords() -> None:
    # 한 단어에 걸친 두 서브워드 확률의 기하평균.
    text = "reschedule"
    tokens = [(0, 2, math.log(0.9)), (2, 10, math.log(0.4))]
    (span,) = build_confidence_spans(tokens, text)
    assert abs(span.prob - math.sqrt(0.9 * 0.4)) < 1e-6
