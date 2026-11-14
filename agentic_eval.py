#!/usr/bin/env python3
"""agentic_eval.py — 도구 조회를 허용한(에이전틱) 문항 평가.

eval_runner.py 와 달리 모델이 도구를 호출하면 실제로 법령/판례를 조회해 되먹인다.
"법령·판례 조회가 있으면 정답률이 오르는가"를 재는 용도.

사용:
  ./agentic_eval.py <base_url> <model> <out.json> --set SET.json [--turns 3] [--limit N]
                    [--reasoning-budget 1024] [--max-tokens 8192]

백엔드는 lawtool.py 를 따른다(LAW_BACKEND=lawapi|bing|auto, 기본 auto).
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
import lawtool  # noqa: E402
import difytool  # noqa: E402

TOOLS = [{
    "type": "function",
    "function": {
        "name": "lookup_regulations",
        "description": "조사 실무 규정을 조회한다: 회생위원·관리인·관리위원·개인파산관재인 직무편람, 회생법원 실무준칙. "
                       "절차·기한·서식·실무 기준을 물을 때 쓴다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색 질의(자연어)"},
                "top": {"type": "integer", "description": "가져올 조각 수(기본 4)"},
            },
            "required": ["query"],
        },
    },
}, {
    "type": "function",
    "function": {
        "name": "lookup_law",
        "description": "한국 법령 조문 또는 판례·법령해석례를 조회한다. 답에 근거가 필요하면 먼저 호출하라.",
        "parameters": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["law", "prec", "expc", "detc"],
                         "description": "law=법령 조문, prec=판례, expc=법령해석례, detc=헌재결정"},
                "query": {"type": "string", "description": "법령명 또는 검색어"},
                "article": {"type": "string", "description": "조문 번호(예: '750', '3의2'). 선택"},
            },
            "required": ["kind", "query"],
        },
    },
}, {
    "type": "function",
    "function": {
        "name": "lookup_precedent",
        "description": "판례 코퍼스(15만 건, 원문) 의미검색. 최신 판례 우선으로 재정렬한다. "
                       "판례의 법리가 쟁점일 때 lookup_law 대신 이 도구를 쓴다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색 질의(자연어)"},
                "top": {"type": "integer", "description": "가져올 판례 수(기본 2)"},
            },
            "required": ["query"],
        },
    },
}]

SYS = ("너는 한국 법률·회계 실무자다. 근거가 필요한 문제에서는 lookup_law 도구로 법령·판례를 조회한 뒤 "
       "그 내용에 근거해 답하라. 최종 답은 요구된 형식만 출력한다(객관식은 보기 문자 하나).")


def post(url, body, timeout=900):
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def norm(s):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()


def grade(it, content):
    c = (content or "").strip()
    if not c:
        return "무응답"
    if it["type"] == "mc":
        m = re.search(r"\b([ABCDE])\b", c.upper()) or re.search(r"([ABCDE])(?:[\.\)]|$)", c.upper())
        return ("정답" if m.group(1) == it["a"] else "오답") if m else "무응답"
    exp, got = norm(it["a"]), norm(c)
    if it["a"] == "없음":
        return "정답" if "없음" in c else "오답"
    return "정답" if exp and exp in got else "오답"


def ask(base, model, messages, args, force_final=False, force_tool=False):
    choice = "none" if force_final else ("auto" if not force_tool else
              {"type": "function", "function": {"name": "lookup_law"}})
    body = {"model": model, "messages": messages, "tools": TOOLS,
            "tool_choice": choice,
            "max_tokens": args.max_tokens, "temperature": 0,
            "reasoning_budget_tokens": args.reasoning_budget}
    return post(base, body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("model")
    ap.add_argument("out")
    ap.add_argument("--set", required=True)
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reasoning-budget", type=int, default=1024)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--tool-prefix", default="", help="프롬프트에 덧붙일 지시(도구 없이 비교하려면 빈칸)")
    ap.add_argument("--dummy-tools", action="store_true",
                    help="도구가 항상 '검색 결과 없음'을 돌려주는 대조군(추론 추가효과 측정)")
    ap.add_argument("--force-first", action="store_true",
                    help="첫 턴에 lookup_law 호출을 강제한다(모델이 조회를 건너뛰는 문제 회피)")
    args = ap.parse_args()

    items = json.loads(pathlib.Path(args.set).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    results = []
    for i, it in enumerate(items, 1):
        prompt = it["q"]
        if it["type"] == "mc":
            opts = "\n".join(f"{L}. {it[L]}" for L in "ABCDE" if L in it)
            prompt = f"{prompt}\n\n{opts}\n\n정답 문자만 출력:"
        messages = [{"role": "system", "content": SYS + (" " + args.tool_prefix if args.tool_prefix else "")},
                    {"role": "user", "content": prompt}]
        tool_log, t0, content, fin, seen = [], time.time(), "", None, set()
        try:
            for turn in range(args.turns + 1):
                force_final = turn == args.turns
                force_tool = args.force_first and turn == 0
                if force_final:
                    messages.append({"role": "user",
                                     "content": "지금까지 확인한 내용만으로 답하라. 도구를 더 호출하지 마라. "
                                                "객관식이면 보기 문자 하나만 출력."})
                d = ask(args.base, args.model, messages, args, force_final, force_tool)
                msg = d["choices"][0]["message"]
                calls = msg.get("tool_calls") or []
                content = msg.get("content") or ""
                fin = d["choices"][0].get("finish_reason")
                if not calls:
                    break
                messages.append({"role": "assistant", "content": msg.get("content"),
                                 "tool_calls": calls})
                for c in calls:
                    fn = c["function"]["name"]
                    try:
                        a = json.loads(c["function"].get("arguments") or "{}")
                    except Exception:
                        a = {}
                    if fn == "lookup_precedent":
                        signature = ("prec_lbox", a.get("query", ""), str(a.get("top", 2)))
                    elif fn == "lookup_regulations":
                        signature = ("reg", a.get("query", ""), str(a.get("top", 4)))
                    else:
                        signature = (a.get("kind", "law"), a.get("query", ""), a.get("article") or "")
                    dup = signature in seen
                    if dup:
                        txt = "이미 조회한 내용이다. 같은 조회를 반복하지 말고 확인된 내용으로 답하라."
                    else:
                        seen.add(signature)
                        if getattr(args, "dummy_tools", False):
                            txt = "검색 결과 없음 (이 저장소에서는 해당 자료를 찾지 못했습니다)"
                        elif fn == "lookup_precedent":
                            sys.path.insert(0, "/data/models/lbox")
                            import lbox_search as L
                            hits = L.search("/data/models/lbox/index_corpus", a.get("query", ""),
                                            int(a.get("top", 2)), min_year=2000, recency=0.05)
                            txt = "\n\n".join(
                                f"[판례 {h['doc']} · {h.get('year')}년 · off {h['off']}] {h['text'][:900]}"
                                for h in hits) or "(검색 결과 없음)"
                        elif fn == "lookup_regulations":
                            txt = difytool.lookup(a.get("query", ""), int(a.get("top", 4)))
                        else:
                            txt = lawtool.lookup(*signature)
                    tool_log.append({"name": fn, "args": a, "chars": len(txt), "dup": dup})
                    messages.append({"role": "tool", "tool_call_id": c["id"],
                                     "content": txt[:2500]})
            verdict = grade(it, content)
        except Exception as e:
            verdict, content, fin = "오류", f"{e}"[:200], "error"
        el = time.time() - t0
        results.append({"id": it["id"], "type": it["type"], "verdict": verdict,
                        "answer": it["a"], "content": (content or "")[:200],
                        "tool_calls": tool_log, "secs": round(el, 1), "finish": fin})
        print(f"[{i}/{len(items)}] {it['id']:<24} {verdict:<4} {el:6.1f}s "
              f"tools={len(tool_log)} content={(content or '').strip()[:30]!r}", flush=True)
    pathlib.Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in results if r["verdict"] == "정답")
    called = sum(1 for r in results if r["tool_calls"])
    print(f"\n정답 {ok}/{len(results)} ({100*ok/len(results):.0f}%)  도구호출 {called}건  "
          f"평균 {sum(r['secs'] for r in results)/len(results):.1f}s")


if __name__ == "__main__":
    main()
