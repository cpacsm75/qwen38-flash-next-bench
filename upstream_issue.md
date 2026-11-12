## Hardware

- RTX 5090 32 GB (sm_120), power limit **450 W**, driver 595.99.02 / CUDA 13.2
- 183 GiB RAM, Ubuntu, single card
- release binary v0.3.2 (no source build), int8 KV, `--vision dynamic`

## Packs and placement

| pack | file | experts | decode | placement |
|---|---:|---:|---:|---|
| `UD-Q6_K_XL` | 161 GiB | 102 GiB | **93–98 tok/s** | 78.0 GiB page-locked in RAM + 28.9 GiB VRAM, `pcie=0.0%`, load 21 s |
| `Q8_0` | 179 GiB | 120 GiB | **79–84 tok/s** | 120 GiB in RAM, `pcie=0.0%` |

Prefill (Q6, 13K prompt): **6,954–7,074 tok/s**. Draft acceptance 73–87%, expert-cache hit 77–80%.

## Long context (needle test, fact buried mid-document)

| setup | prompt | found | prefill | total |
|---|---:|---|---:|---:|
| Q6 YaRN×2 (ctx 524288) | 451,354 | yes | 6,424 | 70.3 s |
| Q6 no scaling (ctx 524288) | 451,354 | yes | 6,434 | 70.1 s |
| Q6 YaRN×4 (ctx 1048576) | 864,224 | yes | 5,230 | 165.2 s |
| Q6 no scaling (ctx 1048576) | 864,224 | yes | 5,214 | 165.8 s |
| Q8 YaRN×2 | 451,354 | yes | 6,549 | 68.9 s |
| Q8 YaRN×4 | 864,224 | yes | 5,325 | 162.3 s |

YaRN vs no scaling: **0.15–0.5%** — no measurable speed cost. Retrieval still worked at 864K with no scaling at all (3.3× the trained 262,144).

## Two things that may be worth a look

**1. A memory-limited cgroup silently disables the resident tier.** Running the engine inside a 4 GiB memory cgroup (a systemd scope) made it report `available RAM (1.45 GiB)` and refuse the resident complement, so 78 GiB of experts stayed in the file: **6 tok/s instead of ~95**, with only `warning: resident RAM mode does not fit` naming RAM. The machine had 174 GiB free — the clamp came from `memory.max` on the cgroup. The same binary outside that scope reported `resident RAM mode: 91.43 GiB of experts in RAM (page-locked)`. Suggest the warning name the cgroup limit when that is what clamped the reading, since `free` looks healthy the whole time.

**2. An unset `reasoning_budget_tokens` can return an empty answer.** With `max_tokens` 900 the request spent all 900 tokens on reasoning and returned **0 characters** of content (`finish_reason=length`, no warning). The same prompt with `reasoning_budget_tokens: 400` answered in 8.4 s. A note on the `done` line, or defaulting the budget, would save the guesswork.

**3. (documentation)** `rope-scaling` is fixed for the run, which is easy to miss: applying YaRN ×2 globally to reach 524,288 changed 3 of 22 answers on a short-context Korean exam (21/22 → 18/22, same pack, temperature 0). We now keep YaRN in separate configs and switch only for long-document work. Worth a sentence next to the setting.

## Quality (not the official KLD gate)

No BF16 base file is published, so this is a 22-item Korean professional exam (10 accounting, 5 calculation/trap, 7 statute questions with audited answer keys) at temperature 0: **21/22 for both packs**, same single wrong item. Tool calling (5 scenarios) scored 5/5 by intent.

Full write-up (Korean): https://github.com/cpacsm75/qwen38-flash-next-bench/blob/main/BASALT_2026-11-10.md
