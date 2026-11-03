import json, re, time, html, urllib.parse, urllib.request, pathlib
SET=json.load(open('/data/bench-results/eval_set_2026-11-04.json'))
items={i['id']:i for i in SET}
QUERIES={"Law-1":"site:law.go.kr 경비업법 특수경비원 무기 지급",
         "Law-2":"site:law.go.kr 경비업법 경비지도사 교육",
         "Law-3":"site:law.go.kr 청원경찰법 복제"}
BASE="http://127.0.0.1:20084"; MODEL="deepseek-v4.1-flash-1017-xq"
def search(q,n=5):
    u="http://127.0.0.1:20088/search?"+urllib.parse.urlencode({"q":q,"format":"json"})
    return json.load(urllib.request.urlopen(u,timeout=40)).get("results",[])[:n]
def text(url):
    try:
        r=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        raw=urllib.request.urlopen(r,timeout=25).read()
        t=raw.decode("utf-8","replace")
    except Exception: return ""
    t=re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>"," ",t)
    t=re.sub(r"(?s)<[^>]+>"," ",t); t=html.unescape(t)
    return re.sub(r"\s+"," ",t).strip()
out=[]
for tid,q in QUERIES.items():
    it=items[tid]; res=search(q)
    ctx="\n\n".join(f"[{r.get('title','')}] {text(r.get('url',''))[:3500]}" for r in res[:3])
    pr=f"근거:\n{ctx[:9000]}\n\n문제:\n{it['q']}\nA. {it['A']}\nB. {it['B']}\nC. {it['C']}\nD. {it['D']}\n\n정답 문자 하나만:"
    body={"model":MODEL,"messages":[{"role":"system","content":"근거를 우선 적용하고 보기 문자 하나만 출력하라."},{"role":"user","content":pr}],"max_tokens":1024,"temperature":0,"reasoning_budget_tokens":4096}
    req=urllib.request.Request(BASE+"/v1/chat/completions",data=json.dumps(body).encode(),headers={"Content-Type":"application/json"},method="POST")
    t0=time.time(); d=json.load(urllib.request.urlopen(req,timeout=900)); el=time.time()-t0
    c=(d.get('choices') or [{}])[0].get('message',{}).get('content') or ""
    m=re.search(r"\b([ABCD])\b",c.upper()); got=m.group(1) if m else ""
    v="정답" if got==it['a'] else ("무응답" if not got else "오답")
    out.append({"id":tid,"answer":it['a'],"got":got,"verdict":v,"ctx_len":len(ctx),"srcs":[r.get('url') for r in res[:3]]})
    print(f"[{tid}] {v} 정답={it['a']} 낸답={got or '-'} ctx={len(ctx)}자 ({el:.1f}s)",flush=True)
pathlib.Path('/data/bench-results/rag3_ds41.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
print("RAG(법령타깃):", sum(1 for r in out if r['verdict']=='정답'), "/", len(out))
