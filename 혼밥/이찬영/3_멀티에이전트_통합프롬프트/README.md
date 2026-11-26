# 1126proto · 혼밥 식당 추천 멀티 에이전트 프롬프트

- 만든 날: 2026-11-26
- 날씨·거리·예산·취향·혼밥편의 에이전트와 조율자·메뉴·검증 에이전트를 하나의 계약으로 합쳤다.
- 모든 판정·규칙 점수는 10점 만점이다.
  개별 점수는 0~10 정수, 총점은 0.0~10.0이다.

## 읽는 순서

1. `00_전체구조.md`: 구조, 10점 공통 규칙, 공통 입출력, 가중치, 흐름
2. `criteria.json`: 모든 숫자가 있는 판정 기준표 (기준을 바꿀 때는 이 파일만 고친다)
3. `prompts/*.md`: 에이전트별 시스템 프롬프트
4. `01_필요데이터_수정사항.md`: 없는 데이터, 팀이 정할 것, 기존 코드에 옮길 것

## 파일

| 파일 | 내용 |
|---|---|
| `00_전체구조.md` | 전체 구조와 공통 계약 |
| `01_필요데이터_수정사항.md` | 필요한 데이터와 수정할 내용 |
| `criteria.json` | 판정 기준표 (10점 만점) |
| `scoring.py` | 점수 도구 참고 구현. 에이전트는 점수를 직접 계산하지 않고 이 함수를 부른다 |
| `test_scoring.py` | `python3 test_scoring.py`로 설계 문서·`role_check.json` 예시를 시험한다 |
| `prompts/coordinator.md` | 조율자 |
| `prompts/weather.md` | 날씨 |
| `prompts/distance.md` | 거리 |
| `prompts/budget.md` | 예산 |
| `prompts/preference.md` | 취향기록 |
| `prompts/solo.md` | 혼밥편의 |
| `prompts/menu.md` | 메뉴 (정보 공유, 점수 없음) |
| `prompts/verifier.md` | 검증 |
| `ref/예산에이전트_설계_원본.md` | 원본 설계 문서 복사본 (`1123실습/`) |
| `ref/weather-agent_README_원본.md` | 날씨 에이전트 원본 설명 복사본 |

## 데이터 (`data/`)

모두 `honbap/`에서 복사했다.
원본은 그대로 두었다.

| 파일 | 원본 위치 | 쓰는 에이전트 | 비고 |
|---|---|---|---|
| `stores_app_동성로276.json` | `weather-agent/앱데이터.json` | 전체 | 앱이 내보낸 동성로 가게 276곳. 좌석·좌표·평점 칸은 비어 있다 |
| `restaurants_대구1174.json` | `chatbot/restaurants.json` | 혼밥편의, 메뉴, 예산 | 대구 1,174곳 1인분 판정과 메뉴 가격 |
| `source_1in/*.csv` | `chatbot/data_src/` | 혼밥편의 | 다이닝코드·대구푸드 1인분·최소 주문 근거 (2026-11-21 확인) |
| `voc_clean.csv` | `voc_clean.csv` | 예산 (VOC 보정, 지금은 꺼 둠) | 331건, 모두 D등급. **공개 저장소라 이 폴더에는 넣지 않았다** (고객 글 원문) |
| `혼밥일기.json` | `weather-agent/혼밥일기.json` | 취향기록 | 샘플 일기 9건 |
| `취향요약.json` | `weather-agent/취향요약.json` | 취향기록 | 앱 일기로 만든 요약 예시 (별점 1~5 기준 옛 형식) |
| `가게정보.csv` | `weather-agent/가게정보.csv` | 취향기록 | 샘플 가게 11곳의 음식 종류 |
| `sample_stores.json` | `weather-agent/sample_stores.py` | 전체 (시험용) | 예시 가게 6곳의 메뉴·1인분·좌석 |
| `weather_result.json` | `weather-agent/weather_result.json` | 날씨 | 날씨 결과 예시 (2026-11-26 14:37) |
| `role_check.json` | `weather-agent/role_check.json` | 시험 | 날씨·거리·취향 역할 점검 결과 |

복사하지 않은 것은 다음과 같다.

- `weather-agent/api_key.txt`: 비밀값이다.
- `history.csv`, `history_old.csv`: 비어 있다.
- `chatbot/data_src/대구푸드_맛집DB_905곳.json`: `restaurants_대구1174.json`이 이 파일로 만든 결과라 뺐다.

## 근거 규칙

`honbap/CLAUDE.md` 3장을 그대로 따른다.

- 고객 글 근거는 `voc_id`로만 단다.
- `대구거주`가 `모름`인 글은 대구 고객이라고 쓰지 않는다.
- 근거 등급을 바꾸지 않고, D등급으로 빈도·비율을 말하지 않는다.
