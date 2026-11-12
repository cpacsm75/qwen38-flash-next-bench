#!/usr/bin/env python3
"""difytool.py — Dify 지식베이스 조회 (조사규정-참고자료).

회생위원·관리인·관리위원·개인파산관재인 직무편람, 수원회생법원 실무준칙 등.

사용:
  ./difytool.py "조사보고서 제출기한"            # 하이브리드 검색 + 리랭크
  ./difytool.py "부인권 행사 대상" --top 5
  ./difytool.py --list                          # 데이터셋/문서 목록

키는 ~/.hermes/.hermes_history 에서 찾은 dataset 키를 쓰거나 DIFY_DATASET_KEY 환경변수.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import urllib.request

BASE = os.environ.get("DIFY_BASE", "http://100.110.89.27:8100")
DATASET = os.environ.get("DIFY_DATASET_ID", "cb50e488-23c4-4b62-b920-1d2c61d5099b")


def _key() -> str:
    k = os.environ.get("DIFY_DATASET_KEY")
    if k:
        return k
    hist = pathlib.Path.home() / ".hermes/.hermes_history"
    if hist.exists():
        m = re.findall(r"dataset-[A-Za-z0-9]{20,}", hist.read_text(errors="ignore"))
        if m:
            return m[-1]
    raise SystemExit("Dify dataset 키를 찾지 못했습니다 (DIFY_DATASET_KEY).")


def _api(path: str, body: dict | None = None, timeout: int = 40):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET",
                                 headers={"Authorization": f"Bearer {_key()}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def list_docs() -> str:
    d = _api(f"/v1/datasets/{DATASET}/documents?page=1&limit=20")
    lines = [f"{x['name']} ({x.get('word_count')} words)" for x in d.get("data", [])]
    return "\n".join(lines)


def retrieve(query: str, top: int = 4, threshold: float | None = None) -> str:
    body = {"query": query,
            "retrieval_model": {"search_method": "hybrid_search", "reranking_enable": True,
                                "top_k": top, "score_threshold_enabled": threshold is not None,
                                "score_threshold": threshold or 0.0}}
    d = _api(f"/v1/datasets/{DATASET}/retrieve", body)
    recs = d.get("records", [])
    if not recs:
        return "검색 결과 없음"
    out = []
    for i, r in enumerate(recs, 1):
        seg = r.get("segment", {})
        doc = seg.get("document", {}).get("name") or seg.get("document_name") or ""
        out.append(f"[{i}] score={r.get('score'):.3f}  {doc}\n{seg.get('content','').strip()}")
    return "\n\n".join(out)


def lookup(query: str, top: int = 4) -> str:
    """에이전틱 하네스에서 쓰는 진입점."""
    try:
        return retrieve(query, top)
    except Exception as e:
        return f"Dify 조회 실패: {e}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--top", type=int, default=4)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        print(list_docs())
    elif a.query:
        print(retrieve(a.query, a.top))
    else:
        ap.print_help()
