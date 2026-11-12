# Raon-1 mini (한국어 특화) vs Qwen3.8 — 변호사시험 선택형 80문항 비교

측정일: 2026-11-12 · RTX 5090 32GB(450W) · 비교군 동일 문항·동일 채점(법무부 최종정답)

## 결론

1. **한국어 특화 모델이 한국 법 시험을 더 잘 보지는 않았다.** Raon-1 mini Q6 **25/80 (31%)**, Qwen3.8 비검열 Q6 **37/80 (46%)**.
2. **차이는 형사법에서 결정됐다.** 형사법 6/25 vs 14/25. 공법도 10/30 vs 16/30으로 Qwen 우세, 민사법은 Raon이 근소하게 앞섰다(9/25 vs 7/25).
3. **문항 단위로는 17문항을 둘 다 맞히고, Qwen만 20문항, Raon만 8문항.** 즉 우열이 아니라 상보 관계에 가깝다.
4. **속도는 Raon이 압도적이다.** 사고를 끄면 문항당 **0.3초**(Qwen 10.5초). 다만 사고를 켜면 한국 법률 문항에서 **12,000토큰을 다 쓰고도 답을 못 내는** 경우가 발생해 실용 구성이 어렵다.
5. **"한국어 대화 강점"은 "한국 법 지식"과 다른 축이다.** 소득처분 유형 질의에서 Raon은 `상여·배당·기소소득·유보`(3/4), Qwen은 `상여·배당·기부금·기타사외유출`(3/4) — 둘 다 정답 `유보·배당·기타사외유출·상여`를 완전히 맞히지 못했다.

## 환경·구동

| 항목 | 값 |
|---|---|
| 모델 | `KRAFTON/Raon-1-mini-preview-gguf` Q6_K (24.1 GiB, Apache-2.0) |
| 아키텍처 | 30B MoE(A4.3B), 하이브리드 선형 어텐션 18층 + MLA 7층 |
| 런타임 | **llama.cpp 는 마스터 미지원** → KRAFTON 포크(`krafton-ai/llama.cpp`) 빌드 필요 (sm_120, `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120`) |
| 링크 | CUDA 라이브러리 경로를 링커에 넘겨야 함(`-L$CUDA/lib64 -Wl,-rpath,...`), 실행 시 `LD_LIBRARY_PATH` 동일 |
| 메모리 | VRAM 25.3 GiB (Q6, ctx 32768), GPU 단독 구동 |

## 결과

| 팩 | 전체 | 공법 | 민사법 | 형사법 | 문항당 |
|---|---:|---:|---:|---:|---:|
| Qwen3.8 비검열 Q6 (basalt) | **37/80 (46%)** | 16/30 | 7/25 | **14/25** | 10.5초 |
| Raon-1 mini Q6 (llama.cpp, 사고 끔) | 25/80 (31%) | 10/30 | **9/25** | 6/25 | **0.3초** |

문항 단위 교차표: 둘 다 정답 17 · Qwen만 20 · Raon만 8

## 사고(thinking) 동작 — 실무상 중요

- KRAFTON 권장 샘플링은 `temperature 1.0 / top_p 0.95 / top_k 20 / presence_penalty 1.5` 이다.
- **`presence_penalty` 를 빼면 사고가 종료되지 않는다.** 짧은 질문에서도 32,768토큰을 소진하고 `finish=length`, `content=""` 로 끝났다. 권장값을 넣으면 같은 질문이 11.3초·1,682토큰에 정상 종료했다.
- 그러나 **변호사시험 문항(장문 지문 5지선다)에서는 권장값을 줘도 12,000토큰을 넘겨 답을 못 내는 사례가 나왔다**(문항당 77초+). 이 과제에서는 사고를 끄는 구성이 유일하게 실용적이다.
- 사용자가 겪은 "2차 세무회계 문제에서 무한 루프" 증상과 동일 계열의 문제다. 해결책은 ① 권장 샘플링 적용 ② `max_tokens` 상향 ③ 과제를 소문항으로 분해.

## 해석

- 한국어 대화 능력과 한국 법 지식은 별개다. Raon은 한국어로 자연스럽게 쓰지만, 판례·학설 기반 문항에서는 Qwen보다 낮았다.
- 다만 민사법에서 Raon이 앞선 점, 문항 단위 상보성이 높은 점은 앙상블/라우팅의 여지가 있다(어려운 문항만 교차 확인).
- 어느 쪽이든 **폐권 30~46%** 로, 법 실무에 단독 투입은 불가하다. 앞선 보고서의 결론(도구·RAG 필수)이 모델을 바꿔도 유지된다.

## 재현

```
git clone --depth 1 https://github.com/krafton-ai/llama.cpp && cd llama.cpp
CU=/data/cuda-13.1/root/usr/local/cuda-13.1
PATH=$CU/bin:$PATH cmake -B build -G Ninja -DGGML_CUDA=ON \
  -DCMAKE_CUDA_ARCHITECTURES=120 -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXE_LINKER_FLAGS="-L$CU/lib64 -Wl,-rpath,$CU/lib64"
PATH=$CU/bin:$PATH cmake --build build -j 12 --target llama-server

LD_LIBRARY_PATH=$CU/lib64 ./build/bin/llama-server \
  --model raon-1-mini-Q6_K.gguf --port 8082 --ctx-size 32768 --n-gpu-layers 99 --jinja

# 평가 (base URL 에 /v1 을 붙이지 말 것 — 러너가 붙인다)
eval_runner.py http://127.0.0.1:8082 "<gguf path>" out.json \
  --set moj/eval_set_moj_2026-11-12.json --max-tokens 8192
```

## 함정

1. llama.cpp 마스터에는 Raon 아키텍처가 없다(PR #31107 은 병합되지 않고 종료). 포크를 써야 한다.
2. llama-server 의 모델 id 는 **파일 경로 문자열**이다.
3. `presence_penalty` 누락 시 사고 무한 루프.
4. 링크 단계에서 CUDA 경로를 안 주면 `undefined reference to cudaEventSynchronize@libcudart.so.13`.
5. 사고 켠 상태로 80문항을 돌리면 문항당 1분 이상 걸려 측정 자체가 비현실적이다.
