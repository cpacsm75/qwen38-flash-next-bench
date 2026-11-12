#!/usr/bin/env python3
"""make_hard_set.py — 팩 간 정밀도 차이를 실제로 구분하는 고난도 문항 세트 생성기.

설계 원칙
  1) 정답 키는 모델이 아니라 코드가 계산한다(합계·회전율·이자·단가 등).
     → 키 오류로 인한 오채점이 구조적으로 불가능.
  2) 난이도는 '주의력'에서 나온다: 긴 표 합산, 다단계 계산, 문서 내 숫자 회수,
     단위 변환, 부정/다중조건. 약한 양자화가 먼저 무너지는 지점들.
  3) 오답 보기는 '흔한 실수'로 만든다(행 하나 누락, 조건 무시, 단위 무시).
     → 찍어서 맞을 확률을 낮춘다.

사용: ./make_hard_set.py [out.json]
"""
import json
import pathlib
import random
import sys

random.seed(20261112)
HERE = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "eval_set_hard_2026-11-12.json"

items = []
_n = {}


def nid(cat):
    _n[cat] = _n.get(cat, 0) + 1
    return f"{cat}-{_n[cat]-1}"


def won(v):
    return f"{v:,}"


def mc(q, correct, distractors, cat):
    """정답 + 오답 3개 → 보기 셔플 후 문자키 확정."""
    opts = [correct] + distractors
    assert len(opts) == 4, opts
    assert len(set(opts)) == 4, f"중복 보기: {opts}"
    correct = opts[0]
    random.shuffle(opts)
    letters = "ABCD"
    key = letters[opts.index(correct)]
    d = {"id": nid(cat), "type": "mc", "q": q}
    for i, o in enumerate(opts):
        d[letters[i]] = o
    d["a"] = key
    items.append(d)


def free(q, answer, cat):
    items.append({"id": nid(cat), "type": "free", "q": q, "a": str(answer)})


# ── A. 긴 표 합산·조건부 집계 (15행) ─────────────────────────────
NAMES = ["갑", "을", "병", "정", "무", "기", "경", "신", "임", "계", "자", "축", "인", "묘", "진"]
for k in range(10):
    rows = []
    for i, nm in enumerate(NAMES):
        amt = random.randrange(1_150_000, 98_500_000, 1_000)
        rows.append((nm + "상사", amt, random.choice(["확정", "보류"])))
    table = "\n".join(f"{i+1}. {n}  {won(a)}원  {s}" for i, (n, a, s) in enumerate(rows))
    total = sum(a for _, a, _ in rows)
    hwak = sum(a for _, a, s in rows if s == "확정")
    # 오답: 행 하나 누락 / 확정액 중복 계상 / 확정액 하나 누락
    h_rows = [a for _, a, s in rows if s == "확정"]
    d1 = total - rows[-1][1]
    d2 = hwak + max(h_rows)
    d3 = hwak - min(h_rows)
    mc(f"다음 채권자 명세표(단위: 원)에서 총 채권액과 '확정' 채권액의 합계를 구하라.\n\n{table}",
       f"{won(total)} / {won(hwak)}", [f"{won(d1)} / {won(hwak)}",
                                      f"{won(total)} / {won(d2)}",
                                      f"{won(total)} / {won(d3)}"], "TableSum")

# ── B. 다단계 회계·법률 계산 (free) ─────────────────────────────
for k in range(12):
    ar1 = random.randrange(40_000_000, 890_000_000, 10_000)
    ar2 = ar1 + random.randrange(-60_000_000, 75_000_000, 10_000)
    rev = int((ar1 + ar2) / 2 * random.choice([2.4, 3.6, 5.1, 7.3, 9.8, 12.5, 16.2]))
    turn = round(rev / ((ar1 + ar2) / 2), 1)
    free(f"기초 매출채권 {won(ar1)}원, 기말 매출채권 {won(ar2)}원, 매출액 {won(rev)}원이다. "
         f"매출채권회전율을 소수 첫째 자리까지 구하라(반올림).", f"{turn:.1f}", "MultiStep")

for k in range(8):
    supply = random.randrange(1_100_000, 47_000_000, 100)
    rate = random.choice([10, 20])
    total = supply + supply * rate // 100
    free(f"부가가치세율 {rate}%일 때 공급대가가 {won(total)}원(세포함)이다. 공급가액은 얼마인가? "
         f"세는 10원 미만 절사로 계산한다.", f"{won(supply)}", "MultiStep")

for k in range(6):
    p = random.randrange(50_000_000, 900_000_000, 100_000)
    r = random.choice([3.5, 4.2, 5.0, 6.8, 7.5])
    m = random.choice([7, 9, 11, 13])
    interest = int(p * r / 100 * m / 12)  # 원 단위 절사(round는 .5 이상에서 1원 틀림)
    free(f"원금 {won(p)}원, 연이율 {r}%, 기간 {m}개월, 단리 기준이다. 이자액은 얼마인가?(원 단위 절사)",
         f"{won(interest)}", "MultiStep")

# ── C. 문서 내 숫자 회수(needle) + 파생 계산 ─────────────────────
FILLER = [
    "제1조(목적) 이 약정은 채무자의 회생절차에서 조사위원이 제출하는 조사보고서의 작성 기준과 "
    "근거자료의 확인 방법에 관하여 필요한 사항을 정함을 목적으로 한다.",
    "제2조(정의) 이 약정에서 사용하는 용어의 뜻은 다음 각 호와 같다. 1. '근거자료'라 함은 "
    "거래명세서, 세금계산서, 계좌이체내역, 차용증, 판결정본 그 밖에 채권의 발생을 증명하는 일체의 서류를 말한다.",
    "제3조(보고서의 기재사항) 조사보고서에는 채권자별 채권의 발생원인, 금액, 변제기, 담보의 유무, "
    "시효의 진행 상황 및 부인권 행사 대상 여부를 기재하여야 한다.",
    "제4조(자료의 보관) 조사위원은 근거자료를 전자적 형태로 보관하여야 하며, 그 보관기간은 절차 종결일로부터 "
    "5년으로 한다. 다만 관계 법령에 다른 규정이 있는 경우에는 그에 따른다.",
]
for k in range(8):
    target = random.randrange(12_000_000, 780_000_000, 100_000)
    marker = (f"※ 참고: 본 건 관련 채권신고서 접수 결과, 신고된 채권 총액 중 확인된 금액은 "
              f"{won(target)}원으로 조사되었다.")
    paras = []
    for j in range(60):
        paras.append(random.choice(FILLER))
        if j == 37:
            paras.append(marker)
    doc = "\n".join(paras)
    derived = round(target * 0.15)
    free(f"다음 문서에서 '확인된 금액'을 찾아, 그 금액의 15%를 원 단위로 구하라.\n\n{doc}",
         f"{won(derived)}", "Needle")

# ── D. 단위·표기 변환 함정 ───────────────────────────────────────
CASES = [
    (12_000_000, "만원", "1200"),
    (357_400_000, "만원", "35740"),
    (85_000_000, "억원", "0.85"),
    (1_250_000_000, "억원", "12.5"),
    (940_500_000, "만원", "94050"),
]
for amt, unit, ans in CASES:
    free(f"{won(amt)}원을 {unit} 단위로 나타내면 얼마인가? 숫자만 출력하라.", ans, "Unit")

for ko, ans in [("삼억 오천만", "350,000,000"), ("십이억 사천만", "1,240,000,000"),
                ("칠백육십오만", "7,650,000")]:
    free(f"'{ko}'을 원 단위 숫자로 쓰시오(콤마 포함, '원' 생략).", ans, "Unit")

# ── E. 부정형·다중조건 (mc) ─────────────────────────────────────
# 4개 항목에서 "합계의 25% 미만"은 유일하게 성립한다(3개가 25%를 넘으면 합이 75% 초과,
# 남은 하나가 반드시 25% 미만). 그래서 작은 항목 1개 + 큰 항목 3개로 구성한다.
for k in range(6):
    small = random.randrange(80_000_000, 400_000_000, 1_000_000)
    big = int(small * 78 / 22 / 3) // 1_000_000 * 1_000_000  # 나머지 3개 균등(각 25% 초과)
    big = max(big, small * 2)
    items_ = [small, big, big + 3_000_000, big - 2_000_000]
    random.shuffle(items_)
    total = sum(items_)
    thr = total * 25 // 100
    below = [i for i, a in enumerate(items_) if a < thr]
    assert len(below) == 1, (items_, thr)
    rows = "\n".join(f"{i+1}) {won(a)}원" for i, a in enumerate(items_))
    correct = f"{below[0]+1}번 {won(items_[below[0]])}원"
    distract = [f"{i+1}번 {won(items_[i])}원" for i in range(4) if i != below[0]]
    mc(f"다음 중 금액이 전체 합계({won(total)}원)의 25% 미만인 항목은?\n\n{rows}",
       correct, distract, "Negation")

# ── 자체 검증: 키 중복·빈값·보기 중복 ───────────────────────────
assert len({it["id"] for it in items}) == len(items)
for it in items:
    assert it["a"], it
    if it["type"] == "mc":
        assert len({it["A"], it["B"], it["C"], it["D"]}) == 4, it["id"]
OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
cats = {}
for it in items:
    cats[it["id"].split("-")[0]] = cats.get(it["id"].split("-")[0], 0) + 1
print(f"{len(items)}문항 -> {OUT}")
for c, n in sorted(cats.items()):
    print(f"  {c:<12} {n}")
