#!/usr/bin/env python3
"""code_eval.py — 코딩 능력 비교: 함수 5개 과제 + 단위테스트 자동 채점.
사용: ./code_eval.py <base_url> <model> <out.json> [--max-tokens N]
함수 본문만 채점한다(테스트 통과 여부). 모델이 낸 코드는 서브프로세스에서 격리 실행(타임아웃 10s).
"""
import argparse, json, re, subprocess, sys, tempfile, time, urllib.request, pathlib, os

TASKS = [
 {"id":"palindrome","name":"is_palindrome",
  "spec":"문자열 s를 받아 회문이면 True, 아니면 False를 반환하라. 대소문자와 공백, 문장부호는 무시한다.",
  "tests":"assert is_palindrome('A man, a plan, a canal: Panama') == True\nassert is_palindrome('hello') == False\nassert is_palindrome('') == True\nassert is_palindrome('가나다라다나가') == True\nassert is_palindrome('No lemon, no melon') == True"},
 {"id":"merge","name":"merge_intervals",
  "spec":"정수 구간 리스트 [(s,e), ...]를 받아 겹치는 구간을 병합한 리스트를 시작값 오름차순으로 반환하라. 끝과 시작이 같은 경우(예: (1,3),(3,5))도 병합한다.",
  "tests":"assert merge_intervals([(1,3),(2,6),(8,10),(15,18)]) == [(1,6),(8,10),(15,18)]\nassert merge_intervals([(1,3),(3,5)]) == [(1,5)]\nassert merge_intervals([]) == []\nassert merge_intervals([(5,7),(1,2)]) == [(1,2),(5,7)]"},
 {"id":"wordfreq","name":"top_k_words",
  "spec":"문자열 text와 정수 k를 받아, 소문자로 바꾸고 영숫자/한글만 남겨 단어를 나눈 뒤 가장 많이 나온 k개 단어를 (단어, 횟수) 튜플 리스트로 빈도 내림차순, 동률이면 사전순 오름차순으로 반환하라.",
  "tests":"r=top_k_words('the cat the dog the bird', 2)\nassert r == [('the',3),('bird',1)], r\nassert top_k_words('a b c', 5) == [('a',1),('b',1),('c',1)]\nassert top_k_words('', 3) == []"},
 {"id":"money","name":"parse_amount",
  "spec":"한국식 금액 문자열을 정수(원)로 변환하라. 예: '1,250,000원' -> 1250000, '3억 4,500만원' -> 345000000, '12,000' -> 12000, '850' -> 850.",
  "tests":"assert parse_amount('1,250,000원') == 1250000\nassert parse_amount('12,000') == 12000\nassert parse_amount('850') == 850\nassert parse_amount('3억 4,500만원') == 345000000"},
 {"id":"dividend","name":"dividend_amount",
  "spec":"가용재원 available, 총채권액 total, 특정 채권액 claim(모두 정수)을 받아 배당액을 원 단위로 내림한 정수를 반환하라. 배당률 = available/total, 배당액 = claim × 배당률(내림). total이 0이면 0을 반환.",
  "tests":"assert dividend_amount(12000000, 48000000, 8000000) == 2000000\nassert dividend_amount(1000000, 3000000, 1000000) == 333333\nassert dividend_amount(100, 0, 50) == 0"},
]

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("model"); ap.add_argument("out")
ap.add_argument("--max-tokens", type=int, default=2048)
ap.add_argument("--reasoning-budget", type=int, default=4096)
a = ap.parse_args()

SYS = "너는 파이썬 프로그래머다. 요구된 함수를 구현한 코드만 ```python 블록으로 출력하라. 설명 금지."

def ask(task):
    p = f"{task['spec']}\n\n함수 이름: {task['name']}\n코드만 출력:"
    body = {"model": a.model,
            "messages": [{"role":"system","content":SYS},{"role":"user","content":p}],
            "max_tokens": a.max_tokens, "temperature": 0}
    if "20084" in a.base:
        body["reasoning_budget_tokens"] = a.reasoning_budget
    req = urllib.request.Request(a.base.rstrip("/")+"/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"}, method="POST")
    if "deepseek.com" in a.base:
        _env = open("/home/cpacsm/.hermes/.env").read()
        _k = re.search(r"^DEEPSEEK_API_KEY=(\S+)", _env, re.M).group(1)
        req.add_header("Authorization", f"Bearer {_k}")
    t0=time.time(); d=json.load(urllib.request.urlopen(req, timeout=1800)); el=time.time()-t0
    ch=(d.get("choices") or [{}])[0]; m=ch.get("message") or {}
    return m.get("content") or "", el

def extract(code):
    m = re.search(r"```(?:python)?\s*(.*?)```", code, re.S)
    body = m.group(1) if m else code
    # 함수 정의부터 끝까지
    return body

def run_tests(task, code):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code + "\n\n" + task["tests"] + "\nprint('OK')\n")
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=15)
        ok = r.returncode == 0 and "OK" in r.stdout
        return ok, (r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "")
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:120]
    finally:
        try: os.unlink(path)
        except OSError: pass

results=[]
for i,t in enumerate(TASKS,1):
    try:
        code, el = ask(t)
        ok, err = run_tests(t, extract(code))
        verdict = "통과" if ok else "실패"
    except Exception as e:
        code, el, err, verdict = "", 0, str(e)[:100], "오류"
    results.append({"id":t["id"],"verdict":verdict,"secs":round(el,1),"err":err,"code_len":len(code)})
    print(f"[{i}/{len(TASKS)}] {t['id']:<12} {verdict:<3} {el:6.1f}s  {err[:70]}", flush=True)

pathlib.Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=1))
ok = sum(1 for r in results if r["verdict"]=="통과")
print(f"\n==== 코딩: {ok}/{len(TASKS)} 통과 · 평균 {sum(r['secs'] for r in results)/len(results):.1f}s ====")
