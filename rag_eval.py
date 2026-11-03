#!/usr/bin/env python3
"""rag_eval.py — closed-book에서 전 모델이 틀린 법률 문항을, 검색 근거를 붙여 재시험.
사용: ./rag_eval.py <base_url> <model> <out.json> [--top N]
검색: 로컬 SearXNG(127.0.0.1:20088). 근거는 상위 결과의 스니펫(content) + 제목/URL.
"""
import argparse, json, re, sys, time, urllib.parse, urllib.request, pathlib

SET = pathlib.Path("/data/bench-results/eval_set_2026-11-04.json")
ITEMS = ["Law-1", "Law-2", "Law-3"]          # 세 모델 모두 오답이었던 문항

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--top", type=int, default=4)
ap.add_argument("--max-tokens", type=int, default=2048)
ap.add_argument("--reasoning-budget", type=int, default=4096)
a = ap.parse_args()

items = {i["id"]: i for i in json.loads(SET.read_text(encoding="utf-8"))}

def search(q, n=6):
    u = "http://127.0.0.1:20088/search?" + urllib.parse.urlencode({"q": q, "format": "json"})
    try:
        d = json.load(urllib.request.urlopen(u, timeout=40))
        return d.get("results", [])[:n]
    except Exception as e:
        print("검색 실패:", str(e)[:80], file=sys.stderr)
        return []

def build_ctx(it, top):
    # 질문에서 핵심어 추출: 한글/영문 토큰 중 긴 것 위주
    q = it["q"]
    toks = re.findall(r"[가-힣A-Za-z]{2,}", q)
    toks = sorted(set(toks), key=len, reverse=True)[:8]
    query = " ".join(toks) + " 법령"
    res = search(query, top)
    lines = [f"[{r.get('title','')}] {r.get('content','')[:400]}" for r in res if r.get("content")]
    return query, "\n".join(lines)[:3000], res

def ask(it, ctx):
    prompt = (f"아래 근거를 참고해 문제의 정답 보기 문자 하나만 출력하라.\n\n"
              f"근거:\n{ctx}\n\n문제:\n{it['q']}\n\nA. {it['A']}\nB. {it['B']}\nC. {it['C']}\nD. {it['D']}\n\n정답 문자:")
    body = {"model": a.model, "messages": [
        {"role": "system", "content": "한국어 객관식 문제다. 근거를 우선 적용하고, 정답 보기 문자 하나만 출력하라."},
        {"role": "user", "content": prompt}],
        "max_tokens": a.max_tokens, "temperature": 0}
    if "20084" in a.base:
        body["reasoning_budget_tokens"] = a.reasoning_budget
    req = urllib.request.Request(a.base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=1800))
    el = time.time() - t0
    ch = (d.get("choices") or [{}])[0]
    return (ch.get("message") or {}).get("content") or "", el

out = []
for tid in ITEMS:
    it = items[tid]
    query, ctx, res = build_ctx(it, a.top)
    content, el = ask(it, ctx) if ctx else ("", 0)
    m = re.search(r"\b([ABCD])\b", content.upper())
    got = m.group(1) if m else ""
    verdict = "정답" if got == it["a"] else ("무응답" if not got else "오답")
    out.append({"id": tid, "answer": it["a"], "got": got, "verdict": verdict,
                "secs": round(el, 1), "query": query,
                "sources": [r.get("url") for r in res][:a.top], "ctx_len": len(ctx)})
    print(f"[{tid}] {verdict} 정답={it['a']} 낸답={got or '-'} ({el:.1f}s) ctx={len(ctx)}자 검색어={query[:40]!r}", flush=True)

pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
ok = sum(1 for r in out if r["verdict"] == "정답")
print(f"\n==== RAG 후: {ok}/{len(ITEMS)} 정답 ====")
