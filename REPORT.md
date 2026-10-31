# RTX 5090 32 GB: Qwen3.8-Flash-Next — PolyStrata Q5/Q8 vs Infernix FP8

Measured **2026-10-31 ~ 11-01 (KST)** on a single RTX 5090 desktop running Ubuntu 26.04 headless.
This report covers long-context serving (256K / 512K / 1M) for three quantizations of the same model.

## Tested software

| Engine | Build | Notes |
| --- | --- | --- |
| PolyStrata | source build, CUDA 13.1 (sm_120), `-DSTRATA_ENABLE_CUDA=ON -DSTRATA_Q6K_EXPERTS=ON -DSTRATA_MMQ_KQUANTS=ON` | UD-Q5_K_XL / Q8_0 (unsloth), MTP on (`--spec 4`, `--mtp mtp/rt`) |
| Infernix | source build `windows-2026.10.18-169-g05f28304-dirty`, CUDA 13.1 | FP8 artifact 5 shards + BF16 ngram, MTP on (bundled drafter), `rope-yarn-factor 2` |

Client: PolyStrata `polystrata.py benchmark` (Q5/Q8) and a streaming OpenAI-compatible harness (`bench_infernix.py`, in this folder) for Infernix.
Raw per-run JSON is beside this file (`q5_*.json`, `q8_*.json`, `infernix_fp8*.json`).

## Hardware and method

- NVIDIA RTX 5090 32 GB (sm_120a), driver 595.99.02; AMD Ryzen 7 9800X3D; 183 GiB RAM; `/data` ext4 NVMe.
- Ubuntu 26.04, **headless target** (`multi-user.target`), GNOME still resident during measurement (it holds ~1.4 GiB VRAM until the first reboot).
- **GPU power limit 450 W** (default 575 W, max 600 W). Kept at 450 W for cable safety; **all numbers here are therefore ~78% of default power**. Final re-measurement at 460 W is planned.
- Q5/Q8: engine timings from PolyStrata's benchmark (prefill/decode), TTFT from the client; VRAM/RAM are machine-wide peaks sampled during the request.
- Infernix: streaming requests with `max_tokens=128`, temperature 0; engine `timings` supply prefill/decode, client supplies TTFT; RAM (machine and engine RSS) and VRAM sampled at 0.5 s intervals.
- Prompts are repeated manual text (~3 chars/token for this corpus); actual token counts come from the engine and are shown in every row. Long-context rows are a single request each — not medians.

## PolyStrata — Qwen3.8-Flash-Next UD-Q5_K_XL

158 GB download, experts 92 GiB, KV int8, context loaded at 1,048,576.

| Prompt tokens | Prefill tok/s | Decode tok/s | TTFT | VRAM peak | RAM peak | MTP accepted |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 266,673 | 4,128.3 | 70.0 | 64.7 s | 31.65 GiB | 121.0 GiB | 66.5% |
| 533,934 | 3,767.2 | 72.7 | 141.9 s | 31.65 GiB | 121.0 GiB | 63.7% |
| 1,000,964 | 3,230.1 | 62.6 | 310.3 s | 31.6 GiB | 121.0 GiB | 60.9% |

## PolyStrata — Qwen3.8-Flash-Next Q8_0

188 GB download, experts 120 GiB, KV int8, context loaded at 1,048,576.

| Prompt tokens | Prefill tok/s | Decode tok/s | TTFT | VRAM peak | RAM peak | MTP accepted |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 266,673 | 3,290.7 | 50.9 | 81.2 s | 31.63 GiB | 142.3 GiB | 63.5% |
| 507,333 | 3,122.5 | 49.2 | 162.7 s | 31.6 GiB | 142.3 GiB | 59.9% |
| 1,000,964 | 2,631.2 | 44.4 | 380.8 s | 31.64 GiB | 151.6 GiB | 60.7% |

Q8 costs ~21–30 GiB more RAM and is 20–40% slower than Q5 at equal context; its only advantage is quantization quality (reference top-1 100% vs 94.6%).

## Infernix — Qwen3.8-Flash-Next-FP8-Infernix

226 GB on disk (model 4×32 GB + 4.7 GB, BF16 ngram 109 GB), KV int8, YaRN factor 2, MTP on (bundled drafter).
Machine RAM 138.2–138.6 GiB, **engine RSS 127.4–127.7 GiB**, VRAM peak 31.4–31.5 GiB, expert cache 4,350 experts (19.9 GiB).

| Prompt tokens | Prefill tok/s | Decode (MTP on) | Decode (MTP off) | TTFT | Expert cache hit |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10,802 | 3,744 | 50.2 | 48.3 | 2.9 s | 50.7% |
| 38,552 | 4,269 | 57.5 | 54.5 | 9.0 s | 69.4% |
| 159,287 | 4,192 | 60.7 | 51.7 | 30.2 s | 33.3% |
| 241,012 | 4,118 | 60.4 | 51.1 | 21.3 s | 47.9% (63.6% prefix cache) |
| 470,419 | 3,788 | 54.6 | 45.7 | 65.0 s | 23.5% |
| 904,378 | 3,373 | 36.4 | — | 268.3 s | 1M via YaRN ×4, prefill-chunk 2048 |

MTP adds +4–5% decode at short prompts and **+17–19%** at long ones. The model's native position count is 262,144; YaRN ×2 raises the ceiling to 524,288. **1M is reachable with `rope-yarn-factor = 4` plus `prefill-chunk = 2048`** — with the default 16,384-token chunk the prefill workspace (7.4 GiB) fails to allocate and the request returns HTTP 500. At 904K tokens decode falls to 36.4 tok/s as KV growth shrinks the expert cache. YaRN ×4 output quality was not evaluated.

## Cross-engine summary (approximately equal context)

| Context | Engine (MTP) | Prompt tokens | Prefill tok/s | Decode tok/s |
| --- | --- | ---: | ---: | ---: |
| ~256K | PolyStrata Q5 (on) | 266,673 | 4,128 | **70.0** |
| ~256K | PolyStrata Q8 (on) | 266,673 | 3,291 | 50.9 |
| ~256K | Infernix FP8 (on) | 241,012 | **4,118** | 60.4 |
| ~512K | PolyStrata Q5 (on) | 533,934 | 3,767 | **72.7** |
| ~512K | PolyStrata Q8 (on) | 507,333 | 3,122 | 49.2 |
| ~512K | Infernix FP8 (on) | 470,419 | **3,788** | 54.6 |
| ~1M | PolyStrata Q5 (on) | 1,000,964 | 3,230 | **62.6** |
| ~1M | PolyStrata Q8 (on) | 1,000,964 | 2,631 | 44.4 |
| ~904K | Infernix FP8 (on) | 904,378 | **3,373** | 36.4 |

Prefill: Infernix FP8 is fastest in every band. Decode: PolyStrata Q5 with MTP is fastest at every length. Q8 is dominated on both axes and only buys quantization quality.

## Caveats

- Power limit 450 W; a 460 W re-run is planned after a headless reboot (expected +5–15% decode from freed VRAM).
- GNOME still held ~1.4 GiB VRAM during these runs.
- Long-context rows are single requests; prefix cache state differs between rows (noted where it mattered).
- Speed alone does not establish output quality; quantization and engine kernels differ.
