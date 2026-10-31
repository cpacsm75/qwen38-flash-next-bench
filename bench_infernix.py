#!/usr/bin/env python3
"""Infernix(OpenAI 호환) 벤치: 지정 토큰 길이의 프롬프트로 prefill/decode/TTFT 측정."""
import json, os, sys, time, urllib.request, pathlib, subprocess, threading

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:20082"
TARGETS = [int(x) for x in (sys.argv[2].split(",") if len(sys.argv) > 2 else ["8192"])]
OUT = sys.argv[3] if len(sys.argv) > 3 else "/data/bench-results/infernix_fp8.json"

CORPUS = pathlib.Path("/data/PolyStrata/docs/DETAILS.md").read_text(encoding="utf-8", errors="replace")
CORPUS = (CORPUS * 20)[:2000000]


def _mem_used_gib():
    info = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    return (info["MemTotal"] - info["MemAvailable"]) / 1048576

def _vram_used_mib():
    try:
        out = subprocess.check_output(["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"], timeout=5)
        return max(int(x) for x in out.decode().split())
    except Exception:
        return None

def _engine_rss_gib():
    try:
        pid = subprocess.check_output(["pgrep","-f", os.environ.get("BENCH_PROC","infernix-serve")], timeout=5).decode().split()[0]
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1048576
    except Exception:
        return None

class Sampler:
    def __init__(self):
        self.base_ram = _mem_used_gib(); self.peak_ram = self.base_ram
        self.peak_vram = _vram_used_mib() or 0; self.peak_rss = _engine_rss_gib() or 0
        self._stop = False
        self.t = threading.Thread(target=self._run, daemon=True); self.t.start()
    def _run(self):
        while not self._stop:
            self.peak_ram = max(self.peak_ram, _mem_used_gib())
            self.peak_vram = max(self.peak_vram, _vram_used_mib() or 0)
            self.peak_rss = max(self.peak_rss, _engine_rss_gib() or 0)
            time.sleep(0.5)
    def stop(self):
        self._stop = True; self.t.join(timeout=2)

def make_prompt(tokens: int) -> str:
    chars = max(1000, tokens * 4)
    body = (CORPUS * (chars // len(CORPUS) + 1))[:chars]
    return "Here is part of a manual:\n\n" + body + "\n\nIn three sentences, what does this software do?"

def run(target: int) -> dict:
    prompt = make_prompt(target)
    payload = {
        "model": os.environ.get("BENCH_MODEL", "Qwen3.8-Flash-Next-FP8-Infernix"),
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
    smp = Sampler()
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
    smp.stop()
    pt = usage.get("prompt_tokens") or target
    ct = usage.get("completion_tokens") or chunks
    dec = None
    if ttft and total > ttft and ct:
        dec = round(ct / (total - ttft), 1)
    rec = {"target_tokens": target, "prompt_tokens": pt, "completion_tokens": ct,
           "eng_prompt_ms": usage.get("t_prompt_ms"), "eng_prefill_tok_s": usage.get("t_prompt_per_second"),
           "eng_decode_tok_s": usage.get("t_predicted_per_second"),
           "ram_base_gib": round(smp.base_ram,1), "ram_peak_gib": round(smp.peak_ram,1),
           "engine_rss_gib": round(smp.peak_rss,1), "vram_peak_mib": smp.peak_vram,
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
