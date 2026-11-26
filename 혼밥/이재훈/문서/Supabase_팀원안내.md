# 혼밥 팀 Supabase 안내 (2026-11-26)

팀 공용 클라우드 DB입니다. 에이전트마다 **구역(schema)** 을 하나씩 쓰고, 가게는 모두 **`restaurant_id`(식당ID)** 로 잇습니다.
지금은 **틀만** 있고 혼밥 데이터는 수집이 끝나면(11-26 저녁) 올립니다.

| | |
|---|---|
| 프로젝트 | `honbap-dongseongro` (서울, 무료) |
| 주인 | 이재훈 계정. 팀원은 **멤버로 초대** 받아 들어옴 |

## 1. 구역

| 구역 | 에이전트 | 지금 들어 있는 것 |
|---|---|---|
| `honbap` | 혼밥(갱신) — 이재훈 | 가게 기준 목록·근거·주요메뉴·확인 대기, 보기 `restaurant_summary`, 점수 함수 `honbap_score` |
| `menu` | 메뉴(갱신) 보조 | 비어 있음 — 담당이 표를 만듦 |
| `price` | 가격 | 비어 있음 |
| `taste` | 취향(일기·후기) | `solo_seats`(1인석) — **혼밥 점수 +2에 바로 쓰임**. 일기 등 다른 표는 담당이 만듦 |
| `distance` | 거리 | 비어 있음 |
| `weather` | 날씨 | 비어 있음 |

## 2. 약속 (멤버는 기술적으로 모든 구역을 고칠 수 있어서 약속으로 지킴)

1. **자기 구역에만** 표를 만들고 고친다. `honbap` 구역은 손대지 않는다(매주 자동 갱신이 다시 만듦).
2. 가게를 가리킬 때는 **`restaurant_id`** 를 쓰고, 가능하면 `references honbap.restaurants (restaurant_id) on delete cascade`로 잇는다. 폐업한 가게가 빠지면 내 줄도 같이 빠진다.
3. 이름은 **영어 소문자_밑줄**(예: `avg_price`), 뜻은 한글 설명으로 붙인다: `comment on column price.xxx.avg_price is '평균 가격(원)';`
4. 앱이 읽을 표는 아래 5번처럼 **읽기 규칙**을 붙인다.
5. 리뷰 작성자 이름·닉네임, 개인정보는 넣지 않는다.

## 3. 이름 대응표 (파일 DB 한글 이름 → Supabase)

| 파일 DB (`혼밥_동성로.db`) | Supabase |
|---|---|
| 식당 | `honbap.restaurants` |
| 식당ID, 상호, 업종, 구군, 행정동, 도로명주소 | `restaurant_id`, `name`, `category`, `gu`, `dong`, `road_address` |
| 위도, 경도, 지도링크, 지도가게번호 | `lat`, `lng`, `map_url`, `map_place_id` |
| 처음넣은날, 마지막확인일, 겹친ID | `first_added`, `last_checked`, `merged_ids` |
| 근거 | `honbap.evidence` |
| 항목, 메뉴명, 인분, 가격, 수, 요지, 판단, 출처, 주소링크, 본날, 상태, 확인자 | `item`, `menu_name`, `servings`, `price`, `count_value`, `summary`, `judgment`, `source`, `source_url`, `seen_on`, `status`, `checker` |
| 주요메뉴 | `honbap.main_menus` (`menu_name`, `price`, `price_unit`, `maybe_side`, `seen_on`) |
| 검색기록 | `honbap.search_log` |
| 설정 | `honbap.settings` |
| 혼밥가게 (보기) | `honbap.restaurant_summary` (`solo_review_count`=혼밥후기수, `one_serving_menus`=일인메뉴, `solo_seat`=일인석, `solo_seat_sources`=일인석출처) |
| (1인석 CSV) | `taste.solo_seats` (`restaurant_id`, `has_solo_seat`, `seen_on`, `note`, `checker`) |

값(예: 항목 '일인메뉴', 상태 '검토전', 가격단위 '단품')은 한글 그대로입니다.

## 4. 앱에서 읽기

먼저 **Supabase 화면 → Project Settings → Data API → Exposed schemas** 에 쓰는 구역(`honbap`, `taste` 등)을 더해야 앱이 읽을 수 있습니다(주인 계정에서 한 번).

```js
// 가게 목록 (보기)
const { data } = await supabase.schema('honbap').from('restaurant_summary').select('*')

// 혼밥 점수: 위치 기반 20곳의 식당ID를 넘기면 점수 높은 순으로 돌려줌
const { data: scores } = await supabase.schema('honbap').rpc('honbap_score', { p_ids: ids20 })
// 한 줄: restaurant_id, name, solo_review_count, rank_no, shop_count, review_points(1~8), solo_seat(있음/없음/모름), seat_points(0/2), score(최대 10)
```

- **혼밥 점수** = 넘긴 가게들 안에서 혼밥하기 좋아요 수로 줄 세워 8칸(1등 칸 8점 ~ 꼴찌 칸 1점, 같은 수는 같은 점수) + 1인석·바 좌석이 있으면 2점.
- 1인석은 `taste.solo_seats`(혼밥일기)와 네이버 정보 탭(`honbap.evidence`의 '1인석') 중 **가장 최근 것이 하나라도 있음이면** 있음.
- 앱(anon 키)은 **읽기만** 됩니다. 쓰기는 대시보드 멤버와 갱신 작업(service_role)만.

## 5. 내 구역에 표 만들기 (예: 가격)

Supabase 화면 → **SQL Editor** 에서:

```sql
create table price.restaurant_avg (
  restaurant_id text primary key references honbap.restaurants (restaurant_id) on delete cascade,
  avg_price     int,
  menu_count    int,
  computed_on   date not null default current_date
);
comment on table price.restaurant_avg is '가게별 평균 가격';
alter table price.restaurant_avg enable row level security;
create policy restaurant_avg_read on price.restaurant_avg for select to anon, authenticated using (true);
```

- 데이터는 **Table Editor → Insert → Import data from CSV** 로 올리거나, 각자 Claude에게 위 약속을 알려 주고 시키면 됩니다.
- 구역에 새로 만든 표는 앱(anon)이 읽기 권한을 자동으로 받습니다(쓰기는 안 됨). 읽기 규칙(위 `create policy`)까지 붙여야 실제로 보입니다.

## 6. 1인석 넣기 (취향 담당)

```sql
insert into taste.solo_seats (restaurant_id, has_solo_seat, seen_on, note)
values ('MA010120220800150732', true, '2026-11-30', '창가 1인석 4자리');
```

같은 가게를 여러 번 넣어도 됩니다. 가장 최근 `seen_on`이 쓰입니다.
