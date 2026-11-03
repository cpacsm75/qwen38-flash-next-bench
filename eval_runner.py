#!/usr/bin/env python3
"""eval_runner.py — 로컬 엔진 품질 비교(객관식 20 + 계산/함정 5).

사용: ./eval_runner.py <base_url> <model> <out.json> [--reasoning-budget N] [--max-tokens N]
채점: content만 본다(reasoning 제외). 객관식은 보기 문자, 자유형은 숫자/문자열 정규화 비교.
"""
import json, re, sys, time, urllib.request, pathlib, argparse

SET = pathlib.Path("/data/bench-results/eval_set_2026-11-04.json")

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--reasoning-budget", type=int, default=4096)
ap.add_argument("--max-tokens", type=int, default=2048)
a = ap.parse_args()

items = json.loads(SET.read_text(encoding="utf-8"))
results = []

SYS_MC = "한국어 객관식 문제다. 정답 보기의 문자 하나(A/B/C/D)만 출력하라. 다른 텍스트 금지."
SYS_FREE = "계산·추출 문제다. 요구된 값만 출력하라. 설명·단위·콤마 없이. 문서에 없으면 '없음'만 출력."

def ask(it):
    if it["type"] == "mc":
        prompt = f"{it['q']}\n\nA. {it['A']}\nB. {it['B']}\nC. {it['C']}\nD. {it['D']}\n\n정답 문자만 출력:"
        system = SYS_MC
    else:
        prompt = it["q"]
        system = SYS_FREE
    body = {"model": a.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "max_tokens": a.max_tokens, "temperature": 0}
    if "20084" in a.base:
        body["reasoning_budget_tokens"] = a.reasoning_budget
    req = urllib.request.Request(a.base.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    if "deepseek.com" in a.base:
        import re as _re
        _env = open("/home/cpacsm/.hermes/.env").read()
        _k = _re.search(r"^DEEPSEEK_API_KEY=(\S+)", _env, _re.M).group(1)
        req.add_header("Authorization", f"Bearer {_k}")
    t0 = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=1800))
    el = time.time() - t0
    ch = (d.get("choices") or [{}])[0]
    m = ch.get("message") or {}
    return m.get("content") or "", (m.get("reasoning_content") or ""), el, ch.get("finish_reason")

def norm(s):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()

def grade(it, content):
    c = content.strip()
    if not c:
        return "무응답"
    if it["type"] == "mc":
        m = re.search(r"\b([ABCD])\b", c.upper())
        if m:
            return "정답" if m.group(1) == it["a"] else "오답"
        m = re.search(r"([ABCD])(?:[\.\)]|$)", c.upper())
        if m:
            return "정답" if m.group(1) == it["a"] else "오답"
        return "무응답"
    exp = norm(it["a"]); got = norm(c)
    if it["a"] == "없음":
        return "정답" if "없음" in c else "오답"
    return "정답" if exp and exp in got else "오답"

for i, it in enumerate(items, 1):
    try:
        content, reasoning, el, fin = ask(it)
        verdict = grade(it, content)
    except Exception as e:
        content, reasoning, el, fin, verdict = "", "", 0, "error", "오류"
        print(f"[{i}/{len(items)}] {it['id']} ERROR {str(e)[:80]}", flush=True)
    results.append({"id": it["id"], "type": it["type"], "verdict": verdict,
                    "answer": it["a"], "content": content[:200], "content_len": len(content),
                    "reasoning_len": len(reasoning), "secs": round(el, 1), "finish": fin})
    print(f"[{i}/{len(items)}] {it['id']:<22} {verdict:<4} {el:6.1f}s  content={content.strip()[:40]!r}", flush=True)

pathlib.Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=1))

def rate(f):
    sel = [r for r in results if f(r)]
    if not sel: return "0/0"
    ok = sum(1 for r in sel if r["verdict"] == "정답")
    return f"{ok}/{len(sel)} ({100*ok/len(sel):.0f}%)"

print("\n==== 요약 ====")
print("전체      ", rate(lambda r: True))
print("객관식    ", rate(lambda r: r["type"] == "mc"))
print("계산/함정 ", rate(lambda r: r["type"] == "free"))
print("무응답    ", sum(1 for r in results if r["verdict"] == "무응답"), "/", len(results))
print("오류      ", sum(1 for r in results if r["verdict"] == "오류"), "/", len(results))
print("평균 소요 ", round(sum(r["secs"] for r in results)/len(results), 1), "s")
