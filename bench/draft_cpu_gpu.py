"""Draft 모델(HY-MT1.5-1.8B) GPU vs CPU 지연 실측.

같은 엔진(transformers)으로 device만 바꿔 공정 비교한다. 짧은/긴 문장 각각 greedy로
번역 생성해 총 지연·출력 토큰·tok/s를 잰다. GPU=fp16, CPU=fp32(실배포 기준).
"""

from __future__ import annotations

import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL = "models/HY-MT1.5-1.8B"
REPS = 3

SHORT = "회의 자료 금요일까지 보내주세요"
LONG = (
    "안녕하세요, 어제 문의드린 주문번호 A-2231 건에 대해 확인 부탁드립니다. "
    "제품이 배송 중에 파손되어 도착했는데, 환불이나 교환이 가능한지 그리고 "
    "처리까지 얼마나 걸리는지 알려주시면 감사하겠습니다."
)


def prompt(src: str) -> str:
    return f"Translate the following segment into English, without additional explanation.\n\n{src}"


def run(device: str, dtype: torch.dtype) -> None:
    print(f"\n=== device={device} dtype={dtype} ===")
    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL, trust_remote_code=True, dtype=dtype)
    model.to(device).eval()

    for label, text in [("짧은 문장", SHORT), ("긴 문장", LONG)]:
        msgs = [{"role": "user", "content": prompt(text)}]
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
        ids = (enc["input_ids"] if hasattr(enc, "keys") else enc).to(device)
        in_tok = ids.shape[1]
        max_new = min(len(text) * 3 + 32, 256)

        # 워밍업
        with torch.no_grad():
            model.generate(ids, max_new_tokens=max_new, do_sample=False,
                           pad_token_id=tok.eos_token_id)

        lat, out_tok = [], 0
        for _ in range(REPS):
            if device == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            with torch.no_grad():
                out = model.generate(ids, max_new_tokens=max_new, do_sample=False,
                                     pad_token_id=tok.eos_token_id)
            if device == "cuda":
                torch.cuda.synchronize()
            lat.append((time.perf_counter() - t0) * 1000)
            out_tok = out.shape[1] - in_tok
        med = sorted(lat)[len(lat) // 2]
        text_out = tok.decode(out[0, in_tok:], skip_special_tokens=True).strip()
        print(f"  [{label}] in={in_tok}tok out={out_tok}tok  중앙지연={med:7.0f}ms  "
              f"{out_tok / (med / 1000):5.1f} tok/s")
        print(f"      → {text_out[:70]}")

    del model
    if device == "cuda":
        torch.cuda.empty_cache()


if __name__ == "__main__":
    if torch.cuda.is_available():
        run("cuda", torch.float16)
    else:
        print("CUDA 불가 — GPU 측정 건너뜀")
    run("cpu", torch.float32)
