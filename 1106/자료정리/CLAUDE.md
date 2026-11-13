# 대구 여행객 한 끼 추천 — 데이터 자동 수집 프로젝트 (인수인계 문서)

> 작성: 2026-11-05. 이 파일은 바탕화면 `api` 폴더(`C:\Users\Green\Desktop\api`)에 두고 Claude Code가 먼저 읽도록 한다.

## 1. 프로젝트 목표

- 팀 과제: 대구 로컬 문제를 데이터 서비스로 **자동화(AX)** 하는 프로젝트 (국비 과정 데이터·서비스 트랙).
- 서비스: 여행객이 **상황(인원, 시간, 예산 등)을 입력하면 조건에 맞는 음식점을 찾아 주는 지도**. 첫 후보에 못 가면 대안도 제시.
- 대상: 맛집만이 아니라 **구역 안의 전체 식사 음식점**. 한 구역을 먼저 완성하고, 같은 스크립트로 구역을 추가한다.
- **이 프로젝트의 핵심 자동화 대상 = "빈 정보 채우기"**: 영업시간·휴무일·브레이크타임·마지막 주문·1인 주문·최소 주문 정보를 사람이 아니라 코드/AI가 채운다.
- 대구 10미는 기준이 아님 (예전 문서에 남아 있어도 무시).

## 2. 확정된 결정 사항 (사용자 답변)

| 항목 | 결정 |
|---|---|
| 첫 구역 | 중구 **대봉1동** (김광석길 일대, 식사 음식점 174곳) |
| 음식점 범위 | **식사 음식점만** (카페·주점·빵집·떡·아이스크림·구내식당 제외) |
| 네이버·카카오 지도 자동 수집(크롤링) | **허용** (사용자가 위험 인지) |
| 유료 API (구글 Places 등 결제 수단 필요) | **불가** |
| 대기 정보 | **첫 버전에서 제외** (단, 카카오맵 시간대별 방문자 수는 저장만 해 둠) |
| 지도 출처 우선순위 | **카카오 먼저**, 비는 식당만 나중에 네이버 보충 검토 |
| 작업 방식 | 스크립트는 Claude가 만들고 **사용자 컴퓨터에서 실행**. 결과물(스크립트·CSV)이 이 폴더에 남아야 함 |

### 진행 순서
1. 수집 ✅ (상가정보 대구 전체, 맛집 API 대구 전체)
2. 한 구역 기본표 ✅ 스크립트 완성 (`step2_build_base.py`) — **사용자 PC에서 아직 실행 확인 안 됨** (파일을 폴더에 안 넣어서 오류 났었음)
3. 빈 정보 자동 채우기 ← **다음 작업**
   - 3-1 카카오 로컬 API(공식)로 각 식당의 카카오 장소 ID 찾기
   - 3-2 카카오맵 장소 상세(JSON)에서 영업시간·메뉴·리뷰·시설 수집
   - 3-3 메뉴/리뷰 글에서 1인·최소 주문 조건 추출 (규칙 우선, 안 되는 것만 AI)
   - 3-4 행안부 일반음식점 API / 식약처 폐업정보로 폐업 식당 거르기
4. 상황 입력 → 조건에 맞는 식당 찾기 스크립트
5. 구역 추가 (스크립트의 구역 이름만 바꿔 재실행)

## 3. 이 폴더의 파일

| 파일 | 내용 |
|---|---|
| `sangga_junggu.py` | 상가정보 API, 중구 음식점 → `sangga_daegu_junggu_food.csv` (3,827곳) |
| `sangga_daegu_all.py` | 상가정보 API, 대구 전체 음식점 → `sangga_daegu_all_food.csv` (**36,775곳**) |
| `matjib_all_daegu.py` | 대구 맛집 API, 8개 구·군 → `matjib_daegu_all.csv` (**905곳**, 군위군 0) |
| `step2_build_base.py` | 2단계: 구역 기본표 → `base_중구_대봉1동.csv` |
| `대구_맛집API_수집현황.xlsx` | 지금까지 분석 요약 (참고용. 일부 시트는 10미·맛집 중심이라 현재 방향과 안 맞음) |
| `matjib_905_matched.csv` | 맛집 905곳 ↔ 상가정보 연결 결과 (참고용) |

## 4. 데이터 출처와 사용법

### 공공데이터포털 인증키
- 하나의 키로 아래 3개 API 사용 (모두 승인됨, 활용기간 ~2028-11-03).
- **키는 코드에 쓰지 않고 환경변수로 넣는다**: `set DATA_GO_KR_KEY=키값` (명령 프롬프트). 팀 GitHub에 키를 올리지 않도록 주의.

### ① 소상공인 상가(상권)정보 — 기본 목록
- `https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong`
- 파라미터: `serviceKey, divId=ctprvnCd|signguCd|adongCd, key=27(대구)|27110(중구), indsLclsCd=I2(음식), numOfRows=1000, pageNo, type=json`
- 주요 필드: `bizesId, bizesNm, brchNm, indsMclsNm, indsSclsNm, signguNm, adongNm, ldongNm, lnoAdr, rdnmAdr, lon, lat`
- 영업시간·메뉴 없음. 좌표·업종은 있음.

### ② 대구 맛집 API (대구 음식관광) — 일부 식당 상세
- `https://www.daegufood.go.kr/kor/api/tasty.html?mode=json&addr=중구` (인증키 없음)
- **브라우저 User-Agent 헤더 없이 요청하면 JSON이 아닌 응답이 옴** → 헤더 필수 (`matjib_all_daegu.py` 참고).
- 필드: `OPENDATA_ID, GNG_CS(주소), FD_CS, BZ_NM, TLNO, MBZ_HR(영업시간 글), SEAT_CNT, PKPL, BKN_YN, MNU(메뉴·가격, <br /> 포함), SMPL_DESC, SBW, BUS`
- 좌표 없음. 휴무일·마지막 주문·1인 주문은 거의 없음 (905곳 중 브레이크타임 62곳, 휴무 1곳, 마지막 주문 1곳).
- 대봉1동 식사 음식점 174곳 중 맛집 API와 연결되는 곳은 **17곳뿐** → 157곳은 3단계에서 채워야 함.

### ③ 행안부 일반음식점 / ④ 식약처 폐업정보 — 3-4단계용
- `https://apis.data.go.kr/1741000/general_restaurants`
- `https://apis.data.go.kr/1471000/FoodBusnssClsbizInfo01`
- **요청 형식 미확인.** 짐작으로 코드를 짜지 말고, 사용자에게 참고문서(행안부: `참고문서 안내(URL).xlsx`)와 요청변수 표를 받아서 만든다.

### ⑤ 카카오 로컬 API (공식) — 3-1단계
- 사용자가 developers.kakao.com에서 **REST API 키 발급 예정** (아직 안 함). 앱 설정에 "카카오맵" 사용 설정이 있으면 켜야 함.
- `GET https://dapi.kakao.com/v2/local/search/keyword.json`
  - 헤더 `Authorization: KakaoAK {REST_API_KEY}` (환경변수 `KAKAO_REST_KEY`로 받기)
  - 파라미터 예: `query=상호, x=경도, y=위도, radius=100, category_group_code=FD6(음식점), sort=distance`
  - 응답 `documents[]`: `id, place_name, category_name, address_name, road_address_name, phone, x, y, place_url, distance`
- 연결 방법 제안: 상가정보 좌표 기준 반경 100m 안에서 상호 유사도 + 거리로 1곳 선택, 애매하면 "확인 필요"로 표시.

### ⑥ 카카오맵 장소 상세 (비공식, 크롤링) — 3-2단계
- 2026-11-05 내장 브라우저로 확인: `GET https://place.map.kakao.com/places/panel3/{장소ID}` → JSON, **로그인 없이 200 응답**.
  - 브라우저 안 fetch에서는 헤더 없이도 200. **파이썬 requests에서는 아직 시험 안 함** → User-Agent, Referer(`https://place.map.kakao.com/{id}`), 필요하면 `pf: PC` 헤더 추가해서 시험.
- 확인된 최상위 키: `summary, open_hours, menu, kakaomap_review, blog_review, visitor, place_add_info, reservation, photos, my_store_notice, find_way ...`
  - `summary`: 이름, 카테고리(`category.name1~4`), 좌표, 주소(jibun/road), 전화, `status`
  - `open_hours.week_from_today.week_periods[].days[]`: `day_of_the_week_desc`("목(11/5)"), `on_days.start_end_time_desc`("16:00 ~ 01:00"). `headline`(영업 전/중 표시)
    - **브레이크타임·휴무일이 있는 식당의 형식은 아직 못 봄** → 원본 JSON(open_hours 통째)도 같이 저장할 것
  - `menu.menus.items[]`: `name, price, desc, is_recommend`
  - `kakaomap_review`: `score_set`(review_count, average_score), `reviews[]`(star_rating, contents, registered_at) — 첫 페이지 일부만 옴
  - `visitor`: 요일별·시간대별 방문자 수 배열 (`weekly_uv_average`, `sunday_uv` … `saturday_uv`, -1은 영업 외 시간) → 붐빔 정도 단서, 지금은 저장만
  - `place_add_info.facilities`: 주차, 반려동물, 장애인 시설 등
- 예시 장소: 육즙(대봉동) ID `2140384347`
- **계정 보호 원칙 (사용자가 카톡 계정 걱정함)**: 크롤링 스크립트에는 카카오 API 키·로그인 정보·쿠키를 넣지 않는다. 3-1(공식 API)과 3-2(크롤링)는 **별도 스크립트**. 요청 간격 1~2초, 한 번에 한 구역만.
- 사용자에게 카카오 디벨로퍼스를 지금 계정으로 할지, 별도 카카오 계정으로 할지 아직 답을 못 들음.

### 네이버지도
- 데이터는 가장 많을 것으로 보이나: 공식 지역 검색 API는 장소 ID를 안 줘서 연결이 어렵고, 차단이 잦은 것으로 알려짐.
- Claude 내장 브라우저에서는 네이버지도/플레이스가 안전 제한으로 열리지 않음 (구조 미확인).
- 카카오로 채운 뒤 빈 식당이 많으면 그때 검토.

## 5. 지금까지 숫자 (팀 보고용)

- 대구 식사 음식점(상가정보, 카페·주점 제외) **24,821곳** / 그중 맛집 API 상세 정보 905곳(약 4%)
- 맛집 905곳 중 상가정보와 자동 연결(좌표 확보) **812곳(89.7%)**
- 대봉1동 식사 음식점 174곳 중 맛집 API 정보 있는 곳 17곳

## 6. 사용자와 일하는 방식 (중요)

- 사용자: 경영학과 학생, **코딩·명령 프롬프트 초보**. Windows, Python 3.15 설치됨, `requests` 설치됨.
- 명령 프롬프트 사용 시 자주 생긴 문제: 창이 `C:\Users\Green`에서 열려 파일을 못 찾음 → `cd Desktop\api`. 다운로드한 파일을 api 폴더로 안 옮김.
- **애매하거나 모르는 건 먼저 물어보고 진행할 것.** 짐작으로 방향을 정해 막 진행하는 걸 싫어함 (이전에 10미 중심, 맛집 중심으로 잘못 짚어서 지적받음).
- **차근차근 한 단계씩.** 한 번에 하나의 할 일만 제시.
- 개념 설명은 **비유 없이 직접적으로.**
- 무조건 긍정하지 말고 **객관적으로** (한계·위험을 같이 말할 것).
- 확인 안 한 것을 확인한 것처럼 말하지 말 것 (API 필드, 요청 형식 등).

## 7. 바로 다음 할 일

1. `step2_build_base.py` 실행 확인 → "식사 음식점: 174곳 / 맛집 API와 연결: 17곳"이 나와야 정상.
2. 카카오 계정 선택(현재 계정 / 별도 계정) 확인 → REST API 키 발급 안내.
3. 3-1 스크립트: `base_중구_대봉1동.csv`의 각 식당 → 카카오 장소 ID·place_url 연결, 연결 결과·확인 필요 표시.
4. 3-2 스크립트: 장소 ID별 panel3 JSON 수집 → 영업시간(요일별)·메뉴·리뷰 일부·방문자 수·원본 JSON 저장. 먼저 3~5곳으로 시험 후 전체.
