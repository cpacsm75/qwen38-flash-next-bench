#!/usr/bin/env python3
"""rag_key.py — 2.25bpw가 closed-book에서 틀린 3문항에 '정확한 조문'을 주고 재시험.
문항별로 해당 조문 원문만 주입한다(검색 아님, 정답 근거를 직접 제공).
"""
import json, re, time, urllib.request, pathlib

SET = {i["id"]: i for i in json.loads(pathlib.Path("/data/bench-results/eval_set_2026-11-04.json").read_text(encoding="utf-8"))}
BASE = "http://127.0.0.1:20084"
MODEL = "deepseek-v4.1-flash-1017-xq"

CTX = {
"Law-0": """[경비업법 시행규칙 제23조(경비원의 명부)]
경비업자는 법제18조제1항에 따라 다음 각 호의 장소에 별지 제14호서식의 경비원 명부를 작성ㆍ비치하여 두고, 이를 항상 정리하여야 한다. 1. 주된 사무소 2. 영제5조제3항에 따른 출장소 3. 집단민원현장
[경비업법 시행규칙 제24조의3(경비원 근무상황 기록부)]
① 경비업자는 경비업무를 수행하는 경비원의 인적사항, 배치일시, 배치장소, 배치폐지일시 및 근무여부 등 근무상황을 기록한 근무상황기록부를 작성하여 주된 사무소 및 출장소에 갖추어 두어야 한다. ② 경비업자는 제1항에 따른 근무상황기록부를 1년 동안 보관하여야 한다.""",

"Law-1": """[경비업법 시행규칙 제18조(무기의 관리수칙 등)]
⑤ 시설주는 다음 각 호의 특수경비원에 대하여 무기를 지급해서는 안 되며, 지급된 무기가 있는 경우 이를 즉시 회수해야 한다. <개정 2021. 12. 31.>
1. 형사사건으로 인하여 조사를 받고 있는 사람
2. 사직 의사를 표명한 사람
3. 정신질환자
4. 그 밖에 무기를 지급하기에 부적합하다고 인정되는 사람""",

"Law-9": """[청원경찰법 제2조(정의)]
이 법에서 "청원경찰"이란 다음 각 호의 어느 하나에 해당하는 기관의 장 또는 시설ㆍ사업장 등의 경영자가 경비(이하 "청원경찰경비"라 한다)를 부담할 것을 조건으로 경찰의 배치를 신청하는 경우 그 기관ㆍ시설 또는 사업장 등의 경비를 담당하게 하기 위하여 배치하는 경찰을 말한다. 1. 국가기관 또는 공공단체와 그 관리하에 있는 중요 시설 또는 사업장 2. 국내 주재 외국기관 3. 그 밖에 행정안전부령으로 정하는 중요 시설, 사업장 또는 장소
[청원경찰법 제3조(청원경찰의 직무)]
청원경찰은 제4조제2항에 따라 청원경찰의 배치 결정을 받은 자(이하 "청원주"라 한다)와 배치된 기관ㆍ시설 또는 사업장의 구역을 관할하는 경찰서장의 감독을 받아 그 경비구역만의 경비를 목적으로 필요한 범위에서 「경찰공무원법」에 따른 경찰관의 직무를 수행한다.""",
}

TRUE = {"Law-0": "A", "Law-1": "A", "Law-9": "D"}

def ask(it, ctx):
    p = (f"다음 근거 조문을 적용해 문제를 푼다.\n\n=== 근거 ===\n{ctx}\n=== 끝 ===\n\n"
         f"문제: {it['q']}\n\nA. {it['A']}\nB. {it['B']}\nC. {it['C']}\nD. {it['D']}\n\n정답 보기 문자 하나만 출력:")
    body = {"model": MODEL, "messages": [
        {"role": "system", "content": "한국어 객관식 문제다. 근거 조문에 따라 판단하고 보기 문자 하나만 출력하라."},
        {"role": "user", "content": p}],
        "max_tokens": 1024, "temperature": 0, "reasoning_budget_tokens": 4096}
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time(); d = json.load(urllib.request.urlopen(req, timeout=900)); el = time.time() - t0
    c = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    m = re.search(r"\b([ABCD])\b", c.upper())
    return (m.group(1) if m else ""), el

res = []
for k in ("Law-0", "Law-1", "Law-9"):
    got, el = ask(SET[k], CTX[k])
    ok = got == TRUE[k]
    res.append({"id": k, "correct": TRUE[k], "got": got, "ok": ok, "secs": round(el, 1)})
    print(f"[{k}] {'정답' if ok else '오답'} 확정={TRUE[k]} 낸답={got or '-'} ({el:.1f}s)", flush=True)

pathlib.Path("/data/bench-results/rag_key_ds41.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(f"\n==== 조문 주입 후: {sum(1 for r in res if r['ok'])}/3 (closed-book은 0/3) ====")
