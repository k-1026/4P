"""파일 DB(혼밥_동성로.db)를 Supabase honbap 구역에 올린다(덮어쓰기). 인터넷 주소 API(PostgREST)를 쓴다.

python -I -B 올리기.py [--점검만]

준비(주인 계정에서 한 번):
- Supabase 화면 → Project Settings → Data API → Exposed schemas 에 honbap 을 더함(앱도 이것이 있어야 읽음)
- Supabase 화면 → Project Settings → API Keys 의 secret 키(또는 service_role 키)를
  갱신/.env 에 SUPABASE_SERVICE_KEY=... 한 줄로 넣음. 이 키는 깃에 올리지 않고 화면·로그에 찍지 않는다.
하는 일: honbap.restaurants를 비우고(근거·주요메뉴·검색기록·1인석은 함께 지워짐) 파일 DB 내용을 다시 넣는다. settings는 바꿀 줄만 덮어쓴다.
--점검만: 올릴 줄 수만 세고 아무것도 보내지 않는다.
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DBDIR = os.path.dirname(HERE)
URL = "https://zcqzfwswjdczovumpkop.supabase.co/rest/v1"
BATCH = 300


def key():
    p = os.path.join(DBDIR, "갱신", ".env")
    for line in open(p, encoding="utf-8-sig"):
        k, _, v = line.strip().partition("=")
        if k.strip() == "SUPABASE_SERVICE_KEY" and v.strip():
            return v.strip().strip("'\"")
    raise SystemExit("갱신/.env 에 SUPABASE_SERVICE_KEY= 줄이 없음(Supabase 화면 → Project Settings → API Keys 의 secret 키)")


def call(method, path, body=None, extra=None):
    k = key()
    h = {"apikey": k, "Content-Type": "application/json",
         "Accept-Profile": "honbap", "Content-Profile": "honbap", "Prefer": "return=minimal"}
    if not k.startswith("sb_"):   # 예전 service_role 키(JWT)만 Authorization에도 넣는다. 새 sb_secret_ 키는 apikey로만
        h["Authorization"] = f"Bearer {k}"
    h.update(extra or {})
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, headers=h, method=method)
    for n in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            if e.code < 500 or n == 2:
                raise SystemExit(f"{method} {path.split('?')[0]} 실패 {e.code}: {msg}")
        except OSError as e:
            if n == 2:
                raise SystemExit(f"{method} {path.split('?')[0]} 실패: {type(e).__name__}")
        time.sleep(3)


def rows():
    c = sqlite3.connect("file:" + os.path.join(DBDIR, "혼밥_동성로.db") + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    q = lambda s: [dict(r) for r in c.execute(s)]  # noqa: E731
    R = [{"restaurant_id": r["식당ID"], "name": r["상호"], "category": r["업종"], "gu": r["구군"], "dong": r["행정동"],
          "road_address": r["도로명주소"], "lat": r["위도"], "lng": r["경도"], "map_url": r["지도링크"], "map_place_id": r["지도가게번호"],
          "first_added": r["처음넣은날"], "last_checked": r["마지막확인일"], "merged_ids": r["겹친ID"]} for r in q("SELECT * FROM 식당")]
    E = [{"restaurant_id": r["식당ID"], "item": r["항목"], "menu_name": r["메뉴명"], "servings": r["인분"], "price": r["가격"],
          "count_value": r["수"], "summary": r["요지"], "judgment": r["판단"], "source": r["출처"], "source_url": r["주소링크"],
          "seen_on": r["본날"], "status": r["상태"], "checker": r["확인자"]} for r in q("SELECT * FROM 근거 ORDER BY 근거ID")]
    M = [{"restaurant_id": r["식당ID"], "menu_name": r["메뉴명"], "price": r["가격"], "price_unit": r["가격단위"],
          "maybe_side": bool(r["곁들임일수있음"]), "seen_on": r["본날"]} for r in q("SELECT * FROM 주요메뉴")]
    L = [{"restaurant_id": r["식당ID"], "searched_on": r["찾은날"], "place": r["찾은곳"], "result": r["결과"], "memo": r["메모"]}
         for r in q("SELECT * FROM 검색기록 ORDER BY 기록ID")]
    S = [{"name": r["이름"], "value": r["값"]} for r in q("SELECT * FROM 설정")]
    return R, E, M, L, S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--점검만", action="store_true")
    a = ap.parse_args()
    R, E, M, L, S = rows()
    print(f"올릴 줄: 가게 {len(R)}, 근거 {len(E)}, 주요메뉴 {len(M)}, 검색기록 {len(L)}, 설정 {len(S)}")
    if a.점검만:
        return
    call("DELETE", "/restaurants?restaurant_id=not.is.null")   # 근거·주요메뉴·검색기록·1인석이 함께 지워짐
    for name, data in (("restaurants", R), ("evidence", E), ("main_menus", M), ("search_log", L)):
        for i in range(0, len(data), BATCH):
            call("POST", f"/{name}", data[i:i + BATCH])
        print(f"  {name} {len(data)}줄 올림", flush=True)
    call("POST", "/settings?on_conflict=name", S, {"Prefer": "return=minimal,resolution=merge-duplicates"})
    print("  settings 올림. 끝")


if __name__ == "__main__":
    main()
