#!/usr/bin/env python3
"""Infernix(OpenAI 호환) 벤치: 지정 토큰 길이의 프롬프트로 prefill/decode/TTFT 측정."""
import json, sys, time, urllib.request, pathlib

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:20082"
TARGETS = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["8192"])]
OUT = sys.argv[3] if len(sys.argv) > 3 else "/data/bench-results/infernix_fp8.json"

CORPUS = pathlib.Path("/data/PolyStrata/docs/DETAILS.md").read_text(encoding="utf-8", errors="replace")
CORPUS = (CORPUS * 20)[:2000000]

def make_prompt(tokens: int) -> str:
    chars = max(1000, tokens * 4)
    body = (CORPUS * (chars // len(CORPUS) + 1))[:chars]
    return "Here is part of a manual:\n\n" + body + "\n\nIn three sentences, what does this software do?"

def run(target: int) -> dict:
    prompt = make_prompt(target)
    payload = {
        "model": "Qwen3.8-Flash-Next-FP8-Infernix",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    t0 = time.time(); ttft = None; usage = {}; chunks = 0
    with urllib.request.urlopen(req, timeout=3600) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                d = json.loads(data)
            except json.JSONDecodeError:
                continue
            if d.get("usage"):
                usage = d["usage"]
            if d.get("timings"):
                usage = dict(usage, **{("t_"+k): v for k, v in d["timings"].items()})
            ch = (d.get("choices") or [{}])[0]
            delta = ch.get("delta") or {}
            if ttft is None and (delta.get("content") or delta.get("reasoning_content")):
                ttft = time.time() - t0
            if delta.get("content"):
                chunks += 1
    total = time.time() - t0
    pt = usage.get("prompt_tokens") or target
    ct = usage.get("completion_tokens") or chunks
    dec = None
    if ttft and total > ttft and ct:
        dec = round(ct / (total - ttft), 1)
    rec = {"target_tokens": target, "prompt_tokens": pt, "completion_tokens": ct,
           "eng_prompt_ms": usage.get("t_prompt_ms"), "eng_prefill_tok_s": usage.get("t_prompt_per_second"),
           "eng_decode_tok_s": usage.get("t_predicted_per_second"),
           "ttft_s": round(ttft, 2) if ttft else None, "total_s": round(total, 2),
           "prefill_tok_s": round(pt / ttft, 1) if ttft else None, "decode_tok_s": dec}
    print(json.dumps(rec, ensure_ascii=False), flush=True)
    return rec

def main():
    out = pathlib.Path(OUT)
    results = json.loads(out.read_text()) if out.exists() else []
    done = {r["target_tokens"] for r in results}
    for t in TARGETS:
        if t in done:
            continue
        results.append(run(t))
        out.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print("written", OUT, flush=True)

if __name__ == "__main__":
    main()
