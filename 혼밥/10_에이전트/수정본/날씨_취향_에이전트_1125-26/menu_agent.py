"""📋 메뉴 에이전트: 가게 데이터에 있는 메뉴를 읽어서 정리하고, 다른 에이전트에게 알려 준다.

점수·탈락·반론은 하지 않는다 (조율자 가중치 0%). 정해진 규칙은 하나:
  혼밥 앱이라 2인분 이상 메뉴(이름에 '2인', '2~3인', '3인' 등)는 전체 가게 데이터에서 모두 뺀다.
  메뉴를 빼고 나서 남는 메뉴가 없는 가게는 후보를 고르기 전에 가게째 뺀다 (before_candidates).
  메뉴 이름에 인원 숫자가 없으면 1인분으로 시킬 수 있다고 본다.

조율자가 부르는 순서
  ② 후보 고르기 전 before_candidates(): 1인 메뉴가 없는 가게를 뺀다 -> 그 자리는 다음 가게가 채운다
  ② 후보 고른 뒤   share(): 후보 가게마다 아래 정보를 붙여서 돌려준다

    menus        1인분으로 시킬 수 있는 메뉴 목록 [{"name", "price", "soup"}]  (첫 메뉴가 대표 메뉴)
    menu         대표 메뉴 이름
    removed_menus 2인분 이상이라 뺀 메뉴 이름들
    menu_from_main  메뉴 목록이 없어서 가게 데이터의 대표 메뉴 하나로 대신했으면 True
    kind         음식 종류 11가지 (취향 에이전트가 씀)
    weather_type 따뜻한 국물 / 따뜻한 요리 / 차가운 요리 (날씨 에이전트가 씀)
    soup         국물 메뉴가 있는지
    price_min, price_avg, price_max  남은 메뉴의 가격 범위 (가격 에이전트가 씀, 가격이 없으면 None)
    solo_menu    이름에 '1인'이 들어간 메뉴가 있는지 (혼밥 에이전트가 씀)

메뉴 목록은 어디서 오나 (앞의 것이 먼저)
  ① ctx["menus"]  : 가게 id -> 메뉴 목록 (예시 가게 sample_stores.MENUS 등)
  ② 메뉴.json     : 같은 모양의 파일. {"1": [{"name": "마제소바 1인 정식", "price": 11000, "soup": false}]}
  둘 다 없으면 가게 데이터의 대표 메뉴(menu, price, soup) 하나로 알려 준다.
"""
import json
import os
import re
from datetime import datetime

import app_data
from taste import josa

NAME = "메뉴"
FOLDER = os.path.dirname(os.path.abspath(__file__))
FILE = "메뉴.json"
MAX_BYTES = 2_000_000
MAX_PEOPLE = 1      # 혼밥 앱: 1인분까지만 남긴다
PEOPLE = re.compile(r"(\d+)\s*(?:~\s*\d+\s*)?인")
SHOW_NAMES = 3      # 뺀 가게 이름은 3곳까지만 말한다


def _clean_item(item):
    if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
        return None
    price = item.get("price")
    ok = isinstance(price, (int, float)) and not isinstance(price, bool) and price >= 0
    return {"name": item["name"].strip(), "price": price if ok else None, "soup": bool(item.get("soup"))}


def _clean(menus):
    """가게 id -> 메뉴 목록. 모양이 틀린 메뉴는 빼고, 남은 메뉴가 없는 가게도 뺀다."""
    if not isinstance(menus, dict):
        return {}
    result = {}
    for key, items in menus.items():
        items = [m for m in map(_clean_item, items if isinstance(items, list) else []) if m]
        if items:
            result[key] = items
    return result


def _read_file(folder):
    path = os.path.join(folder, FILE)
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return {}, None
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return {}, None
    return _clean(data), datetime.fromtimestamp(os.path.getmtime(path)).strftime("%m/%d %H:%M")


def prepare(ctx, folder=FOLDER):
    """메뉴 목록을 읽는다. 없어도 실패하지 않는다 (대표 메뉴로 대신 알려 줌)."""
    if ctx.get("menus") is not None:
        return {"menus": _clean(ctx["menus"]), "updated": ctx.get("menus_updated")}
    menus, updated = _read_file(folder)
    return {"menus": menus, "updated": updated}


def opinion(state, ctx):
    return ""  # 처음에 할 말은 없다. 후보가 나오면 메뉴를 알려 준다.


def people(name):
    """메뉴 이름의 인원: '2인' -> 2, '2~3인' -> 2, 숫자가 없으면 1"""
    found = PEOPLE.search(name)
    return int(found.group(1)) if found else 1


def menus_of(state, store):
    """(1인분 메뉴, 2인분 이상이라 뺀 메뉴 이름, 대표 메뉴로 대신했는지)"""
    menus = state.get("menus") or {}
    found = menus.get(store.get("id")) or menus.get(str(store.get("id")))
    from_main = not found
    if from_main:
        found = [_clean_item({"name": store.get("menu") or store.get("name"), "price": store.get("price"),
                              "soup": store.get("soup")})]
    solo = [m for m in found if people(m["name"]) <= MAX_PEOPLE]
    removed = [m["name"] for m in found if people(m["name"]) > MAX_PEOPLE]
    return solo, removed, from_main


def summarize(store, menus, removed=(), from_main=False):
    """가게 하나의 메뉴를 다른 에이전트가 바로 쓸 수 있는 값으로 정리한다."""
    main = menus[0]
    prices = [m["price"] for m in menus if m["price"] is not None]
    info = {"menus": menus, "menu": main["name"], "removed_menus": list(removed), "menu_from_main": from_main,
            "soup": any(m["soup"] for m in menus),
            "price_min": min(prices) if prices else None,
            "price_avg": round(sum(prices) / len(prices)) if prices else None,
            "price_max": max(prices) if prices else None,
            "solo_menu": any(PEOPLE.search(m["name"]) for m in menus)}
    info["kind"] = app_data.food_kind({**store, **info})
    info["weather_type"] = app_data.weather_type({**store, **info})
    return info


def _split(state, stores):
    kept, gone = [], []
    for store in stores:
        (kept if menus_of(state, store)[0] else gone).append(store)
    return kept, gone


def _gone_text(gone):
    names = ", ".join(s["name"] for s in gone[:SHOW_NAMES]) + (" 등" if len(gone) > SHOW_NAMES else "")
    return f"1인 메뉴가 없는 {len(gone)}곳({names})은 2인분부터라 후보에서 뺐어요."


def before_candidates(state, stores, ctx):
    """후보를 고르기 전, 전체 가게 데이터에서 1인 메뉴가 하나도 없는 가게를 뺀다."""
    kept, gone = _split(state, stores)
    return (stores, "") if not gone else (kept, _gone_text(gone))


def share(state, stores, ctx):
    """후보 가게마다 메뉴 정보를 붙여서 돌려준다 (받은 가게 사전은 바꾸지 않는다).
    before_candidates를 거치지 않고 불려도 1인 메뉴가 없는 가게는 뺀다."""
    kept, gone = _split(state, stores)
    shared, count, only_main = [], 0, []
    for store in kept:
        menus, removed, from_main = menus_of(state, store)
        count += len(menus)
        if from_main:
            only_main.append(store["name"])
        shared.append({**store, **summarize(store, menus, removed, from_main)})
    when = f" ({state['updated']} 기준)" if state.get("updated") else ""
    said = (f"후보 {len(shared)}곳 메뉴 {count}개를 정리했어요{when}. 2인분 메뉴는 빼고, "
            "1인분 메뉴·음식 종류·가격을 모두에게 알려 드릴게요.")
    if gone:
        said += " " + _gone_text(gone)
    if only_main:
        said += f" {josa(', '.join(only_main), '은', '는')} 메뉴 목록이 없어서 대표 메뉴만 알려 드려요."
    return shared, said


def describe(state, store, ctx):
    """③ 표에 쓰는 한 줄: '순대국 외 1개 · 9,000~10,000원 (2인분 1개 뺌)'"""
    menus = store.get("menus") or []
    if not menus:
        return ""
    text = menus[0]["name"] + (f" 외 {len(menus) - 1}개" if len(menus) > 1 else "")
    low, high = store.get("price_min"), store.get("price_max")
    if low is not None:
        text += f" · {low:,}원" if low == high else f" · {low:,}~{high:,}원"
    if store.get("removed_menus"):
        text += f" (2인분 {len(store['removed_menus'])}개 뺌)"
    return text
