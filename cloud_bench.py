#!/usr/bin/env python3
"""cloud_bench.py — 클라우드 Raon API 를 로컬 측정과 같은 조건으로 채점한다.

eval_runner.py 와 동일한 시스템 프롬프트(SYS_MC)·temperature 0 을 쓰고,
응답 시간·토큰·추론토큰을 함께 기록해 로컬 모델과 비교할 수 있게 한다.

사용:
  ./cloud_bench.py out.json --set moj/eval_set_moj_2026-11-12.json [--limit N]
키는 ~/.hermes/config.yaml 의 model_aliases.raon-cloud.api_key 에서 읽는다.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
import urllib.request

import yaml

URL = "https://raon-api.krafton.ai/v1/chat/completions"
MODEL = "raon-1-mini-preview"
SYS_MC = ("너는 한국인 공인회계사(KICPA)다. 모든 답변은 근거를 바탕으로 한국어 문법에 맞게 작성한다. "
          "한국어 객관식 문제다. 정답 보기의 문자 하나(A/B/C/D)만 출력하라. 다른 텍스트 금지.")


def key() -> str:
    cfg = yaml.safe_load(open(pathlib.Path.home() / ".hermes/config.yaml"))
    return cfg["model_aliases"]["raon-cloud"]["api_key"]


def norm(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()


def grade(it, content: str) -> str:
    c = (content or "").strip()
    if not c:
        return "무응답"
    if it["type"] == "mc":
        m = re.search(r"\b([ABCDE])\b", c.upper()) or re.search(r"([ABCDE])(?:[\.\)]|$)", c.upper())
        return ("정답" if m.group(1) == it["a"] else "오답") if m else "무응답"
    if it["a"] == "없음":
        return "정답" if "없음" in c else "오답"
    return "정답" if norm(it["a"]) and norm(it["a"]) in norm(c) else "오답"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--set", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=2048)
    args = ap.parse_args()

    K = key()
    items = json.loads(pathlib.Path(args.set).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    res = []
    for i, it in enumerate(items, 1):
        if it["type"] == "mc":
            opts = "\n".join(f"{L}. {it[L]}" for L in "ABCDE" if L in it)
            prompt = f"{it['q']}\n\n{opts}\n\n정답 문자만 출력:"
        else:
            prompt = it["q"]
        body = json.dumps({"model": MODEL,
                           "messages": [{"role": "system", "content": SYS_MC},
                                        {"role": "user", "content": prompt}],
                           "max_completion_tokens": args.max_tokens, "temperature": 0}).encode()
        req = urllib.request.Request(URL, data=body,
                                     headers={"Authorization": f"Bearer {K}",
                                              "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.load(r)
            content = (d["choices"][0]["message"]["content"] or "").strip()
            us = d.get("usage") or {}
        except Exception as e:
            content, us = f"(오류 {e})", {}
        el = time.time() - t0
        v = grade(it, content)
        res.append({"id": it["id"], "verdict": v, "answer": it["a"], "content": content[:120],
                    "secs": round(el, 1), "completion_tokens": us.get("completion_tokens"),
                    "reasoning_tokens": (us.get("completion_tokens_details") or {}).get("reasoning_tokens")})
        print(f"[{i}/{len(items)}] {it['id']:<24} {v:<4} {el:5.1f}s "
              f"tok={res[-1]['completion_tokens']} reason={res[-1]['reasoning_tokens']}", flush=True)
    pathlib.Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in res if r["verdict"] == "정답")
    print(f"\n정답 {ok}/{len(res)} ({100*ok/len(res):.0f}%)  평균 {sum(r['secs'] for r in res)/len(res):.1f}s")


if __name__ == "__main__":
    main()
