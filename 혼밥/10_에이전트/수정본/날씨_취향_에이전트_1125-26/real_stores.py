"""실제 가게 데이터: 혼밥 DB(마이/data/혼밥_동성로.db)를 앱과 에이전트가 쓰는 모양으로 바꾼다.

DB에는 '1인분이 되고 혼자 가서 먹을 수 있는' 동성로 가게만 들어 있다 (혼밥DB 1차본, 276곳).
DB에 없는 값(별점, 대기, 1인석, 키오스크 …)은 지어내지 않고 비워 둔다(None).

  load()                 DB의 가게 목록 (앱 번호 id는 1001부터, 식당ID 순서로 고정)
  app_stores()           앱(혼밥_홈화면_v2.html)의 가게 목록 R 모양
  agent_stores(place)    조율자·에이전트용 가게 목록 (내 위치에서 잰 거리)
  menus() / solo()       가정 메뉴·혼밥 에이전트에게 넘길 메뉴와 1인분 정보
  python real_stores.py  앱 HTML 안의 가게 목록을 DB 내용으로 다시 만든다
"""
import json
import math
import os
import re
import sqlite3
import sys
import threading

import user_location

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "혼밥_동성로.db")
APP_HTML = os.path.join(ROOT, "혼밥_홈화면_v2.html")
FIRST_ID = 1001
IDS = os.path.join(ROOT, "data", "store_ids.json")  # 식당ID -> 앱 번호 (한 번 정하면 바뀌지 않는다)
_LOCK = threading.Lock()
_CACHE = {}
AREA = {"name": "동성로", "lat": 35.8690, "lng": 128.5955}  # 동성로(성내1~3동) 가운데쯤
START, END = "/*REAL_DATA_START*/", "/*REAL_DATA_END*/"

# DB 업종 -> (아이콘, 그림 색, 에이전트용 분류). 분류는 app_data.CAT_MAP의 이름을 쓴다
KINDS = {
    "백반/한정식": ("🍚", "#e8eedb,#a9c08a", "한식"), "일식 회/초밥": ("🍣", "#fde2dc,#e98a76", "초밥"),
    "경양식": ("🍛", "#f5e6c8,#d9a441", "돈까스"), "김밥/만두/분식": ("🍙", "#fbe9d0,#e5a15a", "분식"),
    "중국집": ("🥟", "#fbe0d0,#d9774f", "중식"), "국/탕/찌개류": ("🍲", "#f1e2c9,#c9935a", "국밥"),
    "베트남식 전문": ("🍜", "#e3efd8,#94b874", "국수"), "일식 면 요리": ("🍜", "#f6d9b8,#e9a35f", "라멘"),
    "마라탕/훠궈": ("🌶", "#fbd5cf,#d9534f", "샤브"), "토스트/샌드위치/샐러드": ("🥪", "#f6ecd0,#d7b45a", "샐러드"),
    "버거": ("🍔", "#f7e0c4,#d98f3f", "버거"), "돼지고기 구이/찜": ("🥓", "#f3c7b5,#c8553a", "고기"),
    "국수/칼국수": ("🍜", "#f1e7cf,#c9a660", "국수"), "패밀리레스토랑": ("🍽", "#e9e3f3,#a593c9", "양식"),
    "일식 카레/돈가스/덮밥": ("🍛", "#f5e6c8,#d9a441", "덮밥"), "소고기 구이/찜": ("🥩", "#f3c7b5,#b84a3a", "고기"),
    "냉면/밀면": ("🍜", "#dfeef5,#7fb2cc", "국수"), "기타 서양식 음식점": ("🍝", "#f5e6c8,#d9a441", "양식"),
    "횟집": ("🐟", "#dbeef0,#6fb3b8", "초밥"), "닭/오리고기 구이/찜": ("🍗", "#f6dcc4,#cf8a4e", "고기"),
    "기타 일식 음식점": ("🍱", "#fde2dc,#e98a76", "덮밥"), "그 외 기타 간이 음식점": ("🍴", "#ece6df,#a8998a", "분식"),
    "뷔페": ("🍽", "#e9e3f3,#a593c9", "뷔페"), "기타 한식 음식점": ("🍚", "#e8eedb,#a9c08a", "한식"),
    "기타 동남아식 전문": ("🍛", "#e3efd8,#94b874", "기타"),
}
SOUP = re.compile(r"국밥|탕|찌개|국수|칼국수|라멘|라면|우동|쌀국수|짬뽕|샤브|마라|전골|해장|곰탕|육개장|수제비|짜글이|훠궈|포$|국$")
COLD = re.compile(r"냉면|밀면|물회|냉모밀|메밀|콩국수|비빔국수")


def _rows(path=DB):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)  # 읽기만 한다
    con.row_factory = sqlite3.Row
    try:
        shops = con.execute("SELECT h.*, s.겹친ID FROM 혼밥가게 h JOIN 식당 s USING(식당ID) ORDER BY 식당ID").fetchall()
        one = {}
        for r in con.execute("SELECT 식당ID, 메뉴명, 가격, 상태, 판단, 출처, 본날 FROM 근거 WHERE 항목='일인메뉴' "
                             "ORDER BY 본날 DESC, 근거ID"):
            one.setdefault(r["식당ID"], dict(r))
        mains = {}
        for r in con.execute("SELECT 식당ID, 메뉴명, 가격, 가격단위, 곁들임일수있음 FROM 주요메뉴 ORDER BY rowid"):
            mains.setdefault(r["식당ID"], []).append({"name": r["메뉴명"], "price": r["가격"], "unit": r["가격단위"],
                                                     "side": bool(r["곁들임일수있음"])})
        made = dict(con.execute("SELECT 이름, 값 FROM 설정").fetchall())
    finally:
        con.close()
    return shops, one, mains, made


def stable_ids(shops, ids_path=IDS):
    """가게마다 앱 번호를 한 번만 정한다. 갱신해서 가게가 늘거나 빠져도 기존 가게 번호는 그대로이고,
    새 가게만 새 번호를 받는다 (핸드폰의 일기·찜·방문 기록이 번호로 가게를 기억하기 때문).
    같은 가게라 합쳐진 경우(겹친ID)는 예전 번호를 이어받는다."""
    with _LOCK:
        try:
            with open(ids_path, encoding="utf-8") as file:
                known = {str(k): int(v) for k, v in json.load(file).items()}
        except (OSError, ValueError):
            known = {}
        changed = False
        if not known:  # 처음: 지금까지 쓰던 번호(식당ID 순서 1001부터)를 그대로 기록한다
            known = {s["식당ID"]: FIRST_ID + i for i, s in enumerate(shops)}
            changed = True
        used = set(known.values())
        for s in shops:
            if s["식당ID"] in known:
                continue
            old = [known[o.strip()] for o in str(s["겹친ID"] or "").replace(";", ",").split(",") if o.strip() in known]
            known[s["식당ID"]] = old[0] if old else max(used | {FIRST_ID - 1}) + 1
            used.add(known[s["식당ID"]])
            changed = True
        if changed:
            os.makedirs(os.path.dirname(ids_path), exist_ok=True)
            tmp = ids_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as file:
                json.dump(known, file, ensure_ascii=False, indent=0)
            os.replace(tmp, ids_path)
        return known


def load(path=DB, ids_path=IDS):
    """DB의 가게 목록. DB 파일이 바뀌지 않았으면 전에 읽은 것을 다시 쓴다."""
    key = (os.path.abspath(path), os.path.getmtime(path), os.path.getsize(path), ids_path)
    if _CACHE.get("key") == key:
        return _CACHE["value"]
    value = _load(path, ids_path)
    _CACHE.update(key=key, value=value)
    return value


def _load(path, ids_path):
    shops, one, mains, made = _rows(path)
    ids = stable_ids(shops, ids_path)
    stores = []
    for s in shops:
        ic, bg, kcat = KINDS.get(s["업종"], ("🍴", "#ece6df,#a8998a", "기타"))
        ev = one.get(s["식당ID"], {})
        menu, price = ev.get("메뉴명"), ev.get("가격")
        menu = menu or (s["일인메뉴"] or "").split(";")[0].strip() or None
        text = f"{menu or ''} {s['상호']} {s['업종']}"
        stores.append({
            "id": ids[s["식당ID"]], "sid": s["식당ID"], "name": s["상호"], "cat": s["업종"], "kcat": kcat, "ic": ic, "bg": bg,
            "dong": s["행정동"], "addr": s["도로명주소"], "lat": s["위도"], "lng": s["경도"], "link": s["지도링크"],
            "cnt": s["혼밥후기수"], "menu": menu, "price": price, "checked": s["마지막확인일"],
            "soup": bool(SOUP.search(text)) and not COLD.search(text),
            "menus": [m for m in mains.get(s["식당ID"], [])][:3],
            # 정보를 누가 확인했나: 사람확인(팀이 확인) / 검토전(AI가 지도 메뉴 화면을 보고 적음)
            "verified": ev.get("상태") == "사람확인", "basis": ev.get("판단"), "source": ev.get("출처"), "seen": ev.get("본날"),
        })
    return stores, made


def app_stores(path=DB):
    """앱의 R 모양. DB에 없는 값은 null (화면에서 '정보 없음'으로 보이거나 숨긴다)."""
    stores, made = load(path)
    lats, lngs = [s["lat"] for s in stores], [s["lng"] for s in stores]
    out = []
    for s in stores:
        dist = round(user_location.distance_m(AREA["lat"], AREA["lng"], s["lat"], s["lng"]))
        tags = ["1인분 가능"] + ([f"혼밥 좋아요 {s['cnt']}"] if s["cnt"] else [])
        out.append({
            "id": s["id"], "sid": s["sid"], "area": 0, "name": s["name"], "cat": s["cat"], "ic": s["ic"], "bg": s["bg"],
            "lv": 1 if not s["price"] or s["price"] < 10000 else 2 if s["price"] < 15000 else 3,
            "rate": None, "cnt": s["cnt"], "tags": tags, "seat": None, "kiosk": None, "wait": None, "min": None,
            "dist": dist, "price": s["price"], "menu": s["menu"] or "1인 메뉴", "soup": s["soup"], "grill": "구이" in s["cat"],
            "outlet": None, "quiet": None, "lat": s["lat"], "lng": s["lng"], "link": s["link"], "addr": s["addr"],
            "dong": s["dong"], "checked": s["checked"], "menus": s["menus"], "real": True,
            "verified": s["verified"], "basis": s["basis"], "source": s["source"], "seen": s["seen"],
            "x": round(8 + 84 * (s["lng"] - min(lngs)) / (max(lngs) - min(lngs) or 1), 1),
            "y": round(8 + 84 * (max(lats) - s["lat"]) / (max(lats) - min(lats) or 1), 1),
        })
    return out, made


def agent_stores(place, path=DB):
    """조율자·에이전트용. 거리는 place(내 위치)에서 잰 직선거리."""
    stores, _ = load(path)
    result = []
    for s in stores:
        dist = round(user_location.distance_m(place["lat"], place["lng"], s["lat"], s["lng"]))
        result.append({"id": s["id"], "area": 0, "name": s["name"], "cat": s["kcat"], "menu": s["menu"] or "",
                       "price": s["price"], "soup": s["soup"], "lat": s["lat"], "lng": s["lng"],
                       "rate": None, "cnt": s["cnt"], "dist_m": dist, "dist_from": "내 위치",
                       "walk_min": math.ceil(dist / 67), "real": True})
    return result


def menus(path=DB):
    """메뉴 에이전트가 쓰는 메뉴: DB의 주요메뉴 중 '단품'이고 곁들임 표시가 없는 것만 (없으면 1인 메뉴).
    크기·세트·무게 단위 메뉴와 곁들임일 수 있는 메뉴(최소주문금액, 공기밥 추가 등)는 가격 계산을 틀리게 하므로 뺀다."""
    stores, made = load(path)
    out = {}
    for s in stores:
        items = [{"name": m["name"], "price": m["price"], "soup": bool(SOUP.search(m["name"]))}
                 for m in s["menus"] if usable(m)]
        if not items and s["menu"]:
            items = [{"name": s["menu"], "price": s["price"], "soup": s["soup"]}]
        if items:
            out[s["id"]] = items
    return out, made.get("만든날")


def usable(menu):
    """가격 계산에 써도 되는 메뉴인가: 가격이 있고, 단품이고, 곁들임 표시가 없다"""
    return bool(menu.get("price")) and menu.get("unit") in (None, "단품") and not menu.get("side")


def solo(path=DB):
    """가정 혼밥 에이전트에게: DB 가게는 모두 1인분 가능. 1인석은 아직 모으지 않아 모름(None)."""
    stores, made = load(path)
    return {s["id"]: {"single_ok": True, "seat": None,
                      "seat_text": None} for s in stores}, made.get("만든날")


def data_block(db=DB):
    """앱 HTML 안에 들어가는 가게 목록 부분 (START~END)"""
    stores, made = app_stores(db)
    return (f"{START}\n/* 실제 데이터: 혼밥DB 동성로 ({made.get('만든날', '')}), {len(stores)}곳. "
            "DB에 없는 값(별점·대기·1인석 등)은 null. 핸드폰 서버는 앱을 보낼 때마다 DB에서 새로 넣는다 */\n"
            f"const AREAS = {json.dumps([AREA], ensure_ascii=False)};\n"
            f"const R = {json.dumps(stores, ensure_ascii=False, separators=(',', ':'))};\n{END}")


def fill(html, db=DB):
    """앱 HTML의 가게 목록 부분을 DB 내용으로 바꾼 글을 돌려준다 (파일은 건드리지 않음)"""
    if START not in html:
        return html
    a, b = html.index(START), html.index(END) + len(END)
    return html[:a] + data_block(db) + html[b:]


def write_app(path=APP_HTML, db=DB):
    """앱 HTML 파일의 가게 목록을 DB 내용으로 바꿔 저장한다 (PC에서 파일로 열 때용).
    처음 한 번은 예전 샘플 목록을 찾아 바꾼다."""
    stores, _ = app_stores(db)
    block = data_block(db)
    html = open(path, encoding="utf-8").read()
    if START in html:
        a, b = html.index(START), html.index(END) + len(END)
    else:
        a = html.index("const AREAS = [")
        b = html.index("];", html.index("const R = [")) + 2
    html = html[:a] + block + html[b:]
    with open(path, "w", encoding="utf-8") as file:
        file.write(html)
    return len(stores)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"앱에 실제 가게 {write_app()}곳을 넣었어요.")
