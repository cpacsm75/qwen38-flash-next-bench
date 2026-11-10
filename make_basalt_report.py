#!/usr/bin/env python3
"""basalt 평가 결과 → 마크다운 표. 사용: make_basalt_report.py <tag> [<tag2> ...]"""
import json
import pathlib
import sys

HERE = pathlib.Path("/data/bench-results")
SET = json.loads((HERE / "eval_set_confirmed_2026-11-10.json").read_text(encoding="utf-8"))
KIND = {}
for it in SET:
    i = it["id"]
    if i.startswith("Accounting"):
        KIND[i] = "회계"
    elif i.startswith("Law"):
        KIND[i] = "법률"
    else:
        KIND[i] = "계산·함정"


def summarize(tag):
    p = HERE / f"eval_basalt_{tag}.json"
    if not p.exists():
        return None
    rows = json.loads(p.read_text(encoding="utf-8"))
    by = {}
    for r in rows:
        k = KIND.get(r["id"], "?")
        by.setdefault(k, [0, 0])
        by[k][1] += 1
        if r["verdict"] == "정답":
            by[k][0] += 1
    total = sum(v[0] for v in by.values()), sum(v[1] for v in by.values())
    secs = [r["secs"] for r in rows if r.get("secs")]
    return {"by": by, "total": total, "avg": sum(secs) / len(secs) if secs else 0,
            "rows": rows}


tags = sys.argv[1:] or ["q6"]
print("| 모델 | 회계 | 계산·함정 | 법률(확정키) | 합계 | 평균 응답 |")
print("|---|---:|---:|---:|---:|---:|")
for t in tags:
    s = summarize(t)
    if not s:
        print(f"| {t} | - | - | - | (없음) | - |")
        continue
    b = s["by"]
    f = lambda k: f"{b.get(k, [0, 0])[0]}/{b.get(k, [0, 0])[1]}"
    ok, n = s["total"]
    print(f"| basalt {t.upper()} | {f('회계')} | {f('계산·함정')} | {f('법률')} | **{ok}/{n}** | {s['avg']:.1f}s |")

print("\n오답·무응답 문항:")
for t in tags:
    s = summarize(t)
    if not s:
        continue
    for r in s["rows"]:
        if r["verdict"] != "정답":
            print(f"- {t.upper()} {r['id']}: {r['verdict']} (정답 {r['answer']}, 응답 {r['content'][:30]!r}, {r['secs']}s)")
