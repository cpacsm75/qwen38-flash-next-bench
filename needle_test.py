#!/usr/bin/env python3
"""장문맥 실동작 확인 — 바늘(needle) 찾기. 토큰 수를 실측 보정해서 프롬프트를 만든다.

사용: needle_test.py <model_id> <target_tokens> [out.json]
"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8080"
MODEL = sys.argv[1]
TARGET = int(sys.argv[2])
OUT = sys.argv[3] if len(sys.argv) > 3 else None

FILLER = ("채무자 회생 절차에서 시인·부인 판단은 채권의 실체 관계에 따라 이루어진다. "
          "관리인은 채권 신고 내역과 장부를 대조하여 시인 여부를 결정하고, 이의가 있으면 조사보고서에 기재한다. ")
NEEDLE = "\n\n[중요] 이 사건의 공동관리인은 박영희이며, 배당 예정일은 2027년 3월 15일이다.\n\n"
QUESTION = "위 문서에서 공동관리인의 이름과 배당 예정일을 정확히 답하라. 형식: 이름 / 날짜"


def ask(text, max_tokens=8):
    body = {"model": MODEL, "messages": [{"role": "user", "content": text}],
            "max_tokens": max_tokens, "temperature": 0, "reasoning_budget_tokens": 32}
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=3600))
    return d, time.time() - t0


# 1) 보정: 20회 반복의 실제 토큰 수를 잰다
CAL = 20
d, _ = ask(FILLER * CAL, max_tokens=1)
tokens_per_rep = (d["usage"]["prompt_tokens"] - 8) / CAL   # 프롬프트 머리 오버헤드 대략 제외
n_repeat = max(1, int(TARGET / tokens_per_rep))
print(f"[cal] {tokens_per_rep:.1f} 토큰/회 -> {n_repeat}회 반복 (목표 {TARGET})", flush=True)

half = n_repeat // 2
body_text = FILLER * half + NEEDLE + FILLER * (n_repeat - half)

# 2) 본 측정
d, el = ask(body_text + "\n\n" + QUESTION, max_tokens=256)
m = d["choices"][0]["message"]
u = d.get("usage") or {}
ans = (m.get("content") or "").strip()
row = {"model": MODEL, "target": TARGET, "prompt_tokens": u.get("prompt_tokens"),
       "completion_tokens": u.get("completion_tokens"), "secs": round(el, 1),
       "prefill_tok_s": round((u.get("prompt_tokens") or 0) / el, 0) if el else 0,
       "answer": ans[:200],
       "needle_found": ("박영희" in ans) and ("2027" in ans)}
print(json.dumps(row, ensure_ascii=False, indent=1))
if OUT:
    json.dump(row, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
