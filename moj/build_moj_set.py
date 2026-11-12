#!/usr/bin/env python3
"""build_moj_set.py — 변호사시험 선택형(공법·민사법·형사법) 기출에서 평가셋을 만든다.

정답은 법무부 최종정답(answers.csv, KOGL 제1유형)에서 온다 — 모델 판단이 아니라 공식 키.
5지선다이므로 eval_runner.py 가 A~E 를 처리하도록 함께 고쳐 둔다.
"""
import csv
import json
import pathlib
import random

random.seed(20261112)
HERE = pathlib.Path(__file__).resolve().parent
rows = list(csv.DictReader(open(HERE / "questions.csv", encoding="utf-8-sig")))

LETTERS = "ABCDE"
cand = []
for r in rows:
    if r["parse_quality"] != "parsed_with_answer":
        continue
    if r["answer"] not in {"1", "2", "3", "4", "5"}:
        continue
    try:
        ch = json.loads(r["choices_json"])
    except Exception:
        continue
    if len(ch) != 5 or not r["stem"].strip():
        continue
    if int(r["year"]) < 2019:
        continue
    cand.append((r, ch))

per_subject = {"공법": 30, "민사법": 25, "형사법": 25}
out = []
for subj, n in per_subject.items():
    pool = [(r, ch) for r, ch in cand if r["subject"] == subj]
    random.shuffle(pool)
    for r, ch in pool[:n]:
        item = {
            "id": f"MOJ-{subj}-{r['year']}-{r['question_no']}",
            "type": "mc",
            "q": r["stem"].strip(),
            "src": {"exam": r["exam"], "round": r["round"], "year": r["year"],
                    "subject": subj, "url": r["source_article_url"]},
        }
        for i, c in enumerate(ch):
            # '① ' 같은 원문 기호를 떼고 A~E 로 고정
            txt = c.strip()
            if txt[:1] in "①②③④⑤":
                txt = txt[1:].strip()
            item[LETTERS[i]] = txt
        item["a"] = LETTERS[int(r["answer"]) - 1]
        out.append(item)

OUT = HERE / "eval_set_moj_2026-11-12.json"
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(out)}문항 -> {OUT}")
for s in per_subject:
    print(f"  {s}: {sum(1 for x in out if x['src']['subject']==s)}")
print("연도분포:", sorted({x['src']['year'] for x in out}))
