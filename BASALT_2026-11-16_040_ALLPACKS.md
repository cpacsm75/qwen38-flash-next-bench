# Basalt 0.4.0 전체 팩 벤치 — Q8 / UD-Q6_K_XL / NVFP4-DQ6_K / NVFP4-DQ8 (2026-11-16~17)

단일 RTX 5090 32GB, 450W, `basalt-bench -p 16384 -t conv,struct,prose`, 엔진 0.4.0.
서비스는 0.4.0으로 전환·검증 후 기본 팩(unc Q6)으로 복귀. DQ8은 해시 검증 후 측정.

## 결과 (0.4.0, spec 8 기본값)

| test | Q8_0 (179GB) | UD-Q6_K_XL (161GB) | NVFP4-DQ6_K (123GB) | NVFP4-DQ8 (123GB) |
|---|---|---:|---:|---:|---:|
| pp16384 | 3833 | 4435 | 5902 | 5871 |
| tg conv | 78 (76.5%) | 100 (74.3%) | 251 (71.4%) | 238 (69.6%) |
| tg struct | 118 (97.7%) | 150 (98.4%) | 472 (98.5%) | 453 (98.1%) |
| tg prose | 93 (74.8%) | 99 (73.6%) | 244 (—) | 237 (66.5%) |

괄호 안은 draft acceptance. Q8의 KLD 0.0197·top-1 95.36%는 0.3.2 시절 실측(정밀도 기준 유지).

## 정밀도 (KLD 게이트, BF16 기준, 100 chunks)

| pack | KLD mean | median | p99 | top-1 | PPL | gate sec |
|---|---:|---:|---:|---:|---:|---:|
| Q8_0 | 0.01970 | 0.00408 | 0.2405 | 95.36% | 3.2776 | 649 |
| NVFP4-DQ8 | **0.05642** | 0.01201 | 0.6454 | **92.06%** | 3.2833 | 255 |
| NVFP4-DQ6_K | 0.06169 | 0.01362 | 0.7180 | 91.67% | 3.3067 | 252 |

DQ8은 DQ6_K보다 KLD 약 8% 낮고 top-1 +0.39%p — 예상 방향 그대로, 폭은 작다. Q8(0.0197)과는 여전히 3배 차이가 난다. 즉 **정밀도 서열: Q8 > DQ8 > DQ6_K**, 속도 서열은 역방향(DQ6_K ≥ DQ8 > Q8)이다.

## 해석

- **DQ8 vs DQ6_K**: decode 약 3~5% 차이(DQ6_K 우세), prefill 동급. 정밀도 차이는 KLD 게이트로 별도 확인 필요 — 속도만으로는 팩 선택 근거가 안 된다.
- **Q8**: 정밀도 최상(KLD 0.0197)이지만 decode는 NVFP4의 1/3 수준. 숫자·법률 검증용, 벌크용 아님.
- **외부 듀얼 GPU 측정치**(사용자 제공: DQ6_K conv 116~117, DQ8 conv 116~117 수준)와 비교하면, 싱글 5090 + 0.4.0이 약 2배 앞선다. 이전 열세는 0.3.2 엔진 탓이었다.
- **측정 함정 (재발 방지)**: 백그라운드 작업의 메모리 4GB cgroup 제한이 걸리면 엔진이 RAM 상주를 포기하고 SSD로 떨어져 5 tok/s가 나온다. 벤치는 반드시 `systemd-run --user --scope -p MemoryMax=infinity` 안에서 돌릴 것. 증상: `resident RAM mode does not fit (available RAM ~1.6 GiB)` 경고 + conv 한 자릿수.

## 재현

```sh
systemctl --user stop basalt.service
systemd-run --user --scope -p MemoryMax=infinity --unit=basalt-bench bash -c '
  export LD_LIBRARY_PATH=/data/cuda-13.1/root/usr/local/cuda-13.1/targets/x86_64-linux/lib
  cd /data/basalt/basalt-v0.4.0-linux-x64
  ./bin/basalt-bench --model <PACK>.basalt --gpu 0 --engine ./bin/basalt \
    --fixtures ./data/bench -p 16384 -t conv,struct,prose --logs <OUT>'
systemctl --user start basalt.service
```

원자료: `q8_040_bench.log` + `logs_q8_040/`, `q6_040_bench.log` + `logs_q6_040/`,
`dq8_040_bench.log` + `logs_dq8_040/`,
`nvfp4_spec8_bench.log` + `logs_nvfp4_spec8/` (0.3.2 기준값), `nvfp4_spec10_bench.log` + `logs_nvfp4_spec10/`.
DQ8 무결성: size 132367747589, sha256 `c96e8f30…0e3fe69` 공식값 일치.

## 법률 80문항 (DQ8, 2026-11-17, T=0)

| 조건 | 공법 | 민사법 | 형사법 | 합계 |
|---|---|---:|---:|---:|
| 무도구 | 15/30 | 5/25 | 14/25 | **34/80** |
| 도구(신 하네스) | 16/30 | 10/25 | 8/25 | **34/80** |

참고: 구 하네스 도구 15/80은 무효(lbox 모듈 부재로 조회 에러가 컨텍스트 오염).
신 하네스 = 도구 통합(lookup_law 하나로, prec 호출 시 MCP+lbox 의미검색 합침) + 판례 2000년 이전 제외·2015년 이후 우선 + 결과 6000자.
KLD 서열(Q8>DQ8>DQ6_K)과 시험 점수 무관 재확인 — 정밀도와 시험 점수는 따로 논다.
