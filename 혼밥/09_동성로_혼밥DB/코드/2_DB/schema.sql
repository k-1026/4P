-- 혼밥 DB (동성로, 2026-11-26). 혼밥DB_시안_20261125의 틀을 바탕으로 사용자와 정한 칸.
-- 이 DB에는 '1인분이 되고 혼자 가서 먹을 수 있는' 가게만 들어간다(11-26 팀 결정).
-- 판정(추천할지)은 저장하지 않는다. 근거만 저장하고, 추천은 조율자 에이전트가 정한다.
-- 혼밥 점수(10점 만점)는 저장하지 않는다. 앱이 넘겨준 가게들(위치 기반 20곳) 안에서 혼밥점수.py가 그때그때 계산한다(11-26 결정).
CREATE TABLE 설정(이름 TEXT PRIMARY KEY, 값 TEXT NOT NULL);

CREATE TABLE 식당(
  식당ID TEXT PRIMARY KEY, 상호 TEXT NOT NULL, 업종 TEXT, 구군 TEXT NOT NULL, 행정동 TEXT, 도로명주소 TEXT NOT NULL,
  위도 REAL NOT NULL, 경도 REAL NOT NULL, 지도링크 TEXT, 지도가게번호 TEXT,
  처음넣은날 TEXT NOT NULL, 마지막확인일 TEXT NOT NULL,
  겹친ID TEXT);   -- 같은 지도 가게로 보여 합친 다른 목록 ID

-- 근거 한 줄 = 한 가게에서 본 사실 하나. 리뷰 글·작성자는 넣지 않는다.
CREATE TABLE 근거(
  근거ID INTEGER PRIMARY KEY, 식당ID TEXT NOT NULL REFERENCES 식당(식당ID) ON DELETE CASCADE,
  항목 TEXT NOT NULL CHECK(항목 IN ('일인메뉴','최소주문','크기세트만','혼밥후기수','1인석')),
  메뉴명 TEXT, 인분 INTEGER CHECK(인분 IS NULL OR 인분>=1), 가격 INTEGER CHECK(가격 IS NULL OR 가격>0),
  수 INTEGER CHECK(수 IS NULL OR 수>=0),
  요지 TEXT NOT NULL, 판단 TEXT,
  출처 TEXT NOT NULL CHECK(출처 IN ('메뉴글','메뉴사진','카카오메뉴','리뷰키워드','혼밥일기','정보탭')),
  주소링크 TEXT, 본날 TEXT NOT NULL,
  상태 TEXT NOT NULL CHECK(상태 IN ('사람확인','검토전')), 확인자 TEXT,
  CHECK(상태<>'사람확인' OR 확인자 IS NOT NULL),
  CHECK(항목<>'혼밥후기수' OR 수 IS NOT NULL),
  CHECK(항목<>'일인메뉴' OR 인분=1),
  CHECK(항목<>'최소주문' OR 인분>=2),
  CHECK(항목<>'1인석' OR (수 IN (0,1) AND 출처 IN ('혼밥일기','정보탭'))));   -- 1인석: 수 1=있음(1인석·바 좌석), 0=없음

-- 가게의 주요 요리(최대 3개)와 가격. 가격·메뉴 에이전트가 쓸 수 있다.
CREATE TABLE 주요메뉴(
  식당ID TEXT NOT NULL REFERENCES 식당(식당ID) ON DELETE CASCADE, 메뉴명 TEXT NOT NULL, 가격 INTEGER,
  가격단위 TEXT CHECK(가격단위 IN ('단품','크기·세트','무게')), 곁들임일수있음 INTEGER NOT NULL DEFAULT 0, 본날 TEXT NOT NULL);

-- 언제 어디서 찾아봤는지. 갱신할 때 다시 볼 곳을 고르는 데 쓴다.
CREATE TABLE 검색기록(
  기록ID INTEGER PRIMARY KEY, 식당ID TEXT NOT NULL REFERENCES 식당(식당ID) ON DELETE CASCADE, 찾은날 TEXT NOT NULL,
  찾은곳 TEXT NOT NULL, 결과 TEXT NOT NULL CHECK(결과 IN ('있음','없음','못 찾음','막힘')), 메모 TEXT);

-- 다른 에이전트가 읽기 쉬운 보기: 가게 한 줄 + 가장 최근 혼밥 후기 수 + 1인 메뉴 + 1인석.
-- 1인석은 출처(혼밥일기·정보탭)마다 가장 최근 줄을 보고, 하나라도 '있음'이면 있음. 줄이 없으면 비어 있음(모름).
CREATE VIEW 혼밥가게 AS
SELECT s.식당ID, s.상호, s.업종, s.행정동, s.도로명주소, s.위도, s.경도, s.지도링크,
  (SELECT 수 FROM 근거 g WHERE g.식당ID=s.식당ID AND 항목='혼밥후기수' ORDER BY 본날 DESC, 근거ID DESC LIMIT 1) AS 혼밥후기수,
  (SELECT group_concat(coalesce(메뉴명,요지) || coalesce(' ' || 가격 || '원',''), '; ') FROM 근거 g WHERE g.식당ID=s.식당ID AND 항목='일인메뉴') AS 일인메뉴,
  s.마지막확인일,
  (SELECT CASE WHEN max(수)=1 THEN '있음' WHEN count(*)>0 THEN '없음' END FROM 근거 g
    WHERE g.식당ID=s.식당ID AND g.항목='1인석' AND NOT EXISTS (SELECT 1 FROM 근거 h WHERE h.식당ID=g.식당ID AND h.항목='1인석'
      AND h.출처=g.출처 AND (h.본날>g.본날 OR (h.본날=g.본날 AND h.근거ID>g.근거ID)))) AS 일인석,
  (SELECT group_concat(출처, ', ') FROM 근거 g
    WHERE g.식당ID=s.식당ID AND g.항목='1인석' AND g.수=1 AND NOT EXISTS (SELECT 1 FROM 근거 h WHERE h.식당ID=g.식당ID AND h.항목='1인석'
      AND h.출처=g.출처 AND (h.본날>g.본날 OR (h.본날=g.본날 AND h.근거ID>g.근거ID)))) AS 일인석출처
FROM 식당 s;
