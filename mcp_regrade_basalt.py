#!/usr/bin/env python3
"""basalt 도구호출 결과를 의미 기준으로 재채점.

정확일치 채점(mcp_eval.py)은 단위·조문 표기 차이를 오답으로 만든다.
  - t1: 검색어에 요청 문구가 포함되면 정답
  - t3: 세 인자가 모두 10,000배 관계(만원 단위)면 정답
  - t4: article 의 숫자만 비교
사용: ./mcp_regrade_basalt.py mcp_<tag>.json
"""
import json
import re
import sys

EXPECT = {
    "t1_law": {"name": "search_law", "query": "임차보증금 우선변제권"},
    "t2_sheet": {"name": "read_sheet", "path": "/data/2026회합1005.xlsx", "sheet": "시부인표"},
    "t3_dividend": {"name": "compute_dividend", "available": 12000000, "total": 48000000, "claim": 8000000},
    "t4_multi": {"name": "search_law", "article": "179"},
    "t5_read": {"name": "read_sheet", "path": "/data/report.xlsx", "sheet": "경제성조사", "max_rows": 100},
}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def judge(cid, args):
    exp = EXPECT[cid]
    if cid == "t1_law":
        q = str(args.get("query", ""))
        return exp["query"] in q or q in exp["query"]
    if cid == "t4_multi":
        got = re.sub(r"[^0-9]", "", str(args.get("article", "")))
        return got == exp["article"]
    if cid == "t3_dividend":
        vals = [num(args.get(k)) for k in ("available", "total", "claim")]
        if any(v is None for v in vals):
            return False
        ratios = [v / exp[k] for v, k in zip(vals, ("available", "total", "claim")) if exp[k]]
        return all(abs(r - 1) < 1e-6 or abs(r * 10000 - 1) < 1e-6 for r in ratios)
    return str(args.get("path", "")).endswith(exp.get("path", "\0")) and str(args.get("sheet", "")) == exp.get("sheet", "\1") \
        and (("max_rows" not in exp) or num(args.get("max_rows")) == exp["max_rows"])


rows = json.loads(open(sys.argv[1], encoding="utf-8").read())
ok = []
for r in rows:
    try:
        args = json.loads(r.get("detail") or "{}")
    except json.JSONDecodeError:
        args = {}
    good = r.get("verdict") == "정답" or judge(r["id"], args)
    ok.append(good)
    print(f"{r['id']:<12} {'정답' if good else '오답'}  (정확일치: {r['verdict']})")
print(f"\n의미 기준 {sum(ok)}/{len(ok)} · 평균 {sum(r['secs'] for r in rows)/len(rows):.1f}s")
