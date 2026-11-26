-- 매주 갱신(클라우드)용 표 (2026-11-26). 001_틀.sql 다음에 적용한다. 앱은 읽지 않는 안쪽 표라 anon 정책이 없다.

create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

-- 새 가게 후보 정보(좌표·동·업태 등)를 확인 대기에 함께 둔다
alter table honbap.check_queue add column if not exists info jsonb;
comment on column honbap.check_queue.info is '새 가게 후보 정보(인허가: 관리번호·업태·인허가일·좌표·행정동 추정 등)';

-- 비교용 동성로 목록(뺀 가게 포함 1,348곳). 새 가게가 '이미 있는 가게'인지, 동성로 안인지 볼 때 쓴다
create table honbap.known_shops (
  collect_id   text primary key,
  name         text not null,
  road_address text not null,
  lat          double precision,
  lng          double precision,
  dong         text
);
comment on table honbap.known_shops is '동성로 목록(뺀 가게 포함): 매주 갱신이 새 가게·동성로 밖을 가를 때 씀';

-- 폐업으로 뺀 가게 기록(가게 줄은 지워지므로 여기 남김)
create table honbap.closed_log (
  log_id        bigint generated always as identity primary key,
  restaurant_id text not null,
  name          text not null,
  permit_name   text,
  closed_on     date,
  mng_no        text,
  road_address  text,
  applied_at    timestamptz not null default now()
);
comment on table honbap.closed_log is '폐업으로 뺀 가게 기록(인허가 폐업 + 상호·주소가 같음)';

-- 매주 실행 기록
create table honbap.weekly_runs (
  run_id        bigint generated always as identity primary key,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  since         date not null,
  status        text not null check (status in ('도는중', '끝', '멈춤')),
  read_rows     int,
  new_count     int,
  closed_count  int,
  recheck_count int,
  message       text
);
comment on table honbap.weekly_runs is '매주 갱신 실행 기록(멈춤이면 message에 이유)';

-- 후기 다시 볼 가게: 1인분인데 혼밥 후기가 5명 미만(기존 대기 + 새 가게)
create table honbap.recheck_targets (
  target_key   text primary key,
  kind         text not null check (kind in ('새가게', '기존')),
  name         text not null,
  road_address text,
  map_url      text,
  first_seen   date not null,
  judgment     jsonb,
  created_at   timestamptz not null default now()
);
comment on table  honbap.recheck_targets is '후기 다시 볼 가게: 새 가게는 처음 본 뒤 2·4·8주, 그 뒤와 기존 대기는 매달(한 번에 최대 30곳)';
comment on column honbap.recheck_targets.judgment is '새 가게의 1인분 판정 결과(5명을 넘으면 이것으로 DB에 넣음)';

create table honbap.recheck_log (
  log_id      bigint generated always as identity primary key,
  target_key  text not null references honbap.recheck_targets (target_key) on delete cascade,
  seen_on     date not null,
  found       text not null check (found in ('예', '아니오')),
  count_value int check (count_value is null or count_value >= 0),
  link        text,
  memo        text
);
create index recheck_log_target_idx on honbap.recheck_log (target_key, seen_on desc);
comment on table honbap.recheck_log is '후기 다시 본 결과(못 찾음·폐업·휴업이면 그 뒤로 안 봄)';

alter table honbap.known_shops     enable row level security;
alter table honbap.closed_log      enable row level security;
alter table honbap.weekly_runs     enable row level security;
alter table honbap.recheck_targets enable row level security;
alter table honbap.recheck_log     enable row level security;
revoke all on honbap.known_shops, honbap.closed_log, honbap.weekly_runs, honbap.recheck_targets, honbap.recheck_log from anon, authenticated;
grant all on honbap.known_shops, honbap.closed_log, honbap.weekly_runs, honbap.recheck_targets, honbap.recheck_log to service_role;
grant usage, select on all sequences in schema honbap to service_role;
