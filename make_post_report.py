#!/usr/bin/env python3
"""헤드리스 재부팅 후 재벤치 결과를 POST_REBOOT.md로 정리한다."""
import json, pathlib, datetime

D = pathlib.Path("/data/bench-results")

def load(name):
    p = D / name
    return json.loads(p.read_text()) if p.exists() else None

def long_run(name):
    d = load(name)
    if not d:
        return None
    runs = [r for r in d.get("runs", []) if r.get("prompt", "").startswith("long")]
    return runs[-1] if runs else None

def main():
    rows = []
    pairs = [
        ("Poly Q5 256K", "q5_256k.json", "q5_post_256k.json"),
        ("Poly Q5 512K", "q5_512k.json", "q5_post_512k.json"),
    ]
    for label, pre_name, post_name in pairs:
        pre, post = long_run(pre_name), long_run(post_name)
        if post:
            rows.append((label, pre, post))

    fp8_pre = {r["prompt_tokens"]: r for r in (load("infernix_fp8_mtp.json") or [])}
    fp8_post = load("fp8_post.json") or []
    for r in fp8_post:
        pt = r["prompt_tokens"]
        pre = fp8_pre.get(pt)
        rows.append((f"Infernix FP8 {pt:,} tok", pre, r))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 헤드리스 재부팅 후 재벤치 — {now}", "",
             "GNOME(약 1.4GiB VRAM) 없이, 전력 450W 고정 상태에서 다시 측정한 결과입니다.", "",
             "| 항목 | 실제 토큰 | 프리필 tok/s (전 → 후) | 디코드 tok/s (전 → 후) | TTFT s (전 → 후) | VRAM GiB (후) | RAM GiB (후) |",
             "| --- | ---: | --- | --- | --- | ---: | ---: |"]
    for label, pre, post in rows:
        pt = post.get("prompt_tokens")
        def pair(key, fmt="{:.1f}"):
            a = pre.get(key) if pre else None
            b = post.get(key)
            if b is None:
                return "-"
            try:
                return f"{fmt.format(a)} → {fmt.format(b)}" if a is not None else f"- → {fmt.format(b)}"
            except (TypeError, ValueError):
                return "-"
        vram = post.get("vram_peak_gib") or (post.get("vram_peak_mib", 0) / 1024 if post.get("vram_peak_mib") else None)
        ram = post.get("ram_peak_gib")
        vram_s = f"{vram:.1f}" if vram else "-"
        ram_s = f"{ram:.1f}" if ram else "-"
        lines.append(f"| {label} | {pt:,} | {pair('prefill_tok_s')} | {pair('decode_tok_s')} | "
                     f"{pair('ttft_s')} | {vram_s} | {ram_s} |")
    lines += ["", "원본: `q5_post_*.json`, `fp8_post.json`, `post_reboot.log`.", ""]
    out = D / "POST_REBOOT.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", out)

if __name__ == "__main__":
    main()
