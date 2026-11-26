"""최종본 DB(honbap_db_final/혼밥_동성로.db) → 1126proto 에이전트 입력 JSON 3개.

python3 -I data/build_from_final_db.py
만드는 것: stores_동성로391.json, 메뉴.json, id_map_app276_to_db.json (모두 이 폴더)
"""
import json, sqlite3, re, math, os
D = os.path.dirname(os.path.abspath(__file__))
# 이름 표기만 달라 자동으로 못 잇는 가게 (동성로 중심 거리·혼밥 후기 수가 같음을 확인, 2026-11-26)
MANUAL = [{"app_id": 1105, "app_name": "수제냉면떡갈비삼락원냉면", "store_id": "MA010120220801356753", "db_name": "삼락원",
           "why": "이름 표기만 다름. 동성로 중심 거리 63m, 혼밥 후기 76명이 둘 다 같다"}]
db = sqlite3.connect(f"file:{D}/honbap_db_final/혼밥_동성로.db?mode=ro", uri=True); db.row_factory = sqlite3.Row
stores, menus = [], {}
for s in db.execute("SELECT * FROM 혼밥가게 ORDER BY 혼밥후기수 DESC, 식당ID"):
    sid = s["식당ID"]
    seen = db.execute("SELECT 본날 FROM 근거 WHERE 식당ID=? AND 항목='혼밥후기수' ORDER BY 본날 DESC, 근거ID DESC LIMIT 1", (sid,)).fetchone()[0]
    one = [{"name": g["메뉴명"], "price": g["가격"], "text": g["요지"], "source": g["출처"], "seen_on": g["본날"], "status": g["상태"]}
           for g in db.execute("SELECT * FROM 근거 WHERE 식당ID=? AND 항목='일인메뉴' ORDER BY 근거ID", (sid,))]
    main = [{"name": m["메뉴명"], "price": m["가격"], "unit": m["가격단위"], "maybe_side": bool(m["곁들임일수있음"]), "seen_on": m["본날"]}
            for m in db.execute("SELECT * FROM 주요메뉴 WHERE 식당ID=? ORDER BY rowid", (sid,))]
    stores.append({"store_id": sid, "name": s["상호"], "cat": s["업종"], "dong": s["행정동"], "road_address": s["도로명주소"],
                   "lat": s["위도"], "lng": s["경도"], "solo_review_count": s["혼밥후기수"], "solo_review_seen_on": seen,
                   "solo_seat": s["일인석"], "solo_seat_sources": s["일인석출처"], "single_ok": True,
                   "one_serving_menus": one, "main_menus": main, "last_checked": s["마지막확인일"]})
    # 메뉴.json: 1인 메뉴 근거 먼저(대표), 그다음 주요메뉴 중 단품·곁들임 아님. 이름이 같으면 한 번만.
    lst, names = [], set()
    for m in [{"name": o["name"], "price": o["price"], "from": "일인메뉴", "seen_on": o["seen_on"]} for o in one if o["name"]] + \
             [{"name": m["name"], "price": m["price"], "from": "주요메뉴", "seen_on": m["seen_on"]} for m in main if m["unit"] == "단품" and not m["maybe_side"]]:
        k = re.sub(r"\s", "", m["name"])
        if k not in names:
            names.add(k); lst.append({**m, "soup": None})
    menus[sid] = lst
meta = {"made": "2026-11-26", "source": "honbap_db_final/혼밥_동성로.db (혼밥팀 최종본 2026-11-26, 391곳)",
        "note": "1인분·혼밥 후기는 AI가 지도 화면을 보고 적은 값(사람 확인 17곳). 지도 링크는 넣지 않았다. 공개 저장소에 올리지 않는다."}
json.dump({**meta, "count": len(stores), "stores": stores}, open(f"{D}/stores_동성로391.json", "w"), ensure_ascii=False, indent=1)
json.dump({**meta, "rule": "store_id -> 1인 메뉴 목록. 일인메뉴 근거(첫 메뉴가 대표) + 주요메뉴 중 가격단위 '단품'·곁들임 아님. soup은 메뉴 에이전트가 정한다(null).",
           "menus": menus}, open(f"{D}/메뉴.json", "w"), ensure_ascii=False, indent=1)
# 앱 1차본(276곳, 번호 1001~) → 식당ID. 이름이 같고, 같은 이름이 여럿이면 동성로 중심(35.8690, 128.5955)에서 잰 거리로 고른다.
app = json.load(open(f"{D}/stores_app_동성로276.json"))["restaurants"]
by = {}
for s in stores: by.setdefault(re.sub(r"\s", "", s["name"]), []).append(s)
def dist(s):
    return 6371000 * math.hypot(math.radians(s["lat"] - 35.8690), math.radians(s["lng"] - 128.5955) * math.cos(math.radians(35.8690)))
idmap, unmatched, ambiguous = {}, [], []
for a in app:
    c = by.get(re.sub(r"\s", "", a["name"]), [])
    m = [x for x in MANUAL if x["app_id"] == a["id"]]
    if m:
        idmap[str(a["id"])] = m[0]["store_id"]; continue
    if not c:
        unmatched.append({"app_id": a["id"], "name": a["name"]}); continue
    best = min(c, key=lambda s: abs(dist(s) - (a["dist"] or 0)))
    idmap[str(a["id"])] = best["store_id"]
    if len(c) > 1:
        ambiguous.append({"app_id": a["id"], "name": a["name"], "app_dist": a["dist"], "picked": best["store_id"],
                          "candidates": {s["store_id"]: round(dist(s)) for s in c}})
json.dump({**meta, "rule": "이름(공백 무시)이 같은 가게. 같은 이름이 여럿이면 앱 dist와 동성로 중심 거리가 가장 가까운 곳.",
           "map": dict(sorted(idmap.items(), key=lambda kv: int(kv[0]))), "unmatched": unmatched, "ambiguous": ambiguous, "manual": MANUAL},
          open(f"{D}/id_map_app276_to_db.json", "w"), ensure_ascii=False, indent=1)
print(len(stores), sum(len(v) for v in menus.values()), "menus,", sum(1 for v in menus.values() if not any(m["price"] for m in v)), "stores w/o price")
print("map", len(idmap), "unmatched", unmatched, "ambiguous", json.dumps(ambiguous, ensure_ascii=False))
print("seat", sum(s["solo_seat"] is not None for s in stores))
