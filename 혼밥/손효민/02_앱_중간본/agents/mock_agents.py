"""아직 없는 에이전트를 '있다고 가정'한 임시 에이전트: 혼밥 / 메뉴 / 가격 (+ 거리 대체용).

진짜 에이전트가 아니라, 설명해 주신 역할을 단순한 규칙으로 흉내 낸다.
진짜 파일(solo_agent.py, menu_agent.py, price_agent.py)이 생기면 그쪽이 쓰인다.

  📋 메뉴: 가게 메뉴를 갱신하고, 다른 에이전트에게 메뉴·음식 종류·국물 여부를 공유한다 (점수 없음)
  🪑 혼밥: 1인분 가능한 가게 데이터를 갱신하고, 혼밥일기에 '1인석 있음'이 있는지 확인한다.
           혼밥 MBTI가 구석자리파면 1인석 있는 곳을 더 추천한다
  💰 가격: 메뉴 평균 가격을 보고, 알뜰파면 싼 곳, 맛우선파면 비싼 곳을 선호한다
"""
import types

import app_data
import mbti
from taste import josa

MAX_WALK = 15  # 거리 대체용: 도보 15분(약 1km)보다 멀면 탈락


def _module(name, **parts):
    return types.SimpleNamespace(NAME=name, ASSUMED=True, **parts)


def _undecided(text, sure="높음"):
    return {"stance": "판단 안 함", "확실도": sure, "message": text}


# ───────── 📋 메뉴 ─────────
def menu_prepare(ctx):
    """메뉴 갱신: ctx["menus"](가게 id -> 메뉴 목록)를 최신 메뉴로 본다. 없으면 가게 대표 메뉴 하나."""
    return {"menus": ctx.get("menus") or {}, "updated": ctx.get("menus_updated")}


def menu_share(state, stores, ctx):
    """후보 가게에 메뉴를 붙여서 다른 에이전트에게 돌려준다 (음식 종류, 국물 여부, 메뉴 가격들)."""
    shared, count = [], 0
    for store in stores:
        menus = state["menus"].get(store["id"])
        if not menus:
            menus = [{"name": store.get("menu") or store["name"], "price": store.get("price"),
                      "soup": bool(store.get("soup"))}]
        count += len(menus)
        main = menus[0]
        info = {"menu": main["name"], "soup": any(m.get("soup") for m in menus)}
        info["kind"] = app_data.food_kind({**store, **info})
        info["weather_type"] = app_data.weather_type({**store, **info})
        shared.append({**store, **info, "menus": menus})
    when = f" ({state['updated']} 기준)" if state.get("updated") else ""
    return shared, f"후보 {len(stores)}곳 메뉴 {count}개를 갱신했어요{when}. 음식 종류와 가격을 모두에게 공유할게요."


menu = _module("메뉴", prepare=menu_prepare, opinion=lambda state, ctx: "", share=menu_share)


# ───────── 💰 가격 ─────────
def avg_price(store):
    prices = [m["price"] for m in store.get("menus") or [] if isinstance(m.get("price"), (int, float))]
    if not prices and isinstance(store.get("price"), (int, float)):
        prices = [store["price"]]
    return round(sum(prices) / len(prices)) if prices else None


def price_score(store, code, budget=None):
    """알뜰파: 1만 원 이하 10점 / 1.2만 원 이하 6점 / 그 위 2점
    맛우선파: 1.2만 원 이상 10점 / 1만 원 이상 6점 / 그 아래 4점
    MBTI 없음: 예산이 있으면 예산의 80% 이하 10점 / 그 위 5점, 없으면 1만 원 이하 8점 / 1.2만 원 이하 6점 / 그 위 4점"""
    price = avg_price(store)
    if price is None:
        return None
    if mbti.has(code, "알뜰파"):
        return 10 if price <= 10000 else 6 if price <= 12000 else 2
    if mbti.has(code, "맛우선파"):
        return 10 if price >= 12000 else 6 if price >= 10000 else 4
    if budget:
        return 10 if price <= budget * 0.8 else 5
    return 8 if price <= 10000 else 6 if price <= 12000 else 4


def _price_taste(code):
    return "알뜰파" if mbti.has(code, "알뜰파") else "맛우선파" if mbti.has(code, "맛우선파") else ""


def price_opinion(state, ctx):
    kind = _price_taste(ctx.get("mbti"))
    if kind == "알뜰파":
        return "알뜰파시니 메뉴 평균 1만 원 이하를 우선할게요."
    if kind == "맛우선파":
        return "맛우선파시니 오늘은 메뉴 평균 1.2만 원 이상도 좋게 볼게요."
    return "메뉴 평균 가격으로 볼게요."


def price_check(state, store, ctx):
    budget, price = ctx.get("budget"), avg_price(store)
    if budget and price and price > budget:
        return False, f"메뉴 평균 {price:,}원이라 예산({budget:,}원)을 넘어요"
    return True, ""


def price_rebut(state, sender, proposed, current, ctx):
    code = ctx.get("mbti")
    p, c = price_score(proposed, code, ctx.get("budget")), price_score(current, code, ctx.get("budget"))
    pa, ca = avg_price(proposed), avg_price(current)
    if p is None or c is None:
        return _undecided("가격 정보가 없어서 비교할 수 없어요.", "낮음")
    kind = _price_taste(code)
    prefix = f"{kind}시니 " if kind else ""
    if p == c:
        return _undecided(f"메뉴 평균 {pa:,}원과 {ca:,}원이라 가격으로는 차이가 작아요.")
    if p > c:
        return {"stance": "동의", "확실도": "높음",
                "message": f"{prefix}{proposed['name']}(평균 {pa:,}원)이 {current['name']}(평균 {ca:,}원)보다 맞아요."}
    return {"stance": "반대", "확실도": "높음",
            "message": f"{prefix}{current['name']}(평균 {ca:,}원)이 {proposed['name']}(평균 {pa:,}원)보다 맞아요."}


price = _module(
    "가격", prepare=lambda ctx: {}, opinion=price_opinion, check=price_check,
    describe=lambda state, store, ctx: (f"평균 {avg_price(store):,}원" if avg_price(store) else "가격 모름"),
    score=lambda state, store, ctx: (
        {"score": 5, "확실도": "낮음", "why": "가격 정보가 없어요."} if price_score(store, ctx.get("mbti"), ctx.get("budget")) is None
        else {"score": price_score(store, ctx.get("mbti"), ctx.get("budget")), "확실도": "높음",
              "why": f"메뉴 평균 {avg_price(store):,}원이에요."}),
    rebut=price_rebut)


# ───────── 🪑 혼밥 ─────────
def solo_prepare(ctx):
    """1인분 가능 가게 데이터 갱신(ctx["solo_data"]: 가게 id -> 정보) + 혼밥일기에서 '1인석 있음' 찾기."""
    seen = {}
    for entry in ctx.get("diary") or []:
        if "1인석 있음" in (entry.get("혼밥포인트") or []):
            seen[entry["가게"]] = entry.get("날짜", "")
    return {"data": ctx.get("solo_data") or {}, "diary_seat": seen, "updated": ctx.get("solo_updated")}


def _solo(state, store):
    """가게 하나의 혼밥 정보: 갱신 데이터 > 가게 기본값, 혼밥일기에 1인석 기록이 있으면 1인석 확인"""
    info = {"single_ok": store.get("single_ok"), "seat": store.get("seat"), "seat_text": store.get("seat_text"),
            "old_review": store.get("old_review"), **state["data"].get(store["id"], {})}
    info["diary_seat"] = store["name"] in state["diary_seat"]
    if info["diary_seat"]:
        info["seat"] = True
    return info


def solo_opinion(state, ctx):
    parts = []
    if state["data"]:
        when = f"({state['updated']} 기준)" if state.get("updated") else ""
        parts.append(f"1인분 가능 가게 데이터를 갱신했어요{when}.")
    if state["diary_seat"]:
        parts.append(f"혼밥일기에서 1인석 기록을 찾았어요: {', '.join(state['diary_seat'])}.")
    if mbti.has(ctx.get("mbti"), "구석자리파"):
        parts.append("구석자리파시니 1인석 있는 곳을 더 추천할게요.")
    return " ".join(parts)


def solo_describe(state, store, ctx):
    info = _solo(state, store)
    if info["single_ok"] is False:
        return '"2인분부터" 확인'
    seat = info["seat_text"] or ("1인석" if info["seat"] else None)
    parts = [seat] if seat else []
    if info["single_ok"]:
        parts.append("1인분 확인")
    if info["diary_seat"]:
        parts.append("내 일기에 1인석 기록")
    if not seat:
        parts.append("좌석 알 수 없음")
    return ", ".join(parts)


def solo_score(state, store, ctx):
    """1인석 확인 10점. 확인 안 되면 구석자리파 3점 / 그 외 6점 (구석자리파일수록 1인석 차이를 크게 본다)"""
    info = _solo(state, store)
    if info["seat"]:
        where = "내 혼밥일기에서 1인석을 확인했어요." if info["diary_seat"] else "1인석이 확인됐어요."
        return {"score": 10, "확실도": "높음", "why": where}
    # 혼밥 MBTI 퍼센트가 있으면 구석자리파 정도는 조율자가 비율로 반영하므로 여기서는 감점하지 않는다 (두 번 반영 방지)
    cozy = mbti.has(ctx.get("mbti"), "구석자리파") and not ctx.get("pct")
    return {"score": 3 if cozy else 6, "확실도": "낮음",
            "why": "1인석은 확인하지 못했어요" + (" (구석자리파라 감점)." if cozy else ".")}


def solo_rebut(state, sender, proposed, current, ctx):
    p, c = _solo(state, proposed), _solo(state, current)
    if c.get("old_review") and p["seat"] and c["seat"] and not c["diary_seat"]:
        return {"stance": "판단 안 함", "확실도": "중간",
                "message": f"{current['name']}의 좌석 후기 하나는 {c['old_review']} 글이라 확실도를 '중간'으로 낮출게요.",
                "확실도_낮춤": {"가게": current["name"], "확실도": "중간", "이유": f"좌석 후기가 {c['old_review']} 글"}}
    if p["seat"] == c["seat"]:
        return _undecided("두 곳 다 1인석이 확인돼서 혼밥 편의는 같아요." if p["seat"]
                          else "두 곳 다 1인석을 확인하지 못했어요.", "높음" if p["seat"] else "낮음")
    cozy = " 구석자리파시니 1인석이 중요해요." if mbti.has(ctx.get("mbti"), "구석자리파") else ""
    if p["seat"]:
        return {"stance": "동의", "확실도": "높음", "message": f"{josa(proposed['name'], '은', '는')} 1인석이 있어요.{cozy}"}
    return {"stance": "반대", "확실도": "중간",
            "message": f"{josa(proposed['name'], '은', '는')} 1인석을 확인하지 못했어요.{cozy}"}


solo = _module(
    "혼밥", prepare=solo_prepare, opinion=solo_opinion, describe=solo_describe,
    check=lambda state, store, ctx: (_solo(state, store)["single_ok"] is not False, '"2인분부터" 확인'),
    score=solo_score, rebut=solo_rebut)


# ───────── 🚶 거리 (진짜 거리 에이전트를 못 쓸 때만) ─────────
def _distance_score(store):
    walk = store.get("walk_min")
    return None if walk is None else max(0, min(10, 12 - walk))


def _distance_rebut(state, sender, proposed, current, ctx):
    p, c = proposed.get("walk_min"), current.get("walk_min")
    if p is None or c is None:
        return _undecided("거리 정보가 없어서 비교할 수 없어요.", "낮음")
    if abs(p - c) < 3:
        return _undecided(f"도보 {p}분, {c}분이라 거리 차이는 작아요.")
    if p < c:
        return {"stance": "동의", "확실도": "높음", "message": f"{josa(proposed['name'], '은', '는')} 도보 {p}분이라 더 가까워요."}
    return {"stance": "반대", "확실도": "높음", "message": f"{josa(proposed['name'], '은', '는')} 도보 {p}분이라 더 멀어요."}


distance = _module(
    "거리", prepare=lambda ctx: {}, opinion=lambda state, ctx: "",
    describe=lambda state, store, ctx: f"약 {store.get('walk_min')}분" if store.get("walk_min") else "도보 시간 모름",
    check=lambda state, store, ctx: ((store.get("walk_min") or 0) <= MAX_WALK, f"도보 {store.get('walk_min')}분이라 너무 멀어요"),
    score=lambda state, store, ctx: (
        {"score": 5, "확실도": "낮음", "why": "거리 정보가 없어요."} if _distance_score(store) is None
        else {"score": _distance_score(store), "확실도": "높음", "why": f"도보 {store['walk_min']}분이에요."}),
    rebut=_distance_rebut)

MOCKS = {"혼밥": solo, "메뉴": menu, "가격": price, "거리": distance}
