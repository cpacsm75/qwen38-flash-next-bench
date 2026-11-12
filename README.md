# 로컬 엔진 벤치마크 — RTX 5090 (Ubuntu 26.04)

측정일: 2026-10-31 ~ 11-01 (KST) · 헤드리스 Linux

## 문서 (한국어 정본)

| 문서 | 내용 |
|---|---|
| [BASALT_2026-11-12_RAON_VS_QWEN.md](BASALT_2026-11-12_RAON_VS_QWEN.md) | **한국어 특화 모델 비교** — Raon-1 mini Q6 vs Qwen 비검열 Q6, 변호사시험 80문항(31% vs 46%) + 사고 루프 함정 |
| [BASALT_2026-11-12_TOOLS_AND_KNOWLEDGE.md](BASALT_2026-11-12_TOOLS_AND_KNOWLEDGE.md) | **도구가 지식을 대체하는가** — KLD 5팩 실측 + 합성 58문항 + 변호사시험 80문항(도구 유/무) + 속도 A/B |
| [QUALITY_2026-11-04.md](QUALITY_2026-11-04.md) | **품질 평가** — 5개 모델 × (KMMLU 25문항 + 도구호출 5 + RAG 3) |
| [UPGRADE_2026-11-03.md](UPGRADE_2026-11-03.md) | PolyStrata poly.7 / Infernix main 업그레이드 및 512K 벤치 |
| [REPORT.md](REPORT.md) | 512K/256K/1M 컨텍스트 처리량 리포트 |
| [POST_REBOOT.md](POST_REBOOT.md) | 재부팅 후 재측정 |

### 해외 저장소에 게시한 코멘트 (영문 원문)

| 링크 | 게시 내용 |
|---|---|
| [PolyStrata #131](https://github.com/VecSzn/PolyStrata/pull/131) | poly.6 vs poly.7 512K 벤치 + Q8/Q5 품질·도구호출·RAG |
| [Infernix #58](https://github.com/Wallawalla47/Infernix/issues/58) | CUDA 13.4 재빌드 FP8/Dense8 512K + FP8 품질·도구호출·RAG |
| [Xolotl #114](https://github.com/Indras-Mirror/Xolotl/issues/114) | DeepSeek V4 XQ arena/prompt-batch 512K + 로컬 vs 클라우드 품질 |

> 해외 메인테이너 저장소에는 **영문**으로 게시했고, 이 저장소 문서가 **한국어 정본**이다.
> 두 문서의 수치는 동일하며, 상세 로그·원본 JSON은 이 디렉터리에 그대로 있다.

## 다음 과제 (보류·예정)

- [ ] **RAG 재실험** — 사용자 요청으로 보류. 조건 3개를 갖춘 뒤 재개:
      ① 키를 조문으로 검증한 문항셋 ② 살아있는 검색 백엔드(SearXNG 현재 429/CAPTCHA)
      ③ 도구 결과를 받아 재판단하는 에이전트 루프(1회 주입 아님)
- [ ] **법률 문항 재구성** — 조문에서 문항·정답을 자동 생성해 키 오류가 구조적으로 불가능하게
- [ ] **엔진 역할 분담 적용** — XQ(20084)=창작, FP8(20082)=판단·검산, Q5(20080)=속도

## 환경

| 항목 | 값 |
|---|---|
| GPU | NVIDIA RTX 5090 32GB (sm_120a) |
| 드라이버 / CUDA | 595.99.02 / CUDA 13.1 툴킷 |
| **GPU 전력 제한** | **450 W (기본 575 W, 최대 600 W)** — **케이블 발열 위험으로 450 W 고정** |
| CPU | AMD Ryzen 7 9800X3D |
| RAM | 183 GiB (184 GB) |
| OS | Ubuntu 26.04, headless (multi-user.target) |
| 저장소 | `/data` ext4 1.8T (nvme3n1p2) |
| 측정 도구 | `polystrata.py benchmark` (PolyStrata), 자체 API 측정 (Infernix/Xolotl) |

> **모든 수치는 450 W 전력 제한에서 측정됨.** 기본 575 W 대비 약 78%.
> 프리필(연산 집약)은 전력 영향을 크게 받으므로, 무제한 환경과 직접 비교하지 말 것.
>
> **예정:** 다음 주 전체 모델 다운로드 완료 후 최종 벤치는 **기본 575 W의 80% 수준(≈460 W)**으로 재설정해 측정한다.
> (사용자 상시 운용 정책: 500 W 이하, 케이블 발열 회피)

## PolyStrata — Qwen3.8-Flash-Next UD-Q5_K_XL

- 다운로드 158 GB · experts 92 GiB (전량 RAM 상주) · KV int8 · MTP on
- 컨텍스트 1,048,576으로 로드

| 구간 | 실제 토큰 | 프리필 tok/s | 디코드 tok/s | TTFT | VRAM 피크 | RAM 피크 | 캐시 hit | MTP 수락 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| short | 63 | 74.9 | 53.9 | 0.88s | 31.57 GiB | 120.0 GiB | 0.70 | 64.6% |
| 256K | 266,673 | 4,128.3 | 70.0 | 64.7s | 31.65 GiB | 121.0 GiB | 0.79 | 66.5% |
| 512K | 533,934 | 3,767.2 | 72.7 | 141.9s | 31.65 GiB | 121.0 GiB | 0.82 | 63.7% |
| 1M | 1,000,964 | 3,230.1 | 62.6 | 310.3s | 31.6 GiB | 121.0 GiB | 0.80 | 60.9% |

## PolyStrata — Qwen3.8-Flash-Next Q8_0

- 다운로드 188 GB · experts 120 GiB · KV int8 · MTP on · 컨텍스트 524288

| 구간 | 실제 토큰 | 프리필 tok/s | 디코드 tok/s | TTFT | VRAM 피크 | RAM 피크 | 캐시 hit | MTP 수락 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| short | 63 | 61.7 | 46.4 | 1.06s | 31.6 GiB | 142.2 GiB | 0.69 | 61.2% |
| 256K | 266,673 | 3,290.7 | 50.9 | 81.2s | 31.63 GiB | 142.3 GiB | 0.73 | 63.5% |
| 512K | 507,333 | 3,122.5 | 49.2 | 162.7s | 31.6 GiB | 142.3 GiB | 0.73 | 59.9% |
| 1M | 1,000,964 | 2,631.2 | 44.4 | 380.8s | 31.64 GiB | 151.6 GiB | 0.74 | 60.7% |

**Q5 vs Q8 (동일 조건):** Q5가 프리필 +25%, 디코드 +40% 빠르고 RAM도 21GiB 적게 씀.
Q8의 이점은 품질(top-1 94.6% vs 100%)뿐 — 실사용은 Q5 권장.

## Infernix — Qwen3.8-Flash-Next-FP8-Infernix

- 다운로드 226 GB (모델 4×32GB+4.7GB, BF16 ngram 109GB) · KV int8 · YaRN factor 2 · **MTP on**(아티팩트 내장 drafter)
- 머신 RAM 138.2~138.6 GiB 사용 · **엔진 RSS 127.4~127.7 GiB** · VRAM peak 31.4~31.5 GiB · expert cache 4,350개

| 실제 토큰 | 프리필 tok/s | 디코드(MTP on) | 디코드(MTP off) | TTFT | 캐시 hit |
|---:|---:|---:|---:|---:|---:|
| 10,802 | 3,744 | 50.2 | 48.3 | 2.9s | 50.7% |
| 38,552 | 4,269 | 57.5 | 54.5 | 9.0s | 69.4% |
| 159,287 | 4,192 | 60.7 | 51.7 | 30.2s | 33.3% (20.6%) |
| 241,012 | 4,118 | 60.4 | 51.1 | 21.3s | 47.9% (63.6%) |
| 470,419 | 3,788 | 54.6 | 45.7 | 65.0s | 23.5% (47.8%) |
| 904,378 | 3,373 | 36.4 | — | 268.3s | yarn 4배, prefill-chunk 2048 |

MTP 이득: 짧은 구간 +4~5%, 긴 구간 **+17~19%**.

**1M 가능 조건:** `rope-yarn-factor = 4`(native 262,144 × 4 = 1,048,576) + `prefill-chunk = 2048`.
기본 chunk(16384)에서는 1M 요청의 prefill workspace 7.4GiB가 VRAM에 안 잡혀 OOM(HTTP 500).
1M에서 decode는 36.4 tok/s까지 떨어짐(KV 증가로 expert cache 축소). YaRN 4배 품질 검증은 미실시.

## 3엔진 비교 (근사 동일 구간)

| 구간 | 엔진 | 실제 토큰 | 프리필 tok/s | 디코드 tok/s |
|---|---|---:|---:|---:|
| ~256K | Poly Q5 (MTP on) | 266,673 | 4,128 | **70.0** |
| ~256K | Poly Q8 (MTP on) | 266,673 | 3,291 | 50.9 |
| ~256K | Infernix FP8 (MTP on) | 241,012 | **4,118** | 60.4 |
| ~512K | Poly Q5 (MTP on) | 533,934 | 3,767 | **72.7** |
| ~512K | Poly Q8 (MTP on) | 507,333 | 3,122 | 49.2 |
| ~512K | Infernix FP8 (MTP on) | 470,419 | **3,788** | 54.6 |
| ~1M | Poly Q5 (MTP on) | 1,000,964 | 3,230 | **62.6** |
| ~1M | Poly Q8 (MTP on) | 1,000,964 | 2,631 | 44.4 |
| ~904K | Infernix FP8 (MTP on) | 904,378 | 3,373 | 36.4 |

**요약:** 프리필은 Infernix FP8이 가장 빠르고, 디코드는 MTP가 켜진 Poly Q5가 압도적.
Q8은 메모리·속도 모두 열세라 실사용 가치는 품질뿐.

## Xolotl — DeepSeek-V4.1-Flash-1017 XQ (V4)

- GGUF 163GB 재조립(16 parts) + Engram 테이블 202.8GB 추출 · `ds41_generate --serve` · ctx 262144 · DSpark/MTP 미사용
- 머신 RAM 75GiB · 엔진 RSS 73.8GiB · VRAM 31.1GiB

| 실제 토큰 | 프리필 tok/s | 디코드 tok/s | TTFT | RAM(머신) |
|---:|---:|---:|---:|---:|
| 10,257 | 420 | 37.7 | 25.5s | 74.8GiB |
| 37,388 | 743 | 36.8 | 51.0s | 75.1GiB |
| 153,067 | 754 | 37.6 | 154.8s | 75.2GiB |
| 232,223 | 696 | 36.6 | 115.2s | 75.3GiB |

참고: 4090 기준 공개 수치(프리필 289~409, 디코드 25.7)보다 높음. Engram·expert 일부가 NVMe에서 스트리밍되어 RAM 사용은 75GiB로 낮음.

## Infernix — Qwen3.8-Flash-Next NVIDIA NVFP4 Dense8 ("Dense8")

- Windows 볼륨에서 복사한 77GB 아티팩트 + 공용 NVFP4 ngram 49GB · KV int8 · MTP on · ctx 262144
- 머신 RAM 133.6~133.9GiB · 엔진 RSS 127.2GiB · VRAM peak 31.4~31.6GiB

| 실제 토큰 | 프리필 tok/s | 디코드 tok/s | TTFT |
|---:|---:|---:|---:|
| 10,802 | 9,285 | 145.0 | 1.2s |
| 38,552 | 10,180 | **153.0** | 3.8s |
| 159,287 | 9,126 | 140.4 | 13.9s |
| 241,012 | 8,664 | 140.2 | 10.2s(캐시) |

**압도적:** FP8 대비 프리필 2.4배(9,100~10,200), 디코드 2.5배(140~153). 긴 구간에서도 140 유지.
NVFP4 4비트 양자라 품질 트레이드오프는 별도 확인 필요. 비검열(Uncensored) NVFP4도 같은 ngram을 공유하며 /data/models/infernix-uncensored에 준비됨.

## PolyStrata Q5 비검열 (Qwen3.8-Flash-Next-Uncensored Q5_K_M, 4.85bpw)

- 아티팩트: `AtomicChat/Qwen3.8-Flash-Next-Uncensored-GGUF` Q5_K_M 3샤드 100GiB (orcarouter 계보, 게이트 아님)
- 팩: `tools/iq_pack.py --compat-bf16` → 변환 460텐서, dense 1.38GiB, expert/PLE 바이트 불변
- PLE: 원본이 Q4_1(엔진 미지원) → unsloth Q5 샤드3의 Q8_0 PLE를 단독 GGUF로 추출해 `--ple-gguf`로 사용
- 런컨픽: `/data/PolyStrata/strata-orca-unc-q5.json`, 포트 20083, ctx 262,144, KV int8

| 실제 토큰 | 프리필 tok/s | 디코드 tok/s | TTFT |
|---:|---:|---:|---:|
| 10,802 | 3,700 | 136.0 | 2.96s |
| 38,552 | 5,757 | 167.1 | 6.75s |

콜드 스타트(전문가 65GiB 로드 중) 첫 측정은 prefill 1,180으로 나오므로 웜 값과 구분해 기록한다.

---

## 2026-11-03 업그레이드 재벤치 (PolyStrata poly.7 · Infernix 11-03 빌드 · DeepSeek arena 130)

전체 표와 상세는 [`UPGRADE_2026-11-03.md`](UPGRADE_2026-11-03.md). 요점만:

| 엔진 | 이전 | 이후 | 512K 프리필 / 디코드 |
|---|---|---|---|
| PolyStrata Q5 | poly.6 (20d839d) | **poly.7 (fabae0d)** | 3,863.3 / 74.0 (poly.6: 3,767.2 / 72.7) |
| Infernix FP8 | 10-31 빌드 (CUDA 13.1) | **11-03 tip (CUDA 13.4)** | 3,991 / 53.5 (구빌드: 3,788 / 54.6) — 프리필 **+5.4%**, RAM −4.9 GiB |
| Infernix Dense8 | 동일 빌드, YaRN2 TOML | — | **8,333.9 / 104.9** (512K 첫 측정치) |
| DeepSeek V4 XQ | arena 60 | **arena 130** | 452,727토큰: 1,056.4 / 42.0 (arena 110: 968.3 / 42.0) |

- 딥시크는 arena 130에서 file tier 10,054 → **1,609**. 같은 조건의 256K는 1,274.2 / 45.1로 512K보다 프리필 +20.6%.
- `--prompt-batch 4096 + --vram-margin 0.5`는 **채택 안 함**: expert seed +45개(+3%)뿐이고 prefill만 느려짐(7분 초과).
- 상류 제출: PolyStrata **PR #131**, Infernix **issue #58**, Xolotl **issue #114**.
