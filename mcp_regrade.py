#!/usr/bin/env python3
"""mcp_regrade.py — MCP 판정을 의미 기준으로 재채점(재실행 없이 저장된 인자 사용)."""
import json, re, sys

def norm_num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def grade(cid, args):
    if not isinstance(args, dict): return False
    a = {k: (v if not isinstance(v, str) else v.strip()) for k, v in args.items()}
    q = str(a.get("query", ""))
    if cid == "t1_law":
        return ("임차보증금" in q) and ("우선변제권" in q or "우선 변제" in q)
    if cid == "t2_sheet":
        return str(a.get("path", "")).endswith("2026회합1005.xlsx") and str(a.get("sheet", "")) == "시부인표"
    if cid == "t3_dividend":
        exp = {"available": 12000000, "total": 48000000, "claim": 8000000}
        for k, e in exp.items():
            v = norm_num(a.get(k))
            if v is None: return False
            if not (v == e or v * 10000 == e):     # 원 단위 또는 만원 단위 표기 모두 인정
                return False
        return True
    if cid == "t4_multi":
        art = str(a.get("article", ""))
        return ("채무자회생법" in q or "채무자 회생" in q) and "179" in art
    if cid == "t5_read":
        return ("report.xlsx" in str(a.get("path", "")) and str(a.get("sheet", "")) == "경제성조사"
                and norm_num(a.get("max_rows")) == 100)
    return False

for tag in ("ds41", "fp8", "q8", "q5"):
    try: d = json.load(open(f"/data/bench-results/mcp_{tag}.json"))
    except FileNotFoundError: continue
    ok = 0; det = []
    for r in d:
        try: args = json.loads(r["detail"]) if r["detail"].startswith("{") else {}
        except Exception: args = {}
        good = grade(r["id"], args)
        ok += good
        det.append(f"{r['id']}={'O' if good else 'X'}")
    print(f"{tag:5s} {ok}/{len(d)}  " + " ".join(det))
