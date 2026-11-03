#!/usr/bin/env python3
"""rag_eval2.py — 개선판 RAG 벤치: 질문 전문으로 검색, 상위 결과의 본문을 실제로 받아 주입.
사용: ./rag_eval2.py <base_url> <model> <out.json>
"""
import argparse, html, json, re, sys, time, urllib.parse, urllib.request, pathlib

SET = pathlib.Path("/data/bench-results/eval_set_2026-11-04.json")
IDS = ["Law-1", "Law-2", "Law-3"]
SEARX = "http://127.0.0.1:20088/search"

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--max-tokens", type=int, default=2048)
ap.add_argument("--reasoning-budget", type=int, default=4096)
ap.add_argument("--pages", type=int, default=3)
ap.add_argument("--page-chars", type=int, default=3500)
a = ap.parse_args()

items = {i["id"]: i for i in json.loads(SET.read_text(encoding="utf-8"))}

def search(q, n=5):
    u = SEARX + "?" + urllib.parse.urlencode({"q": q, "format": "json"})
    try:
        return json.load(urllib.request.urlopen(u, timeout=40)).get("results", [])[:n]
    except Exception as e:
        print("검색실패", str(e)[:80], file=sys.stderr); return []

def fetch_text(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=25).read()
        try: txt = raw.decode("utf-8", "replace")
        except Exception: txt = raw.decode("cp949", "replace")
    except Exception:
        return ""
    txt = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", txt)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()

def build_ctx(it):
    q = it["q"]

    def do(qq):
        res = search(qq, 6)
        chunks = []
        for r in res[: a.pages]:
            body = fetch_text(r.get("url", ""))
            body = body[: a.page_chars]
            if body:
                chunks.append(f"[{r.get('title','')}]\n{body}")
        return qq, "\n\n".join(chunks), res

    qq, ctx, res = do(q)
    if len(ctx) < 800:                       # 본문이 적으면 질문 앞부분만으로 재검색
        qq2, ctx2, res2 = do(q[:60] + " 법령")
        if len(ctx2) > len(ctx):
            qq, ctx, res = qq2, ctx2, res2
    return qq, ctx[:9000], res

def ask(it, ctx):
    prompt = (f"아래 근거 자료를 반드시 우선 적용해 문제를 푼다.\n\n=== 근거 ===\n{ctx}\n=== 끝 ===\n\n"
              f"문제:\n{it['q']}\n\nA. {it['A']}\nB. {it['B']}\nC. {it['C']}\nD. {it['D']}\n\n정답 보기 문자 하나만 출력:")
    body = {"model": a.model,
            "messages": [{"role":"system","content":"한국어 객관식 문제다. 근거에 답이 있으면 그것을 따르고, 보기 문자 하나만 출력하라."},
                         {"role":"user","content":prompt}],
            "max_tokens": a.max_tokens, "temperature": 0}
    if "20084" in a.base:
        body["reasoning_budget_tokens"] = a.reasoning_budget
    req = urllib.request.Request(a.base.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"}, method="POST")
    t0 = time.time(); d = json.load(urllib.request.urlopen(req, timeout=1800)); el = time.time()-t0
    ch = (d.get("choices") or [{}])[0]
    return (ch.get("message") or {}).get("content") or "", el

out = []
for tid in IDS:
    it = items[tid]
    qq, ctx, res = build_ctx(it)
    content, el = ask(it, ctx)
    m = re.search(r"\b([ABCD])\b", content.upper())
    got = m.group(1) if m else ""
    verdict = "정답" if got == it["a"] else ("무응답" if not got else "오답")
    out.append({"id":tid,"answer":it["a"],"got":got,"verdict":verdict,"secs":round(el,1),
                "query":qq,"ctx_len":len(ctx),"sources":[r.get("url") for r in res][:a.pages]})
    print(f"[{tid}] {verdict} 정답={it['a']} 낸답={got or '-'} ({el:.1f}s) ctx={len(ctx)}자 src={len(res)}", flush=True)

pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
ok = sum(1 for r in out if r["verdict"]=="정답")
print(f"\n==== RAG(개선) 후: {ok}/{len(IDS)} 정답 ====")
