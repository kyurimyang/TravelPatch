# TripPatch

> 여행 중 깨진 일정을 **새로 짜지 않고**, 원래 일정에 대한 **최소한의 수정(patch)** 과 그 근거를 계산해 주는 웹서비스

**데모:** https://travel-patch.vercel.app

늦잠, 갑작스러운 비, 예약한 식당의 임시휴무. 여행 중에 일정이 틀어지면 기존 AI 플래너는 일정을 처음부터 다시 만들어 줍니다. 하지만 여행자가 원하는 건 새 일정이 아니라 **"원래 계획에서 무엇을, 얼마나, 왜 바꿔야 하는가"** 입니다.

TripPatch는 일정 복구를 **사용자 우선순위가 가중된 최소 교란(Minimal Perturbation) 재스케줄링 문제**로 정식화합니다. 결과는 새 일정이 아니라 원래 일정에 대한 diff입니다.

```
LLM은 번역기  — 앞: 자연어 → JSON,  뒤: 수치 → 문장
결정은 솔버   — DP + 순서 국소탐색
판정은 검증기 — 솔버와 독립된 재시뮬레이션
```

---

## 핵심 특징

| | 보장하는 것 | 어떻게 |
|---|---|---|
| ① | **하드 제약 위반 0건** | 솔버 결과는 반드시 독립 검증기(`validator.py`)를 통과해야 응답에 포함. 검증기는 솔버를 import하지 않고 처음부터 재시뮬레이션 |
| ② | **결정론** | 엔진은 LLM·네트워크·DB·현재 시각에 의존하지 않는 순수 함수. 같은 입력이면 같은 출력(정렬·tie-break 포함) |
| ③ | **변경량을 수치로 최소화** | Recovery Cost(삭제·단축·대체·순서·시각·이동·의도 손실의 가중합)를 목적함수로 최적화 |
| ④ | **반사실 설명** | "오모테산도를 살리면 하라주쿠를 30분 더 줄여야 해요" — 항목을 고정하고 재계산한 실제 차이 |
| ⑤ | **설명 속 숫자는 LLM이 만들지 않음** | 숫자·장소명은 솔버 값에서 템플릿으로 채우고, LLM은 문장만 다듬음 |

## 비교 실험 결과

일정 10개 × 사건 5종(지연·우천·휴무·체력·연장) = **50개 시나리오**를 다섯 방법으로 풀었습니다.

| 방법 | 제약 위반율 | 해 없음 | 보존율 (위반 없는 해) | RC (위반 없는 해) | 평균 ms |
|---|---|---|---|---|---|
| (a) Right-shift (전부 뒤로 밀기) | 62% | 0 | 93.8% | 1.405 | 0.3 |
| (b) Greedy | 62% | 0 | 75.4% | 4.524 | 0.2 |
| (c) LLM 단독 | 83% | 21 | 78.2% | 4.026 | 2,743 |
| (d) LLM + 검증기 (재시도 포함) | 0% | 42 | 82.9% | 3.368 | 4,651 |
| **(e) TripPatch 엔진** | **0%** | **5** | **90.2%** | **1.686** | **148** |

- LLM 단독은 답의 83%가 영업시간·예약·복귀 마감 등 하드 제약을 어깁니다. 검증기를 붙이면 위반은 0%가 되지만, 50개 중 42개에서 통과하는 답을 끝내 내지 못했습니다.
- 엔진은 위반 0%를 유지하면서 45개 시나리오에서 해를 냈습니다. 해가 없는 5개는 예약 시각이 이미 지났거나(1), 예약된 옥외 일정이 비 시간대에 걸리거나(3), 요청한 연장이 뒤 예약과 충돌하는(1) 경우입니다. 엔진은 이런 입력에서 위반안을 내놓지 않고, 막는 항목을 짚어 사용자에게 "불가"를 알립니다.
- Right-shift의 보존율이 높은 것은 위반을 감수하고 아무것도 지우지 않은 19개만 집계되었기 때문입니다.
- LLM 방법은 3회 반복해 편차도 기록했습니다(`eval/results/repeat_summary.md`). 모델: `gpt-4o-mini`.

전체 결과: [`eval/results/summary.md`](eval/results/summary.md) · [`results.csv`](eval/results/results.csv)

## 복구 알고리즘

**결정 변수** — 남은 각 일정에 연산 하나: 유지 · 이동 · 단축(최소 길이까지 5분 단위) · 삭제 · 대체 · 연장

**하드 제약** — 운영시간, 예약 시각 고정, 이동시간 포함 비겹침, 호텔 복귀 마감, `must` 등급 삭제 금지, 사건에서 온 제약(도보 상한 등), 전략별 추가 제약(최소 버퍼 등)

**목적함수 — Recovery Cost**

```
RC = w1·D_drop + w2·D_shrink + w3·D_sub + w4·D_order + w5·D_time + w6·D_move + w7·D_intent
```

| 항 | 의미 |
|---|---|
| D_drop | 삭제한 항목의 가치 합 |
| D_shrink | Σ 가치 × (줄인 시간 / 원래 시간) |
| D_sub | Σ 가치 × (1 − 대체 가능도) |
| D_order | 원래 순서와의 Kendall tau 거리(뒤집힌 쌍 수) |
| D_time | 시작 시각 이동량 합 |
| D_move | 이동시간 증가량 |
| D_intent | 하루 전체에서 사라진 의도 태그 수 |

사용자에게는 RC 대신 **보존율** `1 − (D_drop + D_shrink + D_sub) / Σ 가치`를 보여줍니다.

**동작**

1. 남은 일정을 원래 순서로 놓고 **DP**: 상태 = (처리한 일정 수, 현재 시각 5분 단위, 마지막 장소). 하드 제약을 어기는 전이는 버림
2. **국소탐색**: 인접 교환·한 개 이동으로 만든 순서마다 DP를 다시 돌려 D_order를 더한 최저안 선택
3. **전략 프리셋**(관광 보존·음식 보존·여유 보존 등)마다 반복해 후보 2–3개를 나란히 제시. 프리셋은 프롬프트가 아니라 가중치·제약의 변경
4. 모든 후보를 **독립 검증기**가 재시뮬레이션, 위반 시 폐기
5. 사용자가 항목을 고정하거나 되살리면 그 조건으로 재계산

## 요청 흐름

```
일정 붙여넣기 → LLM 구조화(JSON 강제) → 장소 매칭(Google Places) → 등급 3탭(꼭·좋음·선택)
                                                    ── 여행 전 ──
상황 한 줄 입력 ("늦잠 잤어") → LLM 해석 → 칩으로 확인·수정 → 규칙 기반 제약 변환
→ 충돌 탐지 → 최적화 → 검증 → 이유 문장화 → diff + 보존율 → 고정·되살리기 → 확정
                                                    ── 여행 중 ──
```

여행 중 입력은 한 줄 + 탭 2–3번으로 끝나도록 설계했고, 무거운 입력은 여행 전에 받습니다.
첫 화면은 일정표가 아니라 **"원래 vs 복구 + 보존율"** diff이며, 변경된 항목에만 "덧댄 패치" 시각 언어를 씁니다.

## 기술 스택

| 구분 | 사용 |
|---|---|
| Frontend | React 19 · Vite · TypeScript(strict) · 모바일 우선 웹 |
| Backend | FastAPI · Python 3.12 · Pydantic v2 · uv |
| 엔진 | 자체 DP + 순서 국소탐색 (외부 솔버 없음) |
| DB·인증 | Supabase (PostgreSQL, Auth, RLS) |
| LLM | OpenAI structured output (`llm/provider.py`로 추상화) |
| 외부 API | Google Places, Google Routes(구현 완료, 기본 꺼짐 — 직선거리 × 보정계수로 대체) |
| 테스트 | pytest · vitest |
| 배포 | Vercel(FE) · Render(BE) · Supabase |

## 디렉터리 구조

```
├─ backend/
│  ├─ app/
│  │  ├─ engine/        # ★ 순수 함수. LLM·DB·네트워크 import 금지
│  │  │  ├─ optimizer_dp.py      # 고정 순서 DP
│  │  │  ├─ local_search.py      # 순서 국소탐색
│  │  │  ├─ validator.py         # 독립 재시뮬레이션
│  │  │  ├─ cost.py              # Recovery Cost, 보존율
│  │  │  ├─ counterfactual.py    # "X를 살리면?" 재계산
│  │  │  ├─ constraint_builder.py, conflict_detector.py, presets.py, reasons.py ...
│  │  │  └─ baselines.py         # 비교 실험용 right-shift / greedy
│  │  ├─ llm/           # 일정 파싱, 상황 해석, 대체 장소 질의, provider
│  │  ├─ services/      # I/O: DB, Places, Routes, LLM을 엮는 계층
│  │  ├─ routers/       # FastAPI 라우터
│  │  └─ schemas/       # Pydantic 모델 (API·엔진 공용)
│  └─ tests/
│     ├─ engine/        # 단위 테스트
│     └─ scenarios/     # 기준 시나리오 A–F, eval50, midday30
├─ frontend/src/        # pages · components · api(OpenAPI 생성 타입) · styles(디자인 토큰)
├─ eval/                # 비교 실험 스크립트와 결과
├─ supabase/migrations/ # DB 마이그레이션 SQL
└─ docs/decisions.md    # 설계 결정 기록 (날짜 · 결정 · 이유 · 버린 대안)
```

## 로컬 실행

### 환경 변수

루트에 `.env` (커밋 금지):

```
OPENAI_KEY=
GOOGLE_PLACES_API_KEY=
GOOGLE_ROUTES_API_KEY=        # ROUTES_TRAVEL_ENABLED=1 일 때만 사용
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

`frontend/.env.local`:

```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
uv run pytest -q          # 외부 API·DB 테스트 제외
uv run pytest -m live     # 실제 API 호출 테스트
```

> Windows에는 IANA 타임존 데이터가 없어 `Asia/Tokyo` 관련 테스트가 실패할 수 있습니다. `uv pip install tzdata`로 해결됩니다.

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run gen:api           # 백엔드 OpenAPI에서 API 타입 재생성
npm test
```

### 비교 실험

```bash
# (a) (b) (e)만 — API 키 없이 실행 가능
python -m eval.run --scenarios backend/tests/scenarios/eval50 --out eval/results

# (c) (d) LLM 방법 포함. 응답은 디스크에 캐시되어 재실행이 무료이고 재현 가능
python -m eval.run --scenarios backend/tests/scenarios/eval50 --out eval/results --with-llm
```

## 설계 결정

알고리즘 선택, 스키마, 트레이드오프는 [`docs/decisions.md`](docs/decisions.md)에 `날짜 · 결정 · 이유 · 버린 대안` 형식으로 기록했습니다. 예:

- 검증기는 솔버 코드를 import하지 않음 — 같은 버그를 공유하면 검증이 무의미하므로
- 순서 거리는 Levenshtein이 아니라 Kendall tau — "몇 쌍의 순서가 뒤집혔나"가 사용자가 느끼는 변화에 가까움
- 기획서의 시나리오 A 정답(오모테산도 삭제)보다 엔진의 해가 RC·보존율 모두 좋아, 가중치를 정답에 맞추지 않고 테스트 기대값을 속성 기반(위반 0, `must` 유지)으로 변경
- Google 데이터는 약관상 허용되는 것만 저장 (`place_id` 영구, 좌표 29일, 이동시간은 저장하지 않음)

## 범위

- **지원:** 전 세계 도시, 한 여행 = 한 도시, 하루 단위 복구
- **하지 않음:** 일정 생성·장소 추천, 실시간 위치(GPS), 실시간 교통·날씨 API, 실제 예약 변경, 다도시 이동

---

실전웹서비스개발(2026-2) 1인 프로젝트 · 2026.10 – 2026.11
