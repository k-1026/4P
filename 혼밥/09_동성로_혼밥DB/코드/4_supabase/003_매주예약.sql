-- 매주 월요일 오전 9시(한국) = 월요일 00:00 UTC 에 honbap-weekly 함수를 부른다.
-- 먼저 할 것(주인 계정, Supabase 화면의 Vault 메뉴 → Add new secret. 메뉴 위치는 화면 판에 따라 Integrations 또는 Database 아래):
--   honbap_data_key   : 공공데이터포털 인허가 '디코딩' 인증키
--   honbap_cron_token : 아무 긴 글자(예: 비밀번호 만들듯 30자 이상). 예약과 함수가 서로 맞춰 보는 열쇠
-- 이 SQL은 비밀값을 담지 않는다(Vault에서 읽음).
select cron.schedule(
  'honbap-weekly',
  '0 0 * * 1',
  $$
  select net.http_post(
    url := 'https://zcqzfwswjdczovumpkop.supabase.co/functions/v1/honbap-weekly',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-honbap-token', (select decrypted_secret from vault.decrypted_secrets where name = 'honbap_cron_token')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 150000
  );
  $$
);
