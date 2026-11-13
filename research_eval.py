#!/usr/bin/env python3
"""research_eval.py — 문항마다 '조사 먼저' 원칙을 강제하는 평가 하네스.

각 문항 처리 순서(모델 답변 이전에 서버측에서 수행):
  1) 조사규정 RAG  (Dify: 회생위원·관리인 직무편람)
  2) 법령·판례 MCP (korean-law 공개 프록시)
  3) 웹검색        (DuckDuckGo lite, 신뢰 낮음으로 표시)
검색어는 모델에게 1회 짧게 물어 뽑는다(법제처 검색이 공백 AND 조건이라 긴 질의는 실패한다).
그 뒤 세 근거를 시스템 컨텍스트로 주입하고, 도구를 쓸 수 있는 상태에서 최종 답을 받는다.

사용:
  ./research_eval.py http://127.0.0.1:8080 "<model>" out.json --set <set.json> [--limit N] [--no-web]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import os
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import difytool  # noqa: E402
import lawtool   # noqa: E402

SYS = ("너는 한국 법률·회계 실무자다. 아래 [사전조사] 자료는 이 문항을 위해 실제로 조회한 근거다. "
       "반드시 그 내용을 대조해 답하라. 자료에 없는 사실은 추측하지 말고, 자료가 부족하면 그 한계를 밝혀라. "
       "객관식이면 보기 문자 하나만 출력한다.")
SYS_SOFT = ("너는 한국 법률·회계 실무자다. 아래 [사전조사] 자료는 참고자료다. "
            "문항과 관련 있는 부분만 쓰고, 관련이 없으면 무시하고 네 판단으로 답하라. "
            "객관식이면 보기 문자 하나만 출력한다.")


def post(url: str, body: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def make_queries(base, model, question, args) -> dict:
    """검색어를 짧게 뽑는다(긴 질의는 MCP 에서 NOT_FOUND)."""
    prompt = ("다음 문제를 조회하려 한다. 검색어만 JSON 으로 출력하라.\n"
              '형식: {"law": "<법령명 또는 핵심 법률개념 1~3어>", "reg": "<실무 절차·서식 핵심어 1~3어>"}\n'
              "법제처 검색은 공백을 AND 로 처리하므로 짧아야 한다. 설명 금지.\n\n"
              f"[문제]\n{question[:1200]}")
    body = {"model": model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200, "temperature": 0, "reasoning_budget_tokens": 128}
    try:
        d = post(base, body, 240)
        txt = d["choices"][0]["message"].get("content") or ""
        m = re.search(r"\{.*\}", txt, re.S)
        q = json.loads(m.group(0)) if m else {}
        return {"law": (q.get("law") or "").strip()[:40], "reg": (q.get("reg") or "").strip()[:40]}
    except Exception:
        return {"law": "", "reg": ""}


def web_search(query: str, timeout: int = 20) -> str:
    """SearXNG(있으면) → Bing 폴백. 둘 다 신뢰 낮음(참고용)."""
    if not query:
        return ""
    sx = os.environ.get("SEARXNG_URL")
    if sx:
        try:
            u = f"{sx.rstrip('/')}/search?q=" + urllib.parse.quote(query) + "&format=json"
            req = urllib.request.Request(u, headers={"User-Agent": "hermes-research/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.load(r)
            return "\n".join(f"- {x.get('title','')}: {x.get('content','')[:200]}"
                             for x in (d.get("results") or [])[:4])[:1500] or "(SearXNG 결과 없음)"
        except Exception as e:
            return f"(SearXNG 실패: {e})"
    url = "https://www.bing.com/search?q=" + urllib.parse.quote(query) + "&count=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            page = r.read().decode("utf-8", "replace")
        items = re.findall(r'<li class="b_algo".*?</li>', page, re.S)
        out = []
        for it in items[:4]:
            title = re.sub(r"<[^>]+>", "", (re.search(r"<h2>(.*?)</h2>", it, re.S) or ["", ""])[1] if re.search(r"<h2>(.*?)</h2>", it, re.S) else "")
            snip = re.sub(r"<[^>]+>", " ", (re.search(r'<p[^>]*>(.*?)</p>', it, re.S) or ["", ""])[1] if re.search(r'<p[^>]*>(.*?)</p>', it, re.S) else "")
            snip = re.sub(r"\s+", " ", snip).strip()
            if snip:
                out.append(f"- {title.strip()}: {snip[:220]}")
        return "\n".join(out)[:1500] or "(Bing 결과 없음)"
    except Exception as e:
        return f"(웹검색 실패: {e})"


def norm(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s).lower()


def grade(it, content: str) -> str:
    c = (content or "").strip()
    if not c:
        return "무응답"
    if it["type"] == "mc":
        m = re.search(r"\b([ABCDE])\b", c.upper()) or re.search(r"([ABCDE])(?:[\.\)]|$)", c.upper())
        return ("정답" if m.group(1) == it["a"] else "오답") if m else "무응답"
    exp = norm(it["a"]); got = norm(c)
    if it["a"] == "없음":
        return "정답" if "없음" in c else "오답"
    return "정답" if exp and exp in got else "오답"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
    ap.add_argument("--set", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--reasoning-budget", type=int, default=1024)
    ap.add_argument("--no-web", action="store_true")
    ap.add_argument("--soft", action="store_true", help="자료를 무시해도 된다고 지시(잡음 완화)")
    ap.add_argument("--lbox", action="store_true", help="판례는 lbox 의미검색 사용(원문+id/오프셋)")
    ap.add_argument("--lbox-index", default="/data/models/lbox/index_corpus",
                    help="lbox 인덱스 접두어(기본: 판례 코퍼스 15만)")
    ap.add_argument("--min-year", type=int, default=2000, help="이 연도 이전 판례는 제외")
    ap.add_argument("--recency", type=float, default=0.05, help="최신성 가산점")
    ap.add_argument("--compact", action="store_true",
                    help="잡음 축소: Dify score 임계값 + 법령/판례 길이 제한(각 900/600자)")
    args = ap.parse_args()

    items = json.loads(pathlib.Path(args.set).read_text(encoding="utf-8"))
    if args.limit:
        items = items[: args.limit]
    results = []
    for i, it in enumerate(items, 1):
        q = it["q"]
        if it["type"] == "mc":
            opts = "\n".join(f"{L}. {it[L]}" for L in "ABCDE" if L in it)
            ask = f"{q}\n\n{opts}\n\n정답 문자만 출력:"
        else:
            ask = q
        t0 = time.time()
        queries = make_queries(args.base, args.model, q, args)
        # ① Dify: 관련도 낮은 조각은 버린다
        regs = ""
        try:
            import difytool as _D
            raw = _D.retrieve(q[:300], 3, threshold=0.60 if args.compact else None)
            regs = raw
        except Exception as e:
            regs = f"(조사규정 조회 실패: {e})"
        # ② 법령은 조문 본문만 짧게
        law = lawtool.lookup("law", queries["law"]) if queries.get("law") else ""
        prec = ""
        if args.lbox:
            # 키워드 AND 검색(MCP) 대신 lbox 의미검색 — 원문 청크 + doc id/오프셋
            try:
                sys.path.insert(0, "/data/models/lbox")
                import lbox_search as L
                hits = L.search(args.lbox_index, q[:400], 2, min_year=args.min_year, recency=args.recency)
                prec = "\n\n".join(f"[판례 {h['doc']} @{h['off']}] {h['text'][:900]}" for h in hits)
            except Exception as e:
                prec = f"(lbox 검색 실패: {e})"
        elif queries.get("law"):
            prec = lawtool.lookup("prec", queries["law"])
        if args.compact:
            def _shrink(t, n):
                t = re.sub(r"\n{2,}", "\n", t or "")
                return t[:n]
            law = _shrink(law, 900)
            # 판례는 '판시사항/판결요지' 앞부분만
            m = re.search(r"(판시사항|판결요지|요지)[\s\S]{0,600}", prec)
            prec = (m.group(0) if m else prec)[:600]
            regs = _shrink(regs, 900)
        web = "" if args.no_web else web_search(f"{queries.get('law','')} 판례")
        ctx = (f"[사전조사 1] 조사규정(직무편람) — 질의: {queries.get('reg','')}\n{regs[:2500]}\n\n"
               f"[사전조사 2] 법령 — 질의: {queries.get('law','')}\n{law[:2000]}\n\n"
               f"[사전조사 3] 판례 — 질의: {queries.get('law','')}\n{prec[:2000]}\n\n"
               f"[사전조사 4] 웹검색(신뢰 낮음)\n{web[:800]}")
        body = {"model": args.model,
                "messages": [{"role": "system", "content": (SYS_SOFT if args.soft else SYS) + "\n\n" + ctx},
                             {"role": "user", "content": ask}],
                "max_tokens": args.max_tokens, "temperature": 0,
                "reasoning_budget_tokens": args.reasoning_budget}
        try:
            d = post(args.base, body)
            content = d["choices"][0]["message"].get("content") or ""
            fin = d["choices"][0].get("finish_reason")
            verdict = grade(it, content)
        except Exception as e:
            content, fin, verdict = f"{e}"[:200], "error", "오류"
        el = time.time() - t0
        results.append({"id": it["id"], "type": it["type"], "verdict": verdict, "answer": it["a"],
                        "content": content[:200], "queries": queries, "secs": round(el, 1),
                        "ctx_chars": {"regs": len(regs), "law": len(law), "prec": len(prec), "web": len(web)},
                        "finish": fin})
        print(f"[{i}/{len(items)}] {it['id']:<24} {verdict:<4} {el:6.1f}s "
              f"q={queries.get('law','')!r} ctx={len(regs)}/{len(law)}/{len(prec)}/{len(web)}", flush=True)
    pathlib.Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for r in results if r["verdict"] == "정답")
    print(f"\n정답 {ok}/{len(results)} ({100*ok/len(results):.0f}%)  평균 {sum(r['secs'] for r in results)/len(results):.1f}s")


if __name__ == "__main__":
    main()
