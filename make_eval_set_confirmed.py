#!/usr/bin/env python3
"""확정 정답 키만으로 평가셋을 만든다.

원본 eval_set_2026-11-04.json 에서
  - key_wrong  → lawkey_audit.json 의 correct 로 정답 키 교체
  - item_defect / unverified → 제외 (채점 불가)
나머지(회계·계산·함정)는 그대로 둔다.

사용: ./make_eval_set_confirmed.py [out.json]
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "eval_set_2026-11-04.json"
AUDIT = HERE / "lawkey_audit.json"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "eval_set_confirmed_2026-11-10.json"

items = json.loads(SRC.read_text(encoding="utf-8"))
audit = json.loads(AUDIT.read_text(encoding="utf-8"))["items"]

out, dropped = [], []
for it in items:
    it = dict(it)
    a = audit.get(it["id"])
    if a:
        if a["verdict"] == "key_wrong":
            it["a_original"] = a["key"]
            it["a"] = a["correct"]
        elif a["verdict"] in ("item_defect", "unverified"):
            dropped.append((it["id"], a["verdict"]))
            continue
    out.append(it)

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(out)}문항 -> {OUT}  (제외 {len(dropped)}: {', '.join(i for i, _ in dropped)})")
