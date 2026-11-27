# v2 초안 — 가격·메뉴를 코드로 바꾼 예측본

- 작성일: 2026-11-27
- 상태: **팀 결정 전 예측본**이다.
  원본 파일(`1126proto/` 바로 아래)은 고치지 않았다.
  팀이 정하면 이 폴더의 파일로 원본을 바꾼다.
- 왜: 가격과 메뉴는 정량값이라 에이전트(LLM)로 두지 않는다(사용자 방향).
  바뀌는 데이터와 끊기는 흐름 B1~B11은 `../02_가격_메뉴_비에이전트_전환_영향.md`.

## 1. 이 초안이 고른 가안

팀 결정 7절의 선택지 중 아래를 골라 썼다.
다르게 정하면 표의 파일을 고친다.

| 번호 | 정할 것 | 이 초안의 가안 | 반영한 파일 |
|---|---|---|---|
| ① | 업종 → 음식 종류 대응표 (D12) | `업종_음식종류_대응표_초안.md` | `criteria.json` `menu`, `prepare.py` |
| ② | 예산 상한을 어디서 거르나 (B4) | **후보 고르기 전 필터** (앱과 같음), 가격 모름은 남김 | `scoring.py` `budget_prefilter`, `prompts/coordinator.md` 4단계, `prompts/verifier.md` R4 |
| ③ | 상의에서 가격 (B3) | **조율자가 사실로만 보여 줌** (`price_facts`), 가격 반론 없음 | `scoring.py`, `prompts/coordinator.md` 10단계, `criteria.json` `debate` |
| ④ | 값을 모르는 가게 (B2 · B5) | 지금 규칙(D1) 그대로 unknown → 0점. 음식 종류는 대응표로 모두 채워져 해당 없음 | – |
| ⑤ | 앱의 쫀득이·폭신이 (B10) | 이 폴더에서는 다루지 않음 (앱 담당과 상의) | – |

## 2. 원본 ↔ 초안

| 원본 (`1126proto/`) | 이 폴더 | 바뀐 내용 |
|---|---|---|
| `00_전체구조.md` | `00_전체구조.md` | 에이전트 8 → 6, 코드 단계 표, 흐름 [미리]~[8], 가중치 표 메뉴 행 삭제, 공통 계약 예시를 날씨로 |
| `criteria.json` | `criteria.json` | 가중치 `menu` 삭제, `budget` 거르기·확실도 규칙, `menu` 낱말 규칙·업종 대응표·날씨 규칙, `debate.price_in_debate`, `replan.targets_allowed` |
| `scoring.py` | `scoring.py` | `budget_prefilter`, `price_facts` 추가. 기존 함수는 그대로 |
| `test_scoring.py` | `test_v2.py` | 기존 15개 + v2 5개 (거르기, 가격 사실, 음식 종류·날씨 규칙, 가격 중앙값) |
| (없음) | `prepare.py` | 메뉴 에이전트 대신 가게마다 가격·종류·날씨용 종류·확실도를 미리 계산 |
| `prompts/budget.md` | `도구설명/예산_점수.md` | 에이전트 프롬프트 → 코드 단계 설명서 |
| `prompts/menu.md` | `도구설명/데이터_준비.md` | 에이전트 프롬프트 → 코드 단계 설명서 |
| `prompts/coordinator.md` | `prompts/coordinator.md` | 에이전트 목록, 4·6·7·10·12단계 |
| `prompts/verifier.md` | `prompts/verifier.md` | R2·R4 문구, `replan_targets` |
| `prompts/weather.md` · `preference.md` | 같은 이름 | 입력 출처 "메뉴 에이전트" → "prepare.py 미리 계산" |
| `prompts/distance.md` · `solo.md` | (그대로) | 바꿀 것 없음 |
| (D12 없음) | `업종_음식종류_대응표_초안.md` | 26종 대응표, 낱말 규칙, 결과와 정확도 |

- 이 폴더에 없는 원본 파일은 바꾸지 않아도 되는 파일이다.
- `spec/userflow.md`, `피칭_슬라이드/08_*`의 "밥톨이 상의" 문구와 앱의 캐릭터 구성은 앱이 바뀐 뒤에 맞춘다.

## 3. 돌려 본 결과 (2026-11-27)

| 확인 | 결과 |
|---|---|
| `python3 -I v2_가격메뉴_코드화_초안/prepare.py` | 391곳 모두 음식 종류·날씨용 종류 정해짐, 1인 가격 388곳 |
| `python3 -B v2_가격메뉴_코드화_초안/test_v2.py` | 20개 모두 통과 |
| 음식 종류 정확도 | 무작위 25곳 중 21곳 맞음(84%), 틀린 4곳은 낱말을 더해 고침 |

- `prepare.py`의 출력 `data/stores_prepared_v2.json`은 팀 안에서만 쓰는 파일이다.
  공개 저장소에 올리지 않는다.
