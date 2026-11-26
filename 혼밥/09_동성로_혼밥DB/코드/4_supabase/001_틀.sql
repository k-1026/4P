-- 혼밥 팀 공용 Supabase 틀 (2026-11-26). 프로젝트 honbap-dongseongro.
-- 에이전트마다 구역(schema)을 나누고, 모든 구역은 honbap.restaurants.restaurant_id(식당ID)로 잇는다.
-- 이름은 영어 소문자, 설명은 한글(COMMENT). 데이터는 수집이 끝난 뒤 따로 올린다.

-- 1. 구역 ---------------------------------------------------------------
create schema if not exists honbap;
create schema if not exists menu;
create schema if not exists price;
create schema if not exists taste;
create schema if not exists distance;
create schema if not exists weather;

comment on schema honbap   is '혼밥(갱신) 에이전트: 혼밥 가능 가게 기준 목록·근거·주요메뉴·혼밥 점수. 다른 구역은 restaurants.restaurant_id로 잇는다';
comment on schema menu     is '메뉴(갱신) 보조 에이전트: 가게 대표 메뉴·가격 갱신';
comment on schema price    is '가격 에이전트: 가게 메뉴 가격 평균 등';
comment on schema taste    is '취향 에이전트: 일기·후기로 개인화. solo_seats(1인석)는 혼밥 점수에 쓰인다';
comment on schema distance is '거리 에이전트';
comment on schema weather  is '날씨 에이전트';

-- 2. honbap 구역 표 ------------------------------------------------------
create table honbap.settings (
  name  text primary key,
  value text not null
);
comment on table honbap.settings is '설정: 만든 날, 넣는 조건, 점수 기준 등';

create table honbap.restaurants (
  restaurant_id text primary key,
  name          text not null,
  category      text,
  gu            text not null,
  dong          text,
  road_address  text not null,
  lat           double precision not null check (lat between 33 and 39),
  lng           double precision not null check (lng between 124 and 132),
  map_url       text,
  map_place_id  text,
  first_added   date not null,
  last_checked  date not null,
  merged_ids    text
);
comment on table  honbap.restaurants is '식당: 혼밥 가능 가게 기준 목록(1인분 + 혼밥하기 좋아요 5명 이상). 모든 구역이 이 restaurant_id로 잇는다';
comment on column honbap.restaurants.restaurant_id is '식당ID (상가정보 번호, 매주 갱신으로 들어온 새 가게는 L로 시작)';
comment on column honbap.restaurants.name          is '상호';
comment on column honbap.restaurants.category      is '업종';
comment on column honbap.restaurants.gu            is '구군';
comment on column honbap.restaurants.dong          is '행정동';
comment on column honbap.restaurants.road_address  is '도로명주소';
comment on column honbap.restaurants.lat           is '위도';
comment on column honbap.restaurants.lng           is '경도';
comment on column honbap.restaurants.map_url       is '지도링크';
comment on column honbap.restaurants.map_place_id  is '지도가게번호 (N=네이버, K=카카오)';
comment on column honbap.restaurants.first_added   is '처음넣은날';
comment on column honbap.restaurants.last_checked  is '마지막확인일';
comment on column honbap.restaurants.merged_ids    is '겹친ID (같은 지도 가게라 합친 다른 목록 번호, "; "로 나눔)';

create table honbap.evidence (
  evidence_id   bigint generated always as identity primary key,
  restaurant_id text not null references honbap.restaurants (restaurant_id) on delete cascade,
  item          text not null check (item in ('일인메뉴', '최소주문', '크기세트만', '혼밥후기수', '1인석')),
  menu_name     text,
  servings      int check (servings is null or servings >= 1),
  price         int check (price is null or price > 0),
  count_value   int check (count_value is null or count_value >= 0),
  summary       text not null,
  judgment      text,
  source        text not null check (source in ('메뉴글', '메뉴사진', '카카오메뉴', '리뷰키워드', '혼밥일기', '정보탭')),
  source_url    text,
  seen_on       date not null,
  status        text not null check (status in ('사람확인', '검토전')),
  checker       text,
  check (status <> '사람확인' or checker is not null),
  check (item <> '혼밥후기수' or count_value is not null),
  check (item <> '일인메뉴' or servings = 1),
  check (item <> '최소주문' or servings >= 2),
  check (item <> '1인석' or (count_value in (0, 1) and source in ('혼밥일기', '정보탭')))
);
create index evidence_restaurant_item_idx on honbap.evidence (restaurant_id, item, seen_on desc);
comment on table  honbap.evidence is '근거: 한 가게에서 본 사실 하나가 한 줄. 숫자가 바뀌면 덮어쓰지 않고 새 줄. 리뷰 글·작성자는 넣지 않음';
comment on column honbap.evidence.item        is '항목: 일인메뉴 / 최소주문 / 크기세트만 / 혼밥후기수 / 1인석';
comment on column honbap.evidence.menu_name   is '메뉴명';
comment on column honbap.evidence.servings    is '인분';
comment on column honbap.evidence.price       is '가격(원)';
comment on column honbap.evidence.count_value is '수 (혼밥후기수: 혼밥하기 좋아요 수, 1인석: 1=있음 0=없음)';
comment on column honbap.evidence.summary     is '요지 (화면 글 그대로)';
comment on column honbap.evidence.judgment    is '판단 (어떻게 그렇게 봤는지)';
comment on column honbap.evidence.source      is '출처';
comment on column honbap.evidence.source_url  is '주소링크';
comment on column honbap.evidence.seen_on     is '본날';
comment on column honbap.evidence.status      is '상태: 사람확인 / 검토전';
comment on column honbap.evidence.checker     is '확인자';

create table honbap.main_menus (
  main_menu_id  bigint generated always as identity primary key,
  restaurant_id text not null references honbap.restaurants (restaurant_id) on delete cascade,
  menu_name     text not null,
  price         int check (price is null or price > 0),
  price_unit    text check (price_unit in ('단품', '크기·세트', '무게')),
  maybe_side    boolean not null default false,
  seen_on       date not null
);
create index main_menus_restaurant_idx on honbap.main_menus (restaurant_id);
comment on table  honbap.main_menus is '주요메뉴: 가게 중심 요리 최대 3개와 가격. 평균을 낼 때는 price_unit=단품, maybe_side=false만';
comment on column honbap.main_menus.price_unit is '가격단위: 단품 / 크기·세트 / 무게';
comment on column honbap.main_menus.maybe_side is '곁들임일수있음';

create table honbap.search_log (
  log_id        bigint generated always as identity primary key,
  restaurant_id text not null references honbap.restaurants (restaurant_id) on delete cascade,
  searched_on   date not null,
  place         text not null,
  result        text not null check (result in ('있음', '없음', '못 찾음', '막힘')),
  memo          text
);
create index search_log_restaurant_idx on honbap.search_log (restaurant_id);
comment on table honbap.search_log is '검색기록: 언제 어디서 찾아봤는지';

create table honbap.check_queue (
  queue_id     bigint generated always as identity primary key,
  kind         text not null check (kind in ('새가게', '후기다시보기')),
  target_key   text not null,
  name         text,
  road_address text,
  map_url      text,
  due_on       date not null,
  status       text not null default '대기' check (status in ('대기', '처리중', '완료', '멈춤')),
  result       jsonb,
  note         text,
  created_at   timestamptz not null default now(),
  done_at      timestamptz,
  unique (kind, target_key, due_on)
);
create index check_queue_waiting_idx on honbap.check_queue (due_on) where status = '대기';
comment on table honbap.check_queue is '확인 대기: 매주 클라우드 갱신이 쌓고, 이 컴퓨터를 켜면 Aside로 네이버를 보고 결과를 채움(앱은 읽지 않음)';

-- 3. taste 구역: 1인석(혼밥 점수에 쓰임). 일기 등 다른 표는 취향 담당이 추가 --------
create table taste.solo_seats (
  seat_id       bigint generated always as identity primary key,
  restaurant_id text not null references honbap.restaurants (restaurant_id) on delete cascade,
  has_solo_seat boolean not null,
  seen_on       date not null,
  note          text check (note is null or length(note) <= 200),
  checker       text,
  created_at    timestamptz not null default now()
);
create index solo_seats_restaurant_idx on taste.solo_seats (restaurant_id, seen_on desc);
comment on table  taste.solo_seats is '1인석: 일기·후기에서 확인한 1인석·바 좌석 여부. 혼밥 점수 +2에 쓰임. 작성자 이름·닉네임은 넣지 않음';
comment on column taste.solo_seats.has_solo_seat is '1인석·바 좌석 있음(true) / 없음(false)';
comment on column taste.solo_seats.seen_on       is '본날 (일기를 쓴 날 또는 확인한 날)';
comment on column taste.solo_seats.note          is '요지 (짧게, 200자 안쪽)';
comment on column taste.solo_seats.checker       is '사람이 확인했으면 이름';

-- 4. 앱이 읽는 보기: 가게 한 줄 + 최근 혼밥 후기 수 + 1인 메뉴 + 1인석 -----------------
-- 1인석은 출처(정보탭=honbap.evidence, 혼밥일기=taste.solo_seats)마다 가장 최근 것을 보고, 하나라도 있으면 '있음'.
create view honbap.restaurant_summary with (security_invoker = true) as
select r.restaurant_id, r.name, r.category, r.dong, r.road_address, r.lat, r.lng, r.map_url,
  (select e.count_value from honbap.evidence e
    where e.restaurant_id = r.restaurant_id and e.item = '혼밥후기수'
    order by e.seen_on desc, e.evidence_id desc limit 1) as solo_review_count,
  (select string_agg(coalesce(e.menu_name, e.summary) || coalesce(' ' || e.price || '원', ''), '; ' order by e.evidence_id)
     from honbap.evidence e where e.restaurant_id = r.restaurant_id and e.item = '일인메뉴') as one_serving_menus,
  r.last_checked,
  seat.solo_seat,
  seat.solo_seat_sources
from honbap.restaurants r
left join lateral (
  with s as (
    select e.source, e.count_value = 1 as yes, e.seen_on, e.evidence_id as id
      from honbap.evidence e where e.restaurant_id = r.restaurant_id and e.item = '1인석'
    union all
    select '혼밥일기', t.has_solo_seat, t.seen_on, t.seat_id
      from taste.solo_seats t where t.restaurant_id = r.restaurant_id
  ), latest as (
    select distinct on (source) source, yes from s order by source, seen_on desc, id desc
  )
  select case when bool_or(yes) then '있음' when count(*) > 0 then '없음' end as solo_seat,
         string_agg(source, ', ') filter (where yes) as solo_seat_sources
    from latest
) seat on true;
comment on view honbap.restaurant_summary is '혼밥가게: 가게 한 줄 + 최근 혼밥 후기 수 + 1인 메뉴 + 1인석(있음/없음/비어 있으면 모름)';

-- 5. 혼밥 점수(10점): 앱이 넘긴 가게들 안에서 후기 수로 줄 세워 8칸(8~1점) + 1인석 2점 ----------
create function honbap.honbap_score(p_ids text[])
returns table (
  restaurant_id text, name text, solo_review_count int, rank_no int, shop_count int,
  review_points int, solo_seat text, solo_seat_sources text, seat_points int, score int
)
language sql stable security invoker set search_path = ''
as $$
  with s as (
    select v.restaurant_id, v.name, v.solo_review_count, v.solo_seat, v.solo_seat_sources
      from honbap.restaurant_summary v
     where v.restaurant_id = any (p_ids) and v.solo_review_count is not null
  ), r as (
    select s.*, rank() over (order by s.solo_review_count desc) as rk, count(*) over () as n from s
  ), p as (
    select r.*, ceil(8.0 * (r.n - r.rk + 1) / r.n)::int as rp,
           case when r.solo_seat = '있음' then 2 else 0 end as sp
      from r
  )
  select p.restaurant_id, p.name, p.solo_review_count, p.rk::int, p.n::int, p.rp,
         coalesce(p.solo_seat, '모름'), coalesce(p.solo_seat_sources, ''), p.sp, p.rp + p.sp
    from p
   order by p.rp + p.sp desc, p.solo_review_count desc, p.restaurant_id;
$$;
comment on function honbap.honbap_score(text[]) is
  '혼밥 점수(10점): 넘긴 식당ID들 안에서 혼밥하기 좋아요 수로 줄 세워 8칸(1등 칸 8점~꼴찌 칸 1점, 같은 수는 같은 점수) + 1인석·바 좌석 있으면 2점. DB에 없는 ID는 빠짐';

-- 6. 권한: 앱(anon, authenticated)은 읽기만, 쓰기는 갱신 작업(service_role)과 대시보드 멤버 ----
grant usage on schema honbap, menu, price, taste, distance, weather to anon, authenticated, service_role;
grant select on all tables in schema honbap, taste to anon, authenticated;
revoke select on honbap.check_queue from anon, authenticated;
grant all on all tables in schema honbap, menu, price, taste, distance, weather to service_role;
grant usage, select on all sequences in schema honbap, taste to service_role;
grant execute on function honbap.honbap_score(text[]) to anon, authenticated, service_role;
alter default privileges in schema menu, price, taste, distance, weather grant select on tables to anon, authenticated;
alter default privileges in schema menu, price, taste, distance, weather grant all on tables to service_role;
alter default privileges in schema menu, price, taste, distance, weather grant usage, select on sequences to service_role;

alter table honbap.settings     enable row level security;
alter table honbap.restaurants  enable row level security;
alter table honbap.evidence     enable row level security;
alter table honbap.main_menus   enable row level security;
alter table honbap.search_log   enable row level security;
alter table honbap.check_queue  enable row level security;
alter table taste.solo_seats    enable row level security;

create policy settings_read     on honbap.settings    for select to anon, authenticated using (true);
create policy restaurants_read  on honbap.restaurants for select to anon, authenticated using (true);
create policy evidence_read     on honbap.evidence    for select to anon, authenticated using (true);
create policy main_menus_read   on honbap.main_menus  for select to anon, authenticated using (true);
create policy search_log_read   on honbap.search_log  for select to anon, authenticated using (true);
create policy solo_seats_read   on taste.solo_seats   for select to anon, authenticated using (true);
-- check_queue는 앱이 읽지 않으므로 anon·authenticated 정책 없음(service_role만)
