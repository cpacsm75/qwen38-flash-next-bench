#!/usr/bin/env python3
"""twostage_eval.py — '모르면 검색' 원칙 구현: 먼저 혼자 답하고, 불확실하면 조사 후 재답.

1단계: 도구 없이 답 + 확신도(high/medium/low)를 JSON 으로 받는다.
2단계: 확신도가 low 이거나 1단계 답이 없으면 → 조사(조사규정 RAG + 법령·판례 MCP + 웹검색) 후 재답.
채점은 최종답 기준. 1단계 답·확신도·조사여부도 함께 저장해 분석에 쓴다.

사용:
  ./twostage_eval.py http://127.0.0.1:8080 "<model>" out.json --set <set.json> [--threshold low|medium]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import difytool   # noqa: E402
import lawtool    # noqa: E402
import research_eval as R   # noqa: E402  (web_search, make_queries, post 재사용)


def ask(base, model, messages, args, extra=None):
    body = {"model": model, "messages": messages, "max_tokens": args.max_tokens,
            "temperature": 0, "reasoning_budget_tokens": args.reasoning_budget}
    if extra:
        body.update(extra)
    return R.post(base, body)


def parse_stage1(text, it):
    """{'answer': 'B', 'confidence': 'low'} 형태를 최대한 관대하게 파싱."""
    txt = text or ""
    conf = "medium"
    m = re.search(r"confidence\W{0,3}(high|medium|low|상|중|하)", txt, re.I)
    if m:
        c = m.group(1).lower()
        conf = {"상": "high", "중": "medium", "하": "low"}.get(c, c)
    ans = ""
    m = re.search(r"answer\W{0,3}[\"']?([ABCDE])", txt, re.I)
    if m:
        ans = m.group(1).upper()
    else:
        m = re.search(r"\b([ABCDE])\b", txt.upper())
        if m:
            ans = m.group(1)
        elif it["type"] == "free":
            m = re.search(r"answer\W{0,3}([^\n,\"}]+)", txt)
            ans = m.group(1).strip() if m else txt[:40]
    return ans, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
    ap.add_argument("--set", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--reasoning-budget", type=int, default=1024)
    ap.add_argument("--threshold", default="low", choices=["low", "medium"],
                    help="이 확신도 이하일 때만 조사한다")
    ap.add_argument("--no-web", action="store_true")
    ap.add_argument("--lbox", action="store_true", help="판례는 lbox 의미검색 사용(원문+id/오프셋)")
    ap.add_argument("--lbox-index", default="/data/models/lbox/index_corpus",
                    help="lbox 인덱스 접두어(기본: 판례 코퍼스 15만)")
    ap.add_argument("--min-year", type=int, default=2000, help="이 연도 이전 판례는 제외")
    ap.add_argument("--recency", type=float, default=0.05, help="최신성 가산점")
    args = ap.parse_args()

    items = json.loads(pathlib.Path(args.set).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    rank = {"low": 0, "medium": 1, "high": 2}
    out = []
    for i, it in enumerate(items, 1):
        q = it["q"]
        opts = "\n".join(f"{L}. {it[L]}" for L in "ABCDE" if L in it) if it["type"] == "mc" else ""
        stage1_prompt = (f"{q}\n\n{opts}\n\n" if opts else f"{q}\n\n") + \
            ('먼저 답을 정하고, 그 답에 대한 확신도를 함께 출력하라.\n'
             '형식(설명 없이 JSON 한 줄): {"answer": "B", "confidence": "high|medium|low"}\n'
             '확신이 없으면 반드시 "low" 로 표시하라.')
        t0 = time.time()
        try:
            d1 = ask(args.base, args.model,
                     [{"role": "system", "content": "너는 한국 법률·회계 실무자다. 모르면 모른다고 표시한다."},
                      {"role": "user", "content": stage1_prompt}], args)
            txt1 = d1["choices"][0]["message"].get("content") or ""
        except Exception as e:
            txt1 = f"(1단계 오류 {e})"
        ans1, conf = parse_stage1(txt1, it)
        need = rank[conf] <= rank[args.threshold]
        final, used = ans1, "stage1"
        ctx_chars = {}
        if need:
            queries = R.make_queries(args.base, args.model, q, args)
            regs = difytool.lookup(q[:300], 3)
            law = lawtool.lookup("law", queries["law"]) if queries.get("law") else ""
            if args.lbox:
                sys.path.insert(0, "/data/models/lbox")
                import lbox_search as L
                hits = L.search(args.lbox_index, q[:400], 2, min_year=args.min_year, recency=args.recency)
                prec = "\n\n".join(f"[판례 {h['doc']} @{h['off']}] {h['text'][:900]}" for h in hits)
            else:
                prec = lawtool.lookup("prec", queries["law"]) if queries.get("law") else ""
            web = "" if args.no_web else R.web_search(f"{queries.get('law','')} 판례")
            ctx_chars = {"regs": len(regs), "law": len(law), "prec": len(prec), "web": len(web)}
            ctx = (f"[조사자료 1] 조사규정(직무편람)\n{regs[:2500]}\n\n"
                   f"[조사자료 2] 법령 — 질의: {queries.get('law','')}\n{law[:2000]}\n\n"
                   f"[조사자료 3] 판례\n{prec[:2000]}\n\n"
                   f"[조사자료 4] 웹검색(신뢰 낮음)\n{web[:800]}")
            stage2 = (f"{q}\n\n{opts}\n\n" if opts else f"{q}\n\n") + "위 문제에 대해 아래 조사자료를 대조해 최종 답을 내라.\n" \
                      + ("객관식이면 보기 문자 하나만 출력." if it["type"] == "mc" else "요구된 값만 출력.")
            try:
                d2 = ask(args.base, args.model,
                         [{"role": "system", "content": "너는 한국 법률·회계 실무자다.\n\n" + ctx},
                          {"role": "user", "content": stage2}], args)
                final = (d2["choices"][0]["message"].get("content") or "").strip()
            except Exception as e:
                final = f"(2단계 오류 {e})"
            used = "researched"
        verdict = R.grade(it, final)
        el = time.time() - t0
        out.append({"id": it["id"], "type": it["type"], "verdict": verdict, "answer": it["a"],
                    "stage1": ans1, "confidence": conf, "used": used, "final": final[:120],
                    "ctx": ctx_chars, "secs": round(el, 1)})
        print(f"[{i}/{len(items)}] {it['id']:<24} {verdict:<4} conf={conf:<6} {used:<10} {el:5.1f}s",
              flush=True)
    pathlib.Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in out if r["verdict"] == "정답")
    rs = sum(1 for r in out if r["used"] == "researched")
    print(f"\n정답 {ok}/{len(out)} ({100*ok/len(out):.0f}%)  조사수행 {rs}건  "
          f"평균 {sum(r['secs'] for r in out)/len(out):.1f}s")


if __name__ == "__main__":
    main()
