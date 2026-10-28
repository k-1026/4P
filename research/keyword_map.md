# 대구 푸드 상권 탐색 서비스: 키워드 맵 (과제 B)

- 작성일: 2026-10-27
- 키워드별 데이터 노트: [data/](data/) (5개를 합친 통합본: [data_sources_all.md](data_sources_all.md))

> **유형 구분 안내**: 받은 요청문이 "3. 일…"에서 끊겨 있어 1, 2번 유형만 원문 그대로다. 3~6번 유형은 프로젝트 목표와 조사 주제를 바탕으로 **팀에서 정한 것으로 가정**했다. 원래 유형명이 다르면 바꿔야 한다.

## 상태 표기

- **데이터 있음**: 공식 데이터셋 페이지를 확인함
- **일부 데이터**: 일부 구·군만 있거나 핵심 필드 일부가 없음
- **데이터 미확인**: 공공데이터를 찾지 못했거나 보도로만 확인함

## 1. 지역 특산물 및 식품

| 키워드 | 설명 | 관련 노트 | 상태 |
|---|---|---|---|
| 대구 사과 | 대구시 주요 작목. 재배면적·생산량 통계와 판매처 데이터가 있음 | [local_food_access.md](data/local_food_access.md) | 데이터 있음 |
| 대구 연근 | 대구시 주요 작목 (농축산물 재배현황 컬럼에 포함) | [local_food_access.md](data/local_food_access.md) | 데이터 있음 |
| 대구 미나리 | 대구시 주요 작목 (농축산물 재배현황 컬럼에 포함) | [local_food_access.md](data/local_food_access.md) | 데이터 있음 |
| 대구 로컬푸드 직매장 | 대구시 로컬푸드직매장 및 직거래장터 현황 | [local_food_access.md](data/local_food_access.md) | 일부 데이터 (컬럼 미확인) |
| 명품 D마크 | 대구시 농축특산물 인증 공동상표 | 없음 | 데이터 미확인 |

## 2. 전통시장 및 상점가

| 키워드 | 설명 | 관련 노트 | 상태 |
|---|---|---|---|
| 대구 전통시장 | 시장 위치, 점포 수, 주차장·화장실, 사용 가능 상품권 | [traditional_markets.md](data/traditional_markets.md) | 데이터 있음 |
| 서문시장 | 대구 대표 시장. 중구 단위 데이터는 찾지 못함 | [notes/seomun_market.md](notes/seomun_market.md) | 일부 데이터 |
| 구·군별 전통시장 | 서구·동구·북구·달서구 데이터 있음 | [traditional_markets.md](data/traditional_markets.md) | 일부 데이터 |
| 온누리상품권 가맹점 | 시장별 가맹 점포와 취급품목 | [traditional_markets.md](data/traditional_markets.md) | 데이터 있음 |

## 3. 일반 음식점 및 먹거리 골목 (가정한 유형)

| 키워드 | 설명 | 관련 노트 | 상태 |
|---|---|---|---|
| 대구 음식점 업종 분포 | 구·동별 음식점 수와 업종 구성 | [food_businesses.md](data/food_businesses.md) | 일부 데이터 |
| 안지랑곱창골목 | 남구 먹거리 골목, 업소 52곳 | [food_districts.md](data/food_districts.md) | 데이터 있음 |
| 앞산카페거리 | 남구 먹거리 골목, 업소 32곳 | [food_districts.md](data/food_districts.md) | 데이터 있음 |
| 앞산맛둘레길 | 남구 먹거리 골목, 업소 44곳 | [food_districts.md](data/food_districts.md) | 데이터 있음 |
| 들안길 먹거리타운 | 수성구 먹거리 골목 | 없음 | 데이터 미확인 |

## 4. 방문 편의 (주차·대중교통) (가정한 유형)

| 키워드 | 설명 | 관련 노트 | 상태 |
|---|---|---|---|
| 대구 공영주차장 | 위치, 운영시간, 요금 | [notes/access_convenience.md](notes/access_convenience.md) | 데이터 있음 |
| 대구 시내버스 정류소 | 정류소 위치, 경유 노선 수 | [notes/access_convenience.md](notes/access_convenience.md) | 일부 데이터 |
| 대구 도시철도역 | 역 위치, 환승 여부 | [notes/access_convenience.md](notes/access_convenience.md) | 일부 데이터 |

## 5. 음식 가격 및 결제 (가정한 유형)

| 키워드 | 설명 | 관련 노트 | 상태 |
|---|---|---|---|
| 대구 외식비 | 냉면·비빔밥 등 8개 품목의 시도별 평균 가격 | [food_prices.md](data/food_prices.md) | 데이터 있음 |
| 농산물 소매가격 | aT·KAMIS 품목별 도·소매 가격 | [food_prices.md](data/food_prices.md) | 일부 데이터 (대구 지역코드 미확인) |
| 착한가격업소 | 업소별 대표메뉴와 가격 | [food_prices.md](data/food_prices.md) | 일부 데이터 (북구만) |
| 대구로페이 가맹점 | 지역화폐 사용처 | 없음 | 데이터 미확인 |

## 6. 리뷰·메뉴·관광 콘텐츠 (가정한 유형)

| 키워드 | 설명 | 관련 노트 | 상태 |
|---|---|---|---|
| 대구 음식 관광정보 | 한국관광공사 국문 관광정보 서비스(TourAPI)의 음식점 정보 | 없음 | 일부 데이터 (음식점 필드 미확인) |
| 대표메뉴 | 업소별 대표메뉴 (착한가격업소에만 확인) | [food_prices.md](data/food_prices.md) | 일부 데이터 |
| 음식점 리뷰·평점 | 이용자 평가. 공공데이터 없음 | 없음 | 데이터 미확인 (추가 기능으로 보류) |
| 대구 10미 | 대구시가 홍보하는 대표 음식 | 없음 | 데이터 미확인 (공식 목록 출처 확인 필요) |

## 트랙 과제: 데이터 소스 후보 노트 5개 (제출본)

| 키워드 | 노트 | 고른 이유 |
|---|---|---|
| 대구 음식점 업종 분포 | [data/food_businesses.md](data/food_businesses.md) | 음식점·카페·식품 점포의 위치와 업종. 지도와 점포 수 비교의 기반 |
| 대구 전통시장 | [data/traditional_markets.md](data/traditional_markets.md) | 서비스 핵심 탐색 대상 |
| 안지랑곱창골목 (먹거리 상권) | [data/food_districts.md](data/food_districts.md) | 상권 단위 비교와 먹거리 골목 데이터 |
| 대구 외식비 | [data/food_prices.md](data/food_prices.md) | 농수산물 가격과 외식비의 확보 가능성 확인 |
| 대구 사과 (지역 먹거리 판매처) | [data/local_food_access.md](data/local_food_access.md) | 특산물·로컬푸드를 어디서 살 수 있는지 |
