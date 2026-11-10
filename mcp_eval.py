#!/usr/bin/env python3
"""mcp_eval.py — 도구 호출(MCP/function calling) 벤치.
도구 스키마 3종을 주고 5개 시나리오에서 올바른 tool_call(name + arguments)을 내는지 채점.
사용: ./mcp_eval.py <base_url> <model> <out.json>
"""
import argparse, json, sys, time, urllib.request, pathlib

TOOLS = [
 {"type":"function","function":{"name":"search_law","description":"한국 법령/조문을 검색한다",
   "parameters":{"type":"object","properties":{"query":{"type":"string","description":"검색어"},
   "article":{"type":"string","description":"조문 번호(선택)"}},"required":["query"]}}},
 {"type":"function","function":{"name":"read_sheet","description":"엑셀 파일의 시트를 읽는다",
   "parameters":{"type":"object","properties":{"path":{"type":"string"},"sheet":{"type":"string"},"max_rows":{"type":"integer"}},
   "required":["path","sheet"]}}},
 {"type":"function","function":{"name":"compute_dividend","description":"배당액을 계산한다",
   "parameters":{"type":"object","properties":{"available":{"type":"number"},"total":{"type":"number"},"claim":{"type":"number"}},
   "required":["available","total","claim"]}}},
]

CASES = [
 {"id":"t1_law","prompt":"개인회생에서 임차보증금 우선변제권 조문을 찾아봐.","expect":{"name":"search_law","args":{"query":"임차보증금 우선변제권"}}},
 {"id":"t2_sheet","prompt":"/data/2026회합1005.xlsx 의 '시부인표' 시트를 읽어줘.","expect":{"name":"read_sheet","args":{"path":"/data/2026회합1005.xlsx","sheet":"시부인표"}}},
 {"id":"t3_dividend","prompt":"가용재원 1,200만원, 총채권 4,800만원, 채권 800만원의 배당액을 계산해줘.","expect":{"name":"compute_dividend","args":{"available":12000000,"total":48000000,"claim":8000000}}},
 {"id":"t4_multi","prompt":"'채무자회생법' 제179조를 검색하고, 결과를 알려줘.","expect":{"name":"search_law","args":{"query":"채무자회생법","article":"179"}}},
 {"id":"t5_read","prompt":"/data/report.xlsx 파일에서 '경제성조사' 시트 첫 100행만 읽어줘.","expect":{"name":"read_sheet","args":{"path":"/data/report.xlsx","sheet":"경제성조사","max_rows":100}}},
]

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--max-tokens", type=int, default=4096)
ap.add_argument("--reasoning-budget", type=int, default=2048)
a = ap.parse_args()

def ask(prompt):
    body = {"model": a.model,
            "messages":[{"role":"system","content":"너는 한국인 공인회계사(KICPA)다. 모든 답변은 근거를 바탕으로 한국어 문법에 맞게 작성한다. 절대 영어나 중국어로 답하지 않는다. 사용자 요청에 필요한 도구를 정확히 하나 호출하라. 인자 값은 요청에 나온 그대로 넣는다."},
                        {"role":"user","content":prompt}],
            "tools": TOOLS, "tool_choice":"auto", "max_tokens": a.max_tokens, "temperature": 0}
    if "20084" in a.base:
        body["reasoning_budget_tokens"] = a.reasoning_budget
    req = urllib.request.Request(a.base.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"}, method="POST")
    t0=time.time(); d=json.load(urllib.request.urlopen(req, timeout=600)); el=time.time()-t0
    ch=(d.get("choices") or [{}])[0]; m=ch.get("message") or {}
    return m, ch.get("finish_reason"), el

def grade(m, expect):
    tcs = m.get("tool_calls") or []
    if not tcs:
        return "도구호출없음", ""
    fn = (tcs[0].get("function") or {})
    name = fn.get("name") or ""
    raw = fn.get("arguments") or "{}"
    try:
        args = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return "인자JSON오류", raw[:80]
    if name != expect["name"]:
        return "도구명불일치", f"{name} != {expect['name']}"
    ok = True
    for k, v in expect["args"].items():
        got = args.get(k)
        if isinstance(v, (int, float)):
            try:
                ok = ok and float(got) == float(v)
            except (TypeError, ValueError):
                ok = False
        else:
            ok = ok and (str(got) == str(v))
    return ("정답" if ok else "인자불일치"), json.dumps(args, ensure_ascii=False)[:120]

res=[]
for c in CASES:
    try:
        m, fin, el = ask(c["prompt"])
        verdict, detail = grade(m, c["expect"])
    except Exception as e:
        m, fin, el, verdict, detail = {}, "error", 0, "오류", str(e)[:80]
    res.append({"id":c["id"],"verdict":verdict,"detail":detail,"finish":fin,"secs":round(el,1),
                "has_tool_calls": bool(m.get("tool_calls"))})
    print(f"[{c['id']:<11}] {verdict:<12} {el:5.1f}s  {detail[:70]}", flush=True)

pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
ok=sum(1 for r in res if r["verdict"]=="정답")
print(f"\n==== 도구호출: {ok}/{len(CASES)} 정확 · 평균 {sum(r['secs'] for r in res)/len(res):.1f}s ====")
