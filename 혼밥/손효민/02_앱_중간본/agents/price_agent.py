"""💰 가격 에이전트: 후보 가게들의 1인 가격을 서로 비교해 점수를 매기고, 다른 에이전트의 제안에 반론한다.

가격은 가게 정보를 불러올 때 함께 오는 값을 그대로 쓴다 (추측하지 않는다).
기준: 1126proto (prompts/budget.md, criteria.json의 budget). 기준을 바꾸려면 아래 숫자를 고친다.

  1인 가격  메뉴 에이전트가 알려 준 1인 메뉴 가격의 중앙값 (없으면 가게 대표 가격)
            4,000원 미만의 꼬치·접시·초밥류·"3ea" 메뉴는 낱개 값이라 한 끼 가격으로 치지 않는다
  상한      말한 예산 > 가성비파 10,000원 / 플렉스파 없음 / MBTI 없음 13,000원. 넘으면 탈락
            예산을 '상관없음'으로 고르면 아무도 탈락하지 않는다 (싼 곳 점수는 그대로)
  점수      floor(10 × 더 비싼 가게 수 ÷ (n − 1) + 0.5). 가장 싼 곳 10점, 가장 비싼 곳 0점
            가격 확인된 곳이 5곳 미만이면: 상한의 80% 이하 10점 / 그 위 5점
  모름      0점, 확실도 낮음 (탈락 아님)
  플렉스파  예산을 말하지 않았으면 가격으로 가르지 않는다 (가중치 0, 나머지 에이전트가 나눠 가짐)
  반론      점수 차 2점 이하면 "차이는 작다", 3점 이상이면 가격 숫자를 들어 동의/반대

가게 데이터와 이어진 가격 후기(VOC)가 없어서 VOC 보정(±1점)은 넣지 않았다.
"""
import math
import re
import statistics
from datetime import datetime

import mbti
from taste import josa

NAME = "가격"
CAP_VALUE = 10000      # 가성비파
CAP_UNKNOWN = 13000    # MBTI 없음
MIN_COMPARE = 5        # 이보다 적으면 상대 비교를 하지 않는다
CLEAR_GAP = 3          # 이 점수 차부터 동의/반대
STALE_DAYS = 365       # 이보다 오래 전에 확인한 가격은 확실도 중간
PIECE_UNDER = 4000     # 이보다 싸고 이름이 낱개 꼴이면 한 끼 가격이 아니다
PIECE_NAME = re.compile(r"꼬치|접시|초밥류|군함류|\d\s*ea", re.IGNORECASE)


def _round(x):
    return math.floor(x + 0.5)


def is_piece(name, price):
    """꼬치 1개·접시 1장처럼 낱개로 파는 값인가"""
    return price < PIECE_UNDER and bool(PIECE_NAME.search(str(name or "")))


def person_price(store):
    """가게의 1인 가격: 1인 메뉴 가격들의 중앙값, 목록에 가격이 없으면 대표 가격, 그것도 없으면 None"""
    prices = [m["price"] for m in store.get("menus") or []
              if isinstance(m.get("price"), (int, float)) and not is_piece(m.get("name"), m["price"])]
    own = store.get("price")
    if not prices and isinstance(own, (int, float)) and not is_piece(store.get("menu"), own):
        prices = [own]
    return _round(statistics.median(prices)) if prices else None


def cap_of(ctx):
    """상한 (원). 플렉스파가 예산을 말하지 않았으면 None"""
    if ctx.get("budget"):
        return ctx["budget"]
    code = ctx.get("mbti")
    if mbti.has(code, "플렉스파"):
        return None
    return CAP_VALUE if mbti.has(code, "가성비파") else CAP_UNKNOWN


def _won(value):
    if value % 10000 == 0:
        return f"{value // 10000:,}만 원"
    return f"{value:,}원"


def _fresh(store, ctx):
    """가격을 확인한 날이 12개월 안인가. 날짜가 없으면 False"""
    try:
        seen = datetime.strptime(str(store.get("seen"))[:10], "%Y-%m-%d")
    except ValueError:
        return False
    return (ctx.get("now", datetime.now()) - seen).days <= STALE_DAYS


def _sure(store, ctx):
    return "높음" if _fresh(store, ctx) else "중간"


def prepare(ctx):
    return {"prices": []}  # 후보가 정해지면 candidates()에서 채운다


def opinion(state, ctx):
    if ctx.get("budget_any"):
        return "예산은 상관없다고 하셔서 가격으로 탈락시키지 않고 비교만 할게요."
    if ctx.get("budget"):
        return f"말씀하신 {_won(ctx['budget'])} 안에서 1인 가격을 비교해 볼게요."
    if mbti.has(ctx.get("mbti"), "가성비파"):
        return f"가성비파시니 {_won(CAP_VALUE)} 이하를 우선할게요."
    if mbti.has(ctx.get("mbti"), "플렉스파"):
        return "플렉스파시니 오늘은 가격으로 가게를 가르지 않을게요."
    return "1인 가격을 후보끼리 비교해 볼게요."


def weightless(state, ctx):
    """True면 조율자가 이 에이전트의 가중치를 빼고 나머지에 나눠 준다 (예산 변별력 없음)"""
    return cap_of(ctx) is None


def candidates(state, stores, ctx):
    """후보 전체의 1인 가격을 모은다. 상대 점수는 이 목록 안에서 정한다."""
    prices = [v for v in map(person_price, stores) if v is not None]
    said = ""
    if prices:
        said = f"후보 {len(prices)}곳의 1인 가격은 {min(prices):,}~{max(prices):,}원이에요."
        if len(prices) < len(stores):
            said += f" {len(stores) - len(prices)}곳은 가격을 몰라요."
    return {**state, "prices": prices}, said


def describe(state, store, ctx):
    price = person_price(store)
    return "가격 모름" if price is None else f"{price:,}원"


def check(state, store, ctx):
    cap, price = cap_of(ctx), person_price(store)
    if not ctx.get("budget_any") and cap is not None and price is not None and price > cap:
        return False, f"1인 {price:,}원이라 상한({cap:,}원)을 넘어요"
    return True, ""


def points(state, store, ctx):
    """0~10 정수. 가격을 모르면 None"""
    price, cap, prices = person_price(store), cap_of(ctx), state.get("prices") or []
    if price is None:
        return None
    if cap is None:
        return 10
    if len(prices) < MIN_COMPARE:
        return 10 if price <= cap * 0.8 else 5
    return _round(10 * sum(p > price for p in prices) / (len(prices) - 1))


def score(state, store, ctx):
    got = points(state, store, ctx)
    if got is None:
        why = ("낱개·접시 가격만 있어서 한 끼 가격을 알 수 없어요." if isinstance(store.get("price"), (int, float))
               else "가격 정보가 없어요.")
        return {"score": 0, "확실도": "낮음", "why": why}
    price, prices = person_price(store), state.get("prices") or []
    why = f"1인 {price:,}원이에요."
    if len(prices) >= MIN_COMPARE and cap_of(ctx) is not None:
        higher = sum(p > price for p in prices)
        why = (f"1인 {price:,}원으로 후보 중 가장 비싼 편이에요." if higher == 0
               else f"1인 {price:,}원, 후보 {len(prices)}곳 중 {higher}곳이 더 비싸요.")
    return {"score": got, "확실도": _sure(store, ctx), "why": why}


def _undecided(message, sure="높음"):
    return {"stance": "판단 안 함", "확실도": sure, "message": message}


def rebut(state, sender, proposed, current, ctx):
    """sender 에이전트가 current(지금 1순위) 대신 proposed를 밀 때, 가격으로만 판단해서 답한다."""
    if cap_of(ctx) is None:
        return _undecided("플렉스파시라 가격으로는 의견을 내지 않을게요.")
    theirs, mine = points(state, proposed, ctx), points(state, current, ctx)
    if theirs is None or mine is None:
        return _undecided("가격을 모르는 곳이 있어서 비교할 수 없어요.", "낮음")
    new, old, cap = person_price(proposed), person_price(current), cap_of(ctx)
    if abs(theirs - mine) < CLEAR_GAP:
        if new == old:
            return _undecided(f"둘 다 {new:,}원이라 가격 차이는 없어요.")
        within = f"둘 다 {_won(cap)} 이내라 " if not ctx.get("budget_any") and max(new, old) <= cap else ""
        return _undecided(f"{within}가격 차이는 작아요 ({new:,}원, {old:,}원).")
    agree = theirs > mine
    if agree:
        text = (f"{sender} 의견에 동의해요. {josa(proposed['name'], '은', '는')} {new:,}원으로 "
                f"{current['name']}({old:,}원)보다 {old - new:,}원 싸요.")
    else:
        text = (f"{sender} 의견에는 반대예요. {josa(proposed['name'], '은', '는')} {new:,}원으로 "
                f"{current['name']}({old:,}원)보다 {new - old:,}원 비싸요.")
    answer = {"stance": "동의" if agree else "반대", "확실도": "높음", "message": text}
    stale = [s for s in (proposed, current) if s.get("seen") and not _fresh(s, ctx)]
    if stale:  # 반론은 점수를 바꾸지 않고, 내 정보의 확실도만 낮춘다
        answer["확실도"] = "중간"
        answer["확실도_낮춤"] = {"가게": stale[0]["name"], "확실도": "중간",
                            "이유": f"가격을 확인한 날이 {str(stale[0]['seen'])[:10]}"}
    return answer


def propose(state, rows, ctx):
    """1순위보다 가격 점수가 3점 이상 높은 가게가 있으면 먼저 이의를 낸다."""
    if cap_of(ctx) is None or len(rows) < 2:
        return None
    top = rows[0]["store"]
    mine = points(state, top, ctx)
    rated = [(points(state, row["store"], ctx), row["store"]) for row in rows[1:]]
    rated = [(got, store) for got, store in rated if got is not None]
    if mine is None or not rated:
        return None
    got, best = max(rated, key=lambda pair: pair[0])
    if got - mine < CLEAR_GAP:
        return None
    new, old = person_price(best), person_price(top)
    return {"proposed": best, "current": top,
            "message": f"1순위 {josa(top['name'], '은', '는')} {old:,}원이에요. "
                       f"{josa(best['name'], '은', '는')} {new:,}원으로 {old - new:,}원 싼데, 이쪽은 어떨까요?"}
