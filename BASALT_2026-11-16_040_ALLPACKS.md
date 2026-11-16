# Basalt 0.4.0 전체 팩 벤치 — Q8 / NVFP4-DQ6_K / NVFP4-DQ8 (2026-11-16)

단일 RTX 5090 32GB, 450W, `basalt-bench -p 16384 -t conv,struct,prose`, 엔진 0.4.0.
서비스는 0.4.0으로 전환·검증 후 기본 팩(unc Q6)으로 복귀. DQ8은 해시 검증 후 측정.

## 결과 (0.4.0, spec 8 기본값)

| test | Q8_0 (179GB) | NVFP4-DQ6_K (123GB) | NVFP4-DQ8 (123GB) |
|---|---:|---:|---:|
| pp16384 | 3833 | 5902 | 5871 |
| tg conv | 78 (76.5%) | 251 (71.4%) | 238 (69.6%) |
| tg struct | 118 (97.7%) | 472 (98.5%) | 453 (98.1%) |
| tg prose | 93 (74.8%) | 244 (—) | 237 (66.5%) |

괄호 안은 draft acceptance. Q8의 KLD 0.0197·top-1 95.36%는 0.3.2 시절 실측(정밀도 기준 유지).

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

원자료: `q8_040_bench.log` + `logs_q8_040/`, `dq8_040_bench.log` + `logs_dq8_040/`,
`nvfp4_spec8_bench.log` + `logs_nvfp4_spec8/` (0.3.2 기준값), `nvfp4_spec10_bench.log` + `logs_nvfp4_spec10/`.
DQ8 무결성: size 132367747589, sha256 `c96e8f30…0e3fe69` 공식값 일치.
