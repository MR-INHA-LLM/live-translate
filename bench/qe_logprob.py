"""목업 QE 실측 — 모델 token logprob → 단어별 신뢰도.

목업의 exact 입력을 logprobs=true로 재생성 → 서브워드를 단어로 합쳐 단어별 확률
계산 → green/amber 임계 분류. 결과를 목업 QE 색에 그대로 반영한다.
"""

from __future__ import annotations

import math

import requests

URL = "http://127.0.0.1:8001/v1/chat/completions"
SRC = "내일 오후 회의를 취소하고 금요일로 옮겨 주세요."
PROMPT = (
    "Translate the following segment into Indonesian, without additional "
    f"explanation.\n\n{SRC}"
)
GOOD_P = 0.55  # 단어 확률 임계 (이상이면 green)


def main() -> None:
    r = requests.post(URL, json={
        "model": "hy-mt1.5-1.8b",
        "messages": [{"role": "user", "content": PROMPT}],
        "temperature": 0, "max_tokens": 64, "logprobs": True, "top_logprobs": 1,
    }, timeout=60)
    r.raise_for_status()
    choice = r.json()["choices"][0]
    print("번역:", choice["message"]["content"])
    toks = choice["logprobs"]["content"]

    # 서브워드 → 단어 (공백 시작 토큰 = 새 단어)
    words: list[list[dict]] = []
    for t in toks:
        if t["token"].startswith(" ") and words:
            words.append([t])
        elif not words:
            words.append([t])
        else:
            words[-1].append(t)

    print(f"\n{'단어':<16}{'p(geomean)':>11}  QE")
    print("-" * 36)
    for w in words:
        text = "".join(t["token"] for t in w).strip()
        if not text or not any(c.isalnum() for c in text):
            continue  # 구두점 스킵
        mean_lp = sum(t["logprob"] for t in w) / len(w)
        p = math.exp(mean_lp)
        qe = "qe-good" if p >= GOOD_P else "qe-warn"
        print(f"{text:<16}{p:>11.2f}  {qe}")


if __name__ == "__main__":
    main()
