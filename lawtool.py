#!/usr/bin/env python3
"""lawtool.py — 법령·판례 조회 (korean-law MCP 경유).

기본 백엔드는 공개 원격 MCP(https://mcp.gomdori.app/law) — 인증키·IP 등록 없이 동작한다.
법제처 공식 API를 직접 쓰려면 LAW_BACKEND=lawapi (호출 서버 IP가 open.law.go.kr
마이페이지에 등록돼 있어야 하고, 미등록이면 "사용자 정보 검증에 실패"로 거부된다).

CLI:
  ./lawtool.py law 주택임대차보호법 3의2
  ./lawtool.py prec "임차보증금 우선변제"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request

MCP_URL = os.environ.get("LAW_MCP_URL", "https://mcp.gomdori.app/law")
OC = os.environ.get("LAW_GO_KR_KEY", "cpacsm")
UA = "hermes-lawtool/1.0"
TARGETS = {"law": "법령", "prec": "판례", "expc": "법령해석례", "detc": "헌재결정", "ordin": "자치법규"}
DOMAIN = {"prec": "precedent", "expc": "interpretation", "detc": "constitutional", "ordin": "precedent"}


def _post(body: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(MCP_URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream",
                                          "User-Agent": UA}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    for line in raw.splitlines():           # SSE 프레임이면 data: 줄만 쓴다
        if line.startswith("data:"):
            raw = line[5:].strip()
            break
    return json.loads(raw)


def mcp_tool(name: str, args: dict, timeout: int = 60) -> str:
    d = _post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": name, "arguments": args}}, timeout)
    if "error" in d:
        return f"[MCP 오류] {d['error']}"
    res = d.get("result", {})
    parts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
    return "\n".join(parts) or json.dumps(res, ensure_ascii=False)[:2000]


def _lawapi(kind: str, query: str, article: str | None) -> str:
    q = urllib.parse.quote(query)
    if article and kind == "law":
        url = (f"https://www.law.go.kr/DRF/lawService.do?OC={OC}&target=law&type=JSON"
               f"&LM={q}&JO={urllib.parse.quote(article)}")
    else:
        url = (f"https://www.law.go.kr/DRF/lawSearch.do?OC={OC}&target={kind}&type=JSON"
               f"&query={q}&display=5")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    if "사용자 정보 검증에 실패" in body:
        raise RuntimeError("법제처 API 호출 서버 IP 미등록")
    return body[:6000]


def lookup(kind: str, query: str, article: str | None = None, force_backend: str | None = None) -> str:
    backend = force_backend or os.environ.get("LAW_BACKEND", "mcp")
    if backend == "lawapi":
        try:
            return f"[backend=법제처API target={kind}]\n{_lawapi(kind, query, article)}"
        except Exception as e:
            return f"법제처 API 실패: {e}"

    if kind == "law":
        head = mcp_tool("search_law", {"query": query, "display": 5})
        m = re.search(r"MST[:：]\s*(\d+)", head)
        if not m:
            return f"[MCP search_law]\n{head[:4000]}"
        jo = None
        if article:
            a = article.replace("제", "").replace("조", "")
            jo = f"제{a.split('의')[0]}조의{a.split('의')[1]}" if "의" in a else f"제{a}조"
        args = {"mst": m.group(1)}
        if jo:
            args["jo"] = jo
        body = mcp_tool("get_law_text", args)
        return (f"[MCP search_law → get_law_text 「{query}」{' ' + jo if jo else ''}]\n"
                f"{head[:600]}\n\n{body[:5000]}")

    dom = DOMAIN.get(kind, "precedent")
    head = mcp_tool("search_decisions", {"domain": dom, "query": query, "display": 3})
    ids = re.findall(r"[Ii][Dd][:：]\s*([0-9]{4,})", head) or re.findall(r"\b(\d{5,})\b", head)
    out = f"[MCP search_decisions domain={dom} query={query}]\n{head[:2500]}"
    if ids:
        out += (f"\n\n[MCP get_decision_text id={ids[0]}]\n"
                f"{mcp_tool('get_decision_text', {'domain': dom, 'id': ids[0]})[:4000]}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=list(TARGETS))
    ap.add_argument("query")
    ap.add_argument("article", nargs="?")
    ap.add_argument("--backend", default=None)
    a = ap.parse_args()
    print(lookup(a.kind, a.query, a.article, a.backend))
