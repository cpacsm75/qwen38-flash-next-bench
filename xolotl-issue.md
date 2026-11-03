### RTX 5090 / 184 GiB Linux: 512K and 256K numbers for V4 XQ, and what `--arena-gib` does on a box this size

Numbers from a headless Linux host running `IndrasMirror/DeepSeek-V4.1-Flash-1017-XQ-Uncensored`
**V4** (163 GB, `rank-1017-v4.bin`) through `tools/v41/serve/serve_ds41.py`, on a card with more
VRAM and much more RAM than the card's reference machine. Posted because the model card's tier
table is scaled for 24 GB + 90 GB, and the arena knob looks different at 32 GB + 184 GB.

**Host**: RTX 5090 32 GiB · Ryzen 7 9800X3D · 183 GiB DDR5-6000 · ext4 NVMe · Ubuntu 26.04
headless · driver 595.99.02 · CUDA 13.1 · **GPU power limit 450 W** (default 575 W, held for cable
temperature; so prompt rates are not comparable with unlimited-power figures) · engine is the only
GPU process.

**Build**: `1dad2ad` (2026-10-31), `build-xolotl/ds41_generate`, no re-quantisation beyond the
served settings below.

**Config**: `--ctx 524288`, `--experts gpu`, no `--kv-q8` / `--kv-fp4` (so KV stays BF16),
`--conversation-cache-mib 8192 --conversation-cache-slots 2`, one request per point,
`max_tokens 128`, greedy, same local corpus for every arm, prompt token counts are the server's.

### Tier split against `--arena-gib` (ctx 524288, 452,727-token prompt)

| arena | experts in VRAM | experts in RAM arena | NVMe file tier | prompt tok/s | decode tok/s | RAM peak |
|---:|---:|---:|---:|---:|---:|---:|
| 60 (default) | 1,591 (at 256K ctx) | 5,306 | 10,054 | not measured at 512K | — | — |
| 110 | 1,494 | 11,128 | 4,232 | 968.3 | 42.0 | 120.8 GiB |
| **130** | 1,494 | **13,751** | **1,609** | **1,056.4** | 42.0 | 141.1 GiB |

`--arena-gib 130` is where the curve flattens: file tier falls 84% from the default 60, prompt rate
+9.1% over 110, decode unchanged (42.0 — consistent with the card's "decode is RAM-bandwidth bound"
note). 130 GiB pinned still leaves ~42 GiB free on this host.

### 256K against 512K at the same settings (arena 130)

| prompt tokens | prompt tok/s | decode tok/s | TTFT |
|---:|---:|---:|---:|
| 232,201 | **1,274.2** | **45.1** | 182.2 s |
| 452,727 | 1,056.4 | 42.0 | 428.6 s |

So the earlier 37K point (743.1 / 36.8) was not a "short context is faster" signal — it ran at
arena 60. With the arena equalised, 256K is the better operating point: +20.6% prompt, +7.4% decode.

### Conversation cache

`serve: conversation cache: parked 153067 tokens in 39.6 ms` / `restored 153052 tokens (pool,
partial) in 5.4 ms` — restoring a 153K-token conversation costs 5 ms against minutes of re-prefill,
which is the main practical lever at these context lengths. Storage is 3.4–3.9 KB/token, so a 470K
conversation is ~1.7 GB; the default 8 GiB pool with 2 slots covers two such conversations.

### An arm that did not help: smaller `--prompt-batch`

`--prompt-batch 4096 --vram-margin 0.5` at arena 130, same 452,727-token prompt: the VRAM expert
seed went 1,494 → 1,539 (+45, +3%), live VRAM during the request fell 31.1 → 18.8 GiB, and the
prompt was still running after 7 minutes, where the 8192 batch had finished its whole point in
7.1 minutes. The workspace saving does not become expert capacity — the seed is decided at load and
the freed VRAM stays headroom for the elastic KV — so the arm trades prompt speed for nothing.
Stopped, not adopted.

### Notes and limitations

- One run per point; VRAM/RAM peaks are the machine's, not the engine's alone.
- `--arena-gib 130` is a pinned 130 GiB (`cudaHostRegister`), so it cannot be swapped out; 130 was
  chosen over 140+ to keep page cache for the file tier.
- Not measured here: `--kv-q8`/`--kv-fp4` (KV is BF16 in all rows), `--prompt-batch` above the
  default 8192, `--tier-batch-pcie`, and any quality or retrieval check.
- Happy to re-run anything on this box if a different profile is more useful.
