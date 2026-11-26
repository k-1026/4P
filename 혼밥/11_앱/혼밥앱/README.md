# 혼밥 밥친구 — 인수인계 문서 (2026-11-26)

대구 동성로 혼밥 식당 추천 앱. 화면 하나(HTML)와 파이썬 에이전트 서버로 되어 있다. 파이썬은 표준 라이브러리만 쓴다.

> **공개 저장소에 올리지 말 것.** `data/`의 가게 DB와 `public/index.html`에는 지도 링크가 들어 있다. GitHub는 **Private** 저장소로 만든다.

## 1. 폴더

| 경로 | 내용 |
|---|---|
| `public/index.html` | 앱 화면 전체 (가게 목록 391곳이 안에 들어 있음) |
| `api/recommend.py` | Vercel 함수: `POST /api/recommend` |
| `api/config.py` | Vercel 함수: `/config.js` (카카오맵 키) |
| `agents/` | 조율자와 에이전트, 시험 코드 |
| `data/혼밥_동성로.db` | 가게 DB (SQLite, 읽기만 함) |
| `data/store_ids.json` | 가게 번호. **지우지 말 것** (일기·찜이 번호로 가게를 기억함) |
| `distance_agent.js` | 거리 규칙의 원본(JS). 서버는 `agents/distance_rules.py`를 쓴다 |
| `run_local.py` | PC에서 실행 |

## 2. PC에서 실행

1. `.env.example`을 `.env`로 복사하고 키를 채운다.
2. `python run_local.py` → http://localhost:8770

| 환경 변수 | 어디서 받나 | 없으면 |
|---|---|---|
| `KMA_API_KEY` | 공공데이터포털 (기상청 단기예보·ASOS) | 날씨 에이전트를 빼고 추천 |
| `KAKAO_JS_KEY` | 카카오 개발자 콘솔 > 앱 > JavaScript 키 | 지도가 안 뜸 |

키 값은 저장소에 없다. 원래 담당자에게 직접 받거나 새로 발급한다.

## 3. 시험

PowerShell에서 파일을 하나씩 돌린다.

```
cd agents
Get-ChildItem test_*.py | ForEach-Object { $_.Name; python $_.Name }
```

`python -m unittest discover`는 쓰지 말 것 (`test_weather.py` 때문에 중간에 끝난다). `test_distance_parity.py`는 node가 있을 때만 돈다.

## 4. Vercel 배포

1. 이 폴더를 **Private** GitHub 저장소로 올린다.
2. Vercel에서 **Add New > Project**로 그 저장소를 가져온다. Framework Preset은 **Other**, 빌드 명령은 비워 둔다(`vercel.json`에 설정되어 있음).
3. **Settings > Environment Variables**에 `KMA_API_KEY`, `KAKAO_JS_KEY`를 넣고 배포(이미 배포했다면 Redeploy)한다.
4. 카카오 개발자 콘솔 > 앱 > 플랫폼 키 > JavaScript 키 > **JavaScript SDK 도메인**에 `https://<프로젝트>.vercel.app`을 추가한다. 안 하면 지도가 401로 실패한다.
5. 핸드폰에서 확인: MBTI → 순위 → 업종 → 예산 → 추천 시작 → 위치 허용 → 지도 탭.

명령 줄로 할 때: `npx vercel` (미리보기) → `npx vercel --prod`.

**배포 전에 알아 둘 것**
- Vercel 배포는 **아직 한 번도 해 보지 않았다.** PC에서 Vercel처럼 요청을 나눠 받는 방식으로만 확인했다.
- 배포 주소를 아는 사람은 누구나 열 수 있다. 팀만 쓰려면 Vercel의 Deployment Protection을 켠다.
- 위치는 서버에 저장하지 않는다. 날씨 조회에는 약 1km로 줄인 위치만 쓴다.
- 해외 지역 서버에서 기상청 API가 느리거나 막히면 Vercel의 Function Region을 서울(`icn1`)로 바꾼다.

## 5. 지금의 추천 규칙

- **가중치 (총합 10):** 거리 2점 고정. 나머지 8점은 사용자가 정한 순위대로 1위 40% · 2위 30% · 3위 20% · 4위 10% (날씨·자리·새로움·가격).
- **후보:** 고른 업종 안에서 1km 이내 가까운 20곳.
- **가격** (`price_agent.py`): 1인 메뉴 가격 중앙값, 후보끼리 비교. 고른 예산 초과는 탈락. 4,000원 미만 꼬치·접시류는 낱개 값이라 뺀다.
- **혼밥** (`solo_agent.py`): '혼밥하기 좋아요' 순위 8점 + 1인석 확인 2점(DB 또는 내 일기).
- **상의** (`coordinator.py`): 반론이 나오면 에이전트가 사용자에게 설명하고, **사용자가** 반론 가게의 점수를 높일지 정한다. 에이전트끼리 판정하지 않는다.
- **업종:** DB 업종을 6가지로 묶음 (`real_stores.py`의 `GROUPS`). 버거·토스트는 기타.

## 6. 가게 데이터 바꾸기

1. 새 DB를 `data/혼밥_동성로.db`로 덮어쓴다 (원본은 따로 보관).
2. `python agents/real_stores.py` → `public/index.html`의 가게 목록을 다시 만든다.
3. `agents/test_real_stores.py`의 가게 수·확인 수를 새 값으로 고치고 시험한다.
4. 새 업종이 있으면 `real_stores.py`의 `KINDS`, `GROUPS`에 추가한다.

## 7. 남은 일

- **1인석 데이터:** DB에 '있음'이 0곳이라 혼밥 점수의 2점은 일기로만 붙는다.
- **취향 '확실도 낮음':** 혼밥일기가 없으면 기본값으로 점수를 낸다.
- **가격을 모르는 6곳:** 크기별·낱개 가격만 있거나 가격이 없다.
- **검증 에이전트:** 설계 자료에는 있지만 만들지 않았다.
- **이웃 공유 일기:** `window.claude`가 있는 환경에서만 동작해 배포 사이트에서는 꺼진다. 일기·찜·MBTI는 그 사람의 브라우저에만 저장된다.
- **시험 화면** `agents/app.py`는 PC용 옛 화면이라 배포에는 쓰지 않는다.

---

**이 사본은 공개용입니다.** `data/`의 DB와 `public/index.html`에서 지도 링크·가게 번호·화면 원문을 뺐습니다. 원본 DB는 팀 안에서 받으세요.
