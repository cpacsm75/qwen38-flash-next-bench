### Linux FP8 / Dense8 at 512K on an RTX 5090 (184 GiB), 2026-11-03 build vs the 2026-10-31 build

Community numbers from a headless Linux host. Two builds at the same power limit and the same
prompt-file, so the columns are directly comparable.

**Host**: RTX 5090 32 GiB (sm_120a) · Ryzen 7 9800X3D · 183 GiB DDR5-6000 · ext4 NVMe ·
Ubuntu 26.04 headless (`multi-user.target`) · driver 595.99.02 · **GPU power limit 450 W**
(default 575 W, held at 450 W for cable temperature safety) · no other GPU process running.

**Builds**: `05f28304` (2026-10-30, built 10-31, CUDA 13.1) → `048d484d` (2026-11-03, CUDA 13.4).
Both built from source, `Release`, `CMAKE_CUDA_ARCHITECTURES=120a`. Note the 13.4 minimum is
enforced at configure time now; the 13.1 prefix had to be replaced (CUDA 13.2 is the one your
configure step warns about, and we did not try it).

**Prompts**: one request per model, `stream=true`, `max_tokens=128`, greedy, prompt from a fixed
local corpus with the same builder as the earlier reports (`prompt_tokens` is the server's count,
470,055). Pretend nothing else is on the box.

### FP8 — `Qwen3.8-Flash-Next-FP8-Infernix`, ctx 524,288, YaRN factor 2, MTP on, int8 KV

| Build | Prompt tok/s (engine) | Decode tok/s (engine) | Machine RAM peak | VRAM peak |
|---|---:|---:|---:|---:|
| `05f28304` (CUDA 13.1) | 3,788 | 54.6 | 138.5 GiB | 31.4 GiB |
| `048d484d` run 1 (CUDA 13.4) | 3,984.1 | 52.8 | 133.6 GiB | 31.5 GiB |
| `048d484d` run 2 (CUDA 13.4) | 3,997.1 | 54.4 | 133.9 GiB | 31.5 GiB |

Prompt +5.4%; decode is within run-to-run spread (52.8–54.4 against 54.6). RAM peak fell 4.9 GiB.

### Dense8 — `Qwen3.8-Flash-Next-NVIDIA-NVFP4-Dense8-Infernix`, ctx 524,288, YaRN factor 2, int8 KV

| Build | Prompt tok/s (engine) | Decode tok/s (engine) | Machine RAM peak | VRAM peak |
|---|---:|---:|---:|---:|
| `048d484d` | 8,348.8 | 109.2 | 132.5 GiB | 31.5 GiB |

The shipped `dense8` TOML has `max-context = 262144`, so a 470K prompt is rejected with 400 until
`rope-yarn-factor = 2` and `max-context = 524288` are set — measured with a separate TOML.

For reference on the same host at 241K, Dense8 was 8,664 prompt / 140 decode; at 512K it is
8,334 / 104.9 (client-side), the expected cost of doubling the KV.

### Notes

- Commands: `bench_infernix.py <base_url> 390000 <out.json>` with `model` set to the id
  `/v1/models` reports (`…-FP8-Infernix`, `…-NVIDIA-NVFP4-Infernix`); `--config` served with
  `systemd-run` so the engine outlives the harness.
- Limitations: one host, 450 W, one run per point except FP8 (two). No quality or retrieval
  evaluation. Prompt rate at this power limit is not comparable with unlimited-power figures.
- Happy to file these as a `docs/` page instead if that is the preferred place.
