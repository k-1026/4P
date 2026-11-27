# -*- coding: utf-8 -*-
"""데이터 준비 (v2 초안) — 메뉴 에이전트가 하던 일을 코드로 한다.

가게마다 아래 값을 미리 계산해 가게 데이터에 붙인다. 같은 입력이면 늘 같은 값이 나온다.
  price            1인 가격 = 1인 메뉴 가격의 중앙값 (사사오입). 가격이 하나도 없으면 None
  price_confidence 사람확인 근거가 있으면 high, 가격이 있으면 mid, 없으면 low
  kind             음식 종류 11가지 중 하나 (대표 메뉴 낱말 규칙 → 업종 대응표)
  kind_source      "메뉴 낱말" 또는 "업종"
  weather_type     따뜻한 국물 / 따뜻한 요리 / 차가운 요리
  soup             대표 메뉴가 국물 요리인지

python3 -I v2_가격메뉴_코드화_초안/prepare.py
  입력: data/stores_동성로391.json, data/메뉴.json (팀 안에서만 쓰는 파일)
  출력: data/stores_prepared_v2.json (팀 안에서만), 화면에 채워진 비율
규칙은 같은 폴더 criteria.json의 menu · budget 부분에서 읽는다.
"""
import json
import math
import os
import re
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
C = json.load(open(os.path.join(HERE, "criteria.json"), encoding="utf-8"))
M = C["menu"]
CONF = C["budget"]["confidence_rules"]


def median_price(prices):
    ps = [p for p in prices if p]
    return math.floor(statistics.median(ps) + 0.5) if ps else None


def kind_of(main_menu, category):
    name = (main_menu or "").replace(" ", "")
    for kind, pattern in M["kind_keywords"]:
        if name and re.search(pattern, name):
            return kind, "메뉴 낱말"
    return M["category_to_kind"].get(category, "기타"), "업종"


def is_soup(name):
    return bool(name and re.search(M["weather_soup_keywords"], name.replace(" ", "")))


def weather_type_of(main_menu, kind):
    name = (main_menu or "").replace(" ", "")
    if name and re.search(M["weather_cold_keywords"], name):
        return "차가운 요리"
    if is_soup(name):
        return "따뜻한 국물"
    return M["weather_kind_default"].get(kind, "따뜻한 요리")


def prepare_store(store, menus):
    main = menus[0]["name"] if menus else None
    kind, src = kind_of(main, store.get("cat"))
    price = median_price([m.get("price") for m in menus])
    human = any(o.get("status") == "사람확인" for o in store.get("one_serving_menus", []))
    conf = CONF["no_price"] if price is None else (CONF["human_checked"] if human else CONF["ai_seen"])
    return {"store_id": store["store_id"], "name": store["name"], "cat": store.get("cat"),
            "main_menu": main, "prices": [m["price"] for m in menus if m.get("price")],
            "price": price, "price_confidence": conf,
            "kind": kind, "kind_source": src,
            "weather_type": weather_type_of(main, kind), "soup": is_soup(main)}


def main():
    stores = json.load(open(os.path.join(ROOT, "data", "stores_동성로391.json"), encoding="utf-8"))["stores"]
    menus = json.load(open(os.path.join(ROOT, "data", "메뉴.json"), encoding="utf-8"))["menus"]
    out = [prepare_store(s, menus.get(s["store_id"], [])) for s in stores]
    dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "stores_prepared_v2.json")
    json.dump({"made": "2026-11-27", "rules": "v2_가격메뉴_코드화_초안/criteria.json menu·budget",
               "note": "팀 안에서만 쓴다. 공개 저장소에 올리지 않는다.", "stores": out},
              open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(out)
    print(f"가게 {n}곳 → {dst}")
    print("1인 가격 있음:", sum(1 for s in out if s["price"] is not None))
    print("확실도:", dict(Counter(s["price_confidence"] for s in out)))
    print("음식 종류:", dict(Counter(s["kind"] for s in out).most_common()))
    print("종류 출처:", dict(Counter(s["kind_source"] for s in out)))
    print("날씨용 종류:", dict(Counter(s["weather_type"] for s in out)))


if __name__ == "__main__":
    main()
