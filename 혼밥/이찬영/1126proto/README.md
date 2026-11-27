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
| `02_가격_메뉴_비에이전트_전환_영향.md` | 가격·메뉴를 에이전트에서 뺄 때 바뀌는 데이터와 끊기는 흐름 (B1~B11), 고칠 파일, 팀 결정 |
| `v2_가격메뉴_코드화_초안/` | 가격·메뉴를 코드로 바꾼 예측본: 바뀔 설계 문서·criteria·scoring·prepare.py·시험, 업종 → 음식 종류 대응표 초안 (팀 결정 전) |
| `spec/spec.md` | 서비스 spec v0 (목표·사용자·기능·제약·완료 기준) |
| `spec/userflow.md`, `spec/ia.md` | 실제 웹페이지로 그린 유저 플로우 v1, 사이트맵·스토리 대응표 |
| `피칭_슬라이드/` | 피칭 PDF 크기(960×540) HTML 슬라이드: 8쪽 유저플로우(실제 1쪽 · 실제·계획·비교 3쪽), 11쪽 시장 규모(2쪽). `피칭_슬라이드/README.md` |
| `market/` | 시장 검증: 경쟁 비교표, 포지셔닝 맵, TAM·SAM·SOM 시트, 검증 메모 (`market/README.md`) |
| `ref/예산에이전트_설계_원본.md` | 원본 설계 문서 복사본 (`1123실습/`) |
| `ref/weather-agent_README_원본.md` | 날씨 에이전트 원본 설명 복사본 |

## 데이터 (`data/`)

모두 `honbap/`에서 복사했거나, 복사한 것으로 만들었다.
원본은 그대로 두었다.
가게 기준은 2026-11-26 혼밥팀 최종본 DB(391곳)다.

| 파일 | 원본 위치 | 쓰는 에이전트 | 비고 |
|---|---|---|---|
| `honbap_db_final/` | `honbap/혼밥팀_최종본_20261126/1_혼밥DB_최종본/` | 전체 (원본) | 최종본 DB `혼밥_동성로.db`(391곳), CSV, `schema.sql`, `혼밥점수.py`, `test_db.py`, `넘겨주기_혼밥DB.md` |
| `stores_동성로391.json` | 최종본 DB에서 만듦 | 전체 | 가게 391곳. `store_id`=식당ID, 좌표, 혼밥후기 수, 1인석, 1인 메뉴, 주요메뉴. 지도 링크는 뺐다 |
| `메뉴.json` | 최종본 DB에서 만듦 | 메뉴, 예산 | `store_id → 1인 메뉴 목록`. 1인 메뉴 근거 + 주요메뉴 중 '단품'·곁들임 아님. `soup`은 null |
| `id_map_app276_to_db.json` | 1차본 앱 데이터 ↔ 최종본 DB | 전체 | 앱 번호(1001~) 276곳 → 식당ID. 이름이 같은 3쌍은 거리로, `삼락원` 1곳은 손으로 이었다 |
| `stores_app_동성로276.json` | `weather-agent/앱데이터.json` | (옛 자료) | 1차 앱 내보내기 276곳. 좌석·좌표·평점 칸이 비어 있다. 최종본 391곳으로 대신한다 |
| `restaurants_대구1174.json` | `chatbot/restaurants.json` | 혼밥편의, 메뉴, 예산 | 대구 1,174곳 1인분 판정과 메뉴 가격 |
| `source_1in/*.csv` | `chatbot/data_src/` | 혼밥편의 | 다이닝코드·대구푸드 1인분·최소 주문 근거 (2026-11-21 확인) |
| `voc_clean.csv` | `voc_clean.csv` | 예산 (VOC 보정, 지금은 꺼 둠) | 331건, 모두 D등급. 공개 결과물에는 원문 대신 요약과 voc_id만 쓴다 |
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

최종본 DB와 그것으로 만든 JSON에는 지도 링크·가게 번호가 들어 있거나 이어진다.
공개 깃허브(4P)에 올리지 않고 팀 안에서만 주고받는다.
그래서 4P 저장소에는 `data/honbap_db_final/`, `data/stores_동성로391.json`, `data/메뉴.json`, `data/voc_clean.csv`를 넣지 않았다.
`메뉴.json`은 파일 안 note에 "공개 저장소에 올리지 않는다"고 적혀 있어 2026-11-26 팀원이 4P에서 뺐다.
공개해도 되는 DB는 `혼밥/이재훈/데이터_공개용/`에 있고, 전체 DB는 혼밥팀 최종본으로 받는다.

`python3 data/build_from_final_db.py`로 최종본 DB에서 JSON 3개를 다시 만든다.

## 근거 규칙

`honbap/CLAUDE.md` 3장을 그대로 따른다.

- 고객 글 근거는 `voc_id`로만 단다.
- `대구거주`가 `모름`인 글은 대구 고객이라고 쓰지 않는다.
- 근거 등급을 바꾸지 않고, D등급으로 빈도·비율을 말하지 않는다.
