# 2026-11-14 작업 정리 — 판례 인덱스 구축, 도구/클라우드 모델 비교, Edge0 설치

대상 모델: **Qwen3.8-Flash-Next Unc UD-Q6_K_XL**(basalt), **Raon-1 mini**(로컬 llama.cpp / KRAFTON 클라우드), **Edge0-145B NVFP4**
시험지: 변호사시험 선택형 80문항 (공법 30 / 민사법 25 / 형사법 25, 법무부 최종정답), T=0

## 1. 판례 코퍼스 인덱스 구축 (완료)

`lbox/lbox_open` 판례 15만 건 원문을 **의미검색 인덱스**로 만들었다.

| 항목 | 값 |
|---|---:|
| 문서 | 150,000건 (원문 4.96억 자) |
| 청크 | **383,110** (1,200자, 150자 겹침, 문서당 최대 4청크) |
| 임베딩 | `qwen3-embedding:4b-q8_0` — **2560차원** (Dify KB와 동일 규격) |
| 벡터 파일 | 3.7 GB (`index_corpus.vec.npy`) |
| 처리 속도 | 5.8~7.0 청크/s (steampc01 RX 9060 XT) |

**원본 대조 보존**: 청크마다 `doc`(lbox 문서 id) · `off`(원문 오프셋) · `year`(선고연도) · `text`(원문 그대로)를 저장.
검색 결과는 `[판례 ID · 연도 · 오프셋] 본문` 형태로 돌려주므로 인용 전 원문 대조가 가능하다(`lbox_search.py --verify`).
원본 jsonl 3종은 SHA-256과 함께 `ORIGINALS.sha256`에 고정했고, 인덱스는 원본을 대체하지 않는다.

부수 인덱스: 판결요지 20,808청크, 공개 PDF(서울회생법원 실무자료·실무준칙, 사법정책연구원 보고서) 1,973쪽 → 3,274청크.

### 임베딩 백엔드 실측 (중요)

| 백엔드 | 속도 | 472k청크 소요 | 비고 |
|---|---:|---:|---|
| steampc01 Ollama `4b-q8_0` | 5.8~7.0 /s | 22 h | Dify와 동일 규격, 채택 |
| 이 PC 5090 llama.cpp `0.6B` | 62 /s | 2.1 h | **차원·풀링이 달라 Dify와 불일치 → 폐기** |
| 이 PC CPU `0.6B` (20스레드) | 10.4 /s | 12.6 h | 규격 불일치로 폐기 |

**규칙**: 인덱싱과 질의는 반드시 같은 엔드포인트·같은 모델·같은 풀링. 섞으면 무관한 문서가 1순위로 올 수 있다.
같은 모델이라도 러너가 다르면(GGUF llama.cpp vs Ollama) 벡터가 미세하게 어긋나므로 혼용하지 않는다.

## 2. 도구·RAG가 정답률을 올리는가 (80문항)

| 조건 | 정답 | 비고 |
|---|---:|---|
| 도구 없음 | 37/80 (46%) | 기준 |
| **자율 도구(MCP 법령·판례)** | **44/80 (55%)** | 모델이 스스로 조회 |
| 강제 주입(검색어 자동 생성 후 시스템프롬프트 삽입) | 31/80 (39%) | 모든 과목에서 기준 이하 |
| 강제 주입(lbox 의미검색) | 8~10/20 (20문항) | 조사가 8건 살리고 11건 죽임 |

동일 20문항 대조군: 도구 없음 10/20 · **빈 도구(껍데기) 7/18** · 실제 도구 13/20.
→ **호출 형식이 아니라 돌아온 내용**이 성적을 만든다.

T=0 결정성 확인: 같은 프롬프트 4회 모두 동일 출력 → 위 차이는 샘플링 잡음이 아니다.
단 80문항의 95% 신뢰구간은 ±10%p로 조건 간 겹침이 있으므로, 순위는 방향으로만 인용해야 한다.

## 3. Raon-1 mini: 로컬 vs 클라우드

| | 로컬(llama.cpp 8082) | 클라우드(`raon-api.krafton.ai`) |
|---|---|---|
| 모델 | Raon-1 mini Q6_K | `raon-1-mini-preview` |
| 접속 | 8082 | OpenAI 호환 `/v1/chat/completions`, 키 인증 |
| 80문항 | **25/80 (31%)** (공법 10, 민사 9, 형사 6) | **측정 불가** |
| 속도 | 0.3 s/문항 (사고 끔) | — |

**클라우드는 긴 한국어 법률 문항에서 답을 내지 못했다.** 모든 토큰을 reasoning 으로만 소모하고 `content` 가 빈 문자열로 돌아온다.

| 설정 | 결과 |
|---|---|
| `max_completion_tokens` 256 / 512 / 1,024 / 4,096 / 8,192 | 전부 `content=""`, reasoning 이 예산 전액 소모 (48~98초) |
| `reasoning_effort` none / minimal / low | 무시됨 |
| `presence_penalty` 1.5 / 2.0 | 효과 없음 (로컬에서는 이 값이 사고 폭주를 멈췄다) |

공식 문서에도 "Raon 은 세 API 모두 사고를 항상 켜며 `enable_thinking` 은 무시된다"고 명시돼 있다.
따라서 **객관식 벤치와 도구 호출 벤치 둘 다 클라우드 Raon 으로는 수행할 수 없다** — 답이 나오기 전에 예산이 끝나기 때문이다.
짧은 일반 대화는 정상 응답(54토큰, 추론 33토큰)하므로 연결 자체는 문제가 없다.

로컬 Raon 이 같은 증상을 보였을 때는 llama.cpp 에서 `presence_penalty 1.5` 로 해결했으나, 클라우드는 해당 손잡이가 없다.

## 4. Edge0-145B NVFP4 설치 (측정은 새벽 자동 실행)

Qwen3.8-Flash-Next 에서 파생된 latent MoE (145B 총 / 10.12B 활성, expert 512·top-10, 입력 2560→1792 압축).

| 항목 | 값 |
|---|---|
| 모델 | `Edge0/Edge0-145B-NVFP4` 112.9 GB (45파일), `inspect` 로 전 파일 검증 |
| 엔진 | `edge0-strata` (Strata 포크) 빌드 완료 — CUDA 13.1, sm_120, ninja |
| 런처 | `edge0-infer` (cpu preset) 빌드 완료 |
| 서버 | 포트 8000, `systemd --user edge0.service` 등록 (basalt·raon 과 상호 배타) |
| 대시보드 | 8091 드롭다운에 `[엔진] Edge0-145B NVFP4` 추가, `/api/switch {"cfg":"edge0"}` |

RAM 상주 최대화: `--model-option ple-io=ram`(PLE 51.2GB 를 RAM 에 mlock) + `--resident-budget-gib 110` + `LimitMEMLOCK=infinity`.

공식 24GB 실측: chat decode 79.6 / agent 98.3 tok/s (NVFP4). 이 PC(32GB)는 그 이상 예상.
새벽 03:00 자동 측정(`dawn_test.sh`): Edge0 80문항(도구 없음/도구 사용) + 로컬 Raon 80문항 → 종료 후 basalt 복귀.

## 5. 막힌 것

- **법제처 OPEN API 장애 (2026-11-14)**: `/DRF/*` 가 `/sorry/sorry.html` 로 리다이렉트. MCP 프록시 경유 `search_law`·`get_law_text`·`search_decisions` 전부 `EXTERNAL_API_ERROR`.
  그 결과 조세심판원·고용노동부·행정심판·등기예규 수집이 0건으로 실패했고, 법조문 정답지(조문 원문) 기반 벤치도 보류 상태다.
  복구되면 재개하도록 감시 스크립트를 준비해 두었다(사용자 지시로 현재는 중지).
- 카카오/타 기관 자료는 PDF 직링크가 없어(JS 렌더링) 수집 불가 — 예규·규칙은 MCP 텍스트로 대체.

## 6. 재현

```sh
# 판례 인덱스
EMB_URL=http://100.110.89.27:11434/api/embed EMB_MODEL=qwen3-embedding:4b-q8_0 \
  ./.venv-py/bin/python lbox_index_par.py --src precedent_corpus_train.jsonl \
  --out index_corpus --chunk 1200 --overlap 150 --batch 32 --workers 1 \
  --chunks-per-doc 4 --field precedent

# 검색(최신 가중)
./.venv-py/bin/python lbox_search.py "취소판결의 기속력" -k 2 --min-year 2000 --recency 0.05

# 도구 조건
./agentic_eval.py http://127.0.0.1:8080 "<model>" out.json \
  --set moj/eval_set_moj_2026-11-12.json --turns 3 --reasoning-budget 1024 --max-tokens 8192

# 클라우드 Raon
./cloud_bench.py out.json --set moj/eval_set_moj_2026-11-12.json --max-tokens 2048
```

원자료: `moj/moj_uncq6_{notools,tools,dummy20,research20,twostage80}.json`, `moj/lbox_scores.json`, `moj/moj_raon_*.json`
