"""🧭 조율자: 대화의 중심. 에이전트에게 차례로 말을 시키고, 점수를 최종으로 내고, 사용자에게 결과를 알려 준다.

흐름 (예시 ①~⑥과 같음)
  ① 날씨·취향 등 첫 의견         ② 1km 안 후보 20곳 + 메뉴 공유 + 도보 시간
  ③ 탈락 조건 (혼밥·거리·가격)   ④ 1차 점수 (가중치)
  ⑤ 반론 1회                     ⑥ 최종 답
아직 만들지 않은 에이전트는 빼고 계산하거나(기본), 가정 에이전트로 채운다(assume_missing=True).
새 에이전트는 agent_template.py를 복사해 아래 파일 이름으로 만들면 자동으로 들어온다.
"""
import importlib
from datetime import datetime

import app_data
import mbti
from taste import josa

# (이름, 파일 이름, 점수를 내면 0보다 큰 값) — 실제 가중치는 아래 weights_for가 정한다. 메뉴는 점수 없이 정보만 공유해서 0
PLAN = (("혼밥", "solo_agent", 35), ("거리", "distance_agent", 20), ("가격", "price_agent", 20),
        ("취향", "taste_agent", 15), ("날씨", "weather_agent", 10), ("메뉴", "menu_agent", 0))
EMOJI = {"혼밥": "🪑", "거리": "🚶", "가격": "💰", "취향": "📒", "날씨": "🌡️", "메뉴": "📋", "조율자": "🧭"}
RADIUS_M = 1000      # 후보는 1km 안
CANDIDATES = 20      # 후보 수
CLOSE_GAP = 0.5      # 1·2위 점수 차이가 이보다 작으면 "바뀔 수 있어요"
OBJECT_RANKS = 10    # 아무도 제안하지 않으면 2~10순위 안에서 반론할 가게를 찾는다


def load_agents(plan=PLAN, importer=importlib.import_module):
    """있는 에이전트는 불러오고, 없는 것은 missing에 이름만 남긴다."""
    agents, missing = [], []
    for name, module_name, weight in plan:
        try:
            module = importer(module_name)
        except ModuleNotFoundError as error:
            if error.name != module_name:  # 파일은 있는데 그 안에서 다른 것을 못 찾음 -> 진짜 오류
                raise
            missing.append(name)
            continue
        agents.append({"name": name, "module": module, "weight": weight})
    return agents, missing


# 가중치는 총합 10: 거리 2점은 고정, 나머지 8점을 혼밥 MBTI 퍼센트에 비례해서 나눈다.
#   날씨 = 날씨파 %, 혼밥 = 아늑파 %           (입맛파·당당파일수록 작아진다)
#   취향 = 탐험파·단골파 중 센 쪽 %, 가격 = 가성비파·플렉스파 중 센 쪽 %
# 퍼센트가 없으면 네 항목을 똑같이 나눈다. 안에서는 합 100(%)으로 계산하고 화면에만 10점으로 적는다.
DISTANCE_POINTS = 2
TOTAL_POINTS = 10
MBTI_SHARE = {"날씨": lambda pct: pct["W"], "혼밥": lambda pct: pct["B"],
              "취향": lambda pct: max(pct["N"], 1 - pct["N"]), "가격": lambda pct: max(pct["V"], 1 - pct["V"])}


# 사용자가 네 가지의 중요 순위를 정하면 MBTI 퍼센트 대신 순위로 8점을 나눈다
RANK_SHARE = (40, 30, 20, 10)                                  # 1위 ~ 4위 (%)
AXIS_AGENT = {"W": "날씨", "B": "혼밥", "N": "취향", "V": "가격"}


def rank_label(order):
    return " · ".join(f"{i}위 {AXIS_AGENT[x]}({share}%)" for i, (x, share) in enumerate(zip(order, RANK_SHARE), 1))


def weights_for(agents, hurry, pct=None, order=None):
    """점수를 내는 에이전트의 가중치 (합 100). 빠진 에이전트의 몫은 남은 MBTI 항목이 나눠 갖는다.
    시간이 없으면 거리를 2배로 한 뒤 다시 합을 맞춘다."""
    names = [a["name"] for a in agents
             if a["weight"] > 0 and hasattr(a.get("module"), "score") and not a.get("weightless")]
    others = [n for n in names if n != "거리"]
    ranked = {AXIS_AGENT[x]: share for x, share in zip(order or [], RANK_SHARE)}
    shares = {n: ranked.get(n, 1) if ranked else MBTI_SHARE[n](pct) if pct and n in MBTI_SHARE else 1
              for n in others}
    if not sum(shares.values()):
        shares = {n: 1 for n in others}
    rest, whole = TOTAL_POINTS - (DISTANCE_POINTS if "거리" in names else 0), sum(shares.values())
    raw = {n: DISTANCE_POINTS * (2 if hurry else 1) if n == "거리" else rest * shares[n] / whole for n in names}
    total = sum(raw.values())
    return {n: v * 100 / total for n, v in raw.items()} if total else {}


def points_label(weights):
    """{"거리": 20.0, ...} -> '거리 2.0 · ...' (총합 10)"""
    return " · ".join(f"{n} {w * TOTAL_POINTS / 100:.1f}" for n, w in weights.items())


def precheck(ctx, missing=(), assumed=(), failed=()):
    """조율자가 시작하기 전에 부족한 것을 찾는다. [{"what": 무엇이, "then": 그래서 이번엔}]"""
    lacking = []
    if mbti.parse_order(ctx.get("order")):
        pass  # 순위를 정했으면 퍼센트가 없어도 가중치를 정할 수 있다
    elif not mbti.parse(ctx.get("mbti")):
        lacking.append({"what": "혼밥 MBTI가 없어요 (앱에서 혼밥 MBTI 테스트를 하면 돼요)",
                        "then": "거리 2점, 나머지는 똑같이 나누고 MBTI 보정은 하지 않아요"})
    else:
        _, problem = mbti.parse_pct(ctx["mbti"], ctx.get("mbti_pct"))
        if problem == "퍼센트 없음":
            lacking.append({"what": "혼밥 MBTI 퍼센트가 없어요 (앱에서 '지금 보내기'를 다시 누르거나 직접 정해 주세요)",
                            "then": "거리 2점, 나머지 8점은 네 항목이 똑같이 나눠요"})
        elif problem:
            lacking.append({"what": f"혼밥 MBTI 퍼센트가 이상해요: {problem}", "then": "거리 2점, 나머지 8점은 네 항목이 똑같이 나눠요"})
    if missing:
        lacking.append({"what": f"아직 없는 에이전트: {', '.join(missing)}", "then": "있는 에이전트끼리 비율을 나눠 계산해요"})
    if assumed:
        lacking.append({"what": f"가정 에이전트로 대신함: {', '.join(assumed)}", "then": "단순한 규칙으로 흉내 낸 점수예요"})
    if failed:
        lacking.append({"what": f"준비하지 못한 에이전트: {', '.join(failed)}", "then": "이번 계산에서 빼요"})
    return lacking


def pick_candidates(stores, area=0, radius=RADIUS_M, count=CANDIDATES):
    """같은 동네, 1km 안에서 가까운 순으로 후보를 고른다 (거리가 같으면 평점 높은 곳).
    음식 종류를 골랐으면 stores에는 그 종류만 들어 있어서 '그 종류 중 가까운 20곳'이 된다."""
    near = [s for s in stores if s.get("area", 0) == area
            and (s.get("dist_m") is None or s["dist_m"] <= radius)]
    near.sort(key=lambda s: (s.get("dist_m") is None, s.get("dist_m") or 0, -(s.get("rate") or 0)))
    return near[:count]


def label(store, walk=None, price=None):
    """가게 이름 (도보 시간, 가격). walk·price는 거리·가격 에이전트가 말한 값 (없으면 앱 값)"""
    parts = []
    if walk and "모름" not in walk:
        parts.append(f"도보 {walk}")
    elif store.get("walk_min") is not None:
        parts.append(f"도보 {store['walk_min']}분")
    if price and "모름" not in price:
        parts.append(price)
    elif not price and isinstance(store.get("price"), (int, float)):  # 가격 에이전트가 모른다고 하면 안 적는다
        parts.append(f"{store['price']:,}원")
    return f"{store['name']} ({', '.join(parts)})" if parts else store["name"]


def fill_assumed(agents, missing, plan=PLAN):
    """없는 에이전트를 mock_agents의 가정 에이전트로 채운다 (PLAN 순서 유지)."""
    import mock_agents
    have = {a["name"]: a for a in agents}
    filled, assumed = [], []
    for name, _, weight in plan:
        if name in have:
            filled.append(have[name])
        elif name in missing and name in mock_agents.MOCKS:
            filled.append({"name": name, "module": mock_agents.MOCKS[name], "weight": weight})
            assumed.append(name)
    return filled, [name for name in missing if name not in assumed], assumed


def objection(scorers, rows, weights):
    """제안이 하나도 없을 때의 반론: 2~10순위 가게가 1순위보다 나은 항목 중, 총점에 가장 크게 작용하는 것.
    1순위가 모든 항목에서 앞서면 None (억지로 만들지 않는다)."""
    top, best = rows[0], None
    for a in scorers:
        name = a["name"]
        for row in rows[1:OBJECT_RANKS]:
            gain = (row["scores"][name]["score"] - top["scores"][name]["score"]) * weights[name]
            if gain > 0 and (best is None or gain > best[0]):
                best = (gain, a, row)
    if best is None:
        return None
    _, a, row = best
    name = a["name"]
    mine, theirs = row["scores"][name], top["scores"][name]["score"]
    message = (f"저는 반론할게요. {name} 점수는 {row['store']['name']}({mine['score']:g}점)이 "
               f"1순위 {top['store']['name']}({theirs:g}점)보다 높아요. {mine.get('why', '')}").strip()
    return {"agent": a, "proposed": row["store"], "current": top["store"], "message": message}


def raised_scores(rows, proposal, weights):
    """'점수를 높일게요'를 골랐을 때의 점수: 반론 가게에 1순위보다 낮은 점수를 준 에이전트가 1순위만큼 올린다.
    rows는 바꾸지 않는다. (올린 점수 {에이전트: (전, 후)}, 새 총점)"""
    top = next(row for row in rows if row["store"] is proposal["current"])
    pick = next(row for row in rows if row["store"] is proposal["proposed"])
    changed = {n: (pick["scores"][n]["score"], top["scores"][n]["score"]) for n in weights
               if pick["scores"][n]["score"] < top["scores"][n]["score"]}
    total = sum((changed[n][1] if n in changed else s["score"]) * weights[n] / 100 for n, s in pick["scores"].items())
    return changed, round(total, 2)


def ask_user(rows, proposal, answers, weights, say):
    """에이전트는 정하지 않는다. 반론한 에이전트가 사용자에게 장점을 말하고, 다른 에이전트는 그대로 두자고
    설득한 뒤, 반론 가게의 점수를 높일지 사용자에게 묻는다. (사용자에게 보여 줄 질문, 말한 목록)"""
    top = next(row for row in rows if row["store"] is proposal["current"])
    pick = next(row for row in rows if row["store"] is proposal["proposed"])
    old_name, new_name = top["store"]["name"], pick["store"]["name"]
    names = {n for n in weights if n in pick["scores"] and n in top["scores"]}
    gap = {n: pick["scores"][n]["score"] - top["scores"][n]["score"] for n in names}
    said_by = dict(answers)
    challenger = proposal["agent"]["name"]
    backers = sorted((n for n in names if gap[n] > 0 and said_by.get(n) != "반대" and n != challenger),
                     key=lambda n: (said_by.get(n) != "동의", -gap[n] * weights[n]))
    defenders = sorted((n for n in names if gap[n] < 0 and n != challenger),
                       key=lambda n: (said_by.get(n) != "반대", gap[n] * weights[n]))[:2]
    talk = []

    def speak(name, text, stance):
        talk.append({"agent": name, "stance": stance, "message": text})
        say(name, text, stance)

    def compare(n):
        return f"{n} 점수가 {new_name} {pick['scores'][n]['score']:g}점, {old_name} {top['scores'][n]['score']:g}점"

    say("조율자", f"{challenger} 에이전트가 반론했어요. 양쪽 이야기를 듣고 직접 정해 주세요.")
    for n in [challenger] + backers[:1]:
        better = f"{compare(n)}이라 이 부분에서 더 나아요." if gap.get(n, 0) > 0 else proposal["message"]
        speak(n, f"사용자님, 저는 {josa(new_name, '이', '가')} 더 좋다고 생각해요. {better} "
                 f"{pick['scores'].get(n, {}).get('why', '') if gap.get(n, 0) > 0 else ''}".strip(), "반론")
    for n in defenders:
        speak(n, f"사용자님, 저는 그대로 가는 게 좋다고 생각해요. 총점이 {old_name} {top['total']:g}점, "
                 f"{new_name} {pick['total']:g}점으로 나왔고, {compare(n)}이거든요. "
                 f"{top['scores'][n].get('why', '')}".strip(), "설득")
    changed, total = raised_scores(rows, proposal, weights)
    detail = ", ".join(f"{n} {a:g}→{b:g}점" for n, (a, b) in changed.items())
    say("조율자", f"{new_name}의 점수를 높일까요? 높이면 {detail}으로 올라 총점이 {pick['total']:g}점에서 {total:g}점이 돼요.")
    return {"question": f"{new_name}의 점수를 높일까요?", "store": new_name, "current": old_name,
            "options": [
                {"value": f"raise:{new_name}", "label": "네, 점수를 높일게요",
                 "detail": f"{new_name} {pick['total']:g}점 → {total:g}점, 1순위가 돼요"},
                {"value": f"keep:{new_name}", "label": "아니요, 그대로 둘게요",
                 "detail": f"1순위 {old_name} {top['total']:g}점 유지"}]}, talk


def apply_raise(rows, proposal, weights):
    """사용자가 높이기를 골랐을 때만 점수를 바꾼다. 바뀐 내용을 글 목록으로 돌려준다."""
    changed, total = raised_scores(rows, proposal, weights)
    pick = next(row for row in rows if row["store"] is proposal["proposed"])
    for n, (_, new) in changed.items():
        pick["scores"][n] = {**pick["scores"][n], "score": new, "why": "직접 고르셔서 점수를 높였어요."}
    pick["total"] = total
    return [f"{n} {a:g}→{b:g}점" for n, (a, b) in changed.items()]


def who(name, assumed):
    return f"{name}(가정)" if name in assumed else name


def run(ctx=None, stores=None, agents=None, missing=None, assume_missing=False, assumed=None):
    """조율자 실행. 결과(dict)와 사람이 읽는 글(result['text']), 대화 기록(result['log'])을 돌려준다.
    assume_missing=True면 없는 에이전트를 '있다고 가정'한 임시 에이전트로 채운다."""
    ctx = {"now": datetime.now(), "hurry": False, "budget": None, "area": 0, "mbti": None, **(ctx or {})}
    if agents is None:
        agents, missing = load_agents()
    missing = list(missing or [])
    assumed = list(assumed or [])
    if assume_missing:
        agents, missing, more = fill_assumed(agents, missing)
        assumed += more
    if stores is None:
        data = app_data.load()
        if data is None:
            text = "앱 데이터가 없어요. 혼밥 앱 '마이' 탭에서 '지금 보내기'를 눌러 주세요."
            return {"ok": False, "text": text, "log": []}
        stores = app_data.stores(data)
        ctx.setdefault("diary", app_data.diary(data))
        ctx["mbti"] = ctx["mbti"] or data.get("mbti")
        if ctx.get("mbti_pct") is None and ctx["mbti"] == data.get("mbti"):
            ctx["mbti_pct"] = data.get("mbti_pct")
    ctx["pct"], _ = mbti.parse_pct(ctx["mbti"], ctx.get("mbti_pct")) if mbti.parse(ctx["mbti"]) else (None, "")

    ctx["order"] = mbti.parse_order(ctx.get("order"))
    lines, log = [], []
    step = {"now": ""}

    def section(title):
        step["now"] = title
        lines.append(("\n" if lines else "") + title)

    def say(agent, text, stance=None):
        tag = f"[{stance}] " if stance and stance != "제안" else ""
        lines.append(f"{EMOJI.get(agent, '🤖')} {who(agent, assumed)}: {tag}{text}")
        log.append({"step": step["now"], "agent": agent, "assumed": agent in assumed,
                    "stance": stance, "text": text})

    def end(text, **extra):
        say("조율자", text)
        return {"ok": False, "text": "\n".join(lines), "log": log, "missing": missing, **extra}

    # ① 준비와 첫 의견 (준비에 실패한 에이전트는 이번 계산에서 뺀다)
    ready, failed = [], []
    for agent in agents:
        try:
            state = agent["module"].prepare(ctx)
        except Exception:
            state = None
        if state is None:
            failed.append(agent["name"])
        else:
            ready.append({**agent, "state": state})
    for a in ready:  # 이번엔 점수로 가를 수 없다고 하는 에이전트 (가격: 플렉스파) -> 가중치를 나머지에 나눈다
        weightless = getattr(a["module"], "weightless", None)
        a["weightless"] = bool(weightless and weightless(a["state"], ctx))
    for a in ready:  # 날씨의 체감온도는 다른 에이전트도 쓴다 (거리: "4도인데 …")
        if a["name"] == "날씨" and isinstance(a["state"], dict):
            ctx["temp_c"] = a["state"].get("feels_like")

    section("① 에이전트 의견")
    names = [a["name"] for a in ready]
    who_line = (f"혼밥 MBTI는 {mbti.label(ctx['mbti'])}예요" if mbti.parse(ctx["mbti"])
                else "혼밥 MBTI는 아직 없어요")
    say("조율자", f"오늘 점심을 같이 정해 볼게요. {who_line}"
                 + (", 시간이 없으시대요" if ctx["hurry"] else "") + f". 참여: {', '.join(names) or '없음'}. "
                 "날씨와 취향부터 들어볼게요.")
    lacking = precheck(ctx, missing, assumed, failed)
    if ctx["order"]:
        say("조율자", f"정해 주신 중요 순위는 {rank_label(ctx['order'])}예요. 이 순위로 가중치를 정할게요.")
    elif ctx["pct"]:
        say("조율자", f"혼밥 MBTI 퍼센트는 {mbti.pct_label(ctx['pct'])}예요. 이 퍼센트로 가중치를 정할게요.")
    if lacking:
        say("조율자", "시작 전에 부족한 게 있어요. " + " ".join(f"{i}) {x['what']} → {x['then']}."
                                                     for i, x in enumerate(lacking, 1)))
    else:
        say("조율자", "부족한 것 없이 모두 준비됐어요.")
    if not ready:
        return end("준비된 에이전트가 없어서 추천할 수 없어요.", failed=failed, lacking=lacking)
    for a in sorted(ready, key=lambda a: {"날씨": 0, "취향": 1}.get(a["name"], 2)):
        said = a["module"].opinion(a["state"], ctx)
        if said:
            say(a["name"], said)

    # ② 후보 → 메뉴 공유(share) → 후보를 받아 준비하는 에이전트(candidates: 거리는 도보 시간을 잰다)
    section("② 후보 선정")
    for a in ready:  # 후보를 고르기 전에 가게를 빼는 에이전트 (메뉴: 1인 메뉴가 없는 2인분 가게)
        screen = getattr(a["module"], "before_candidates", None)
        if screen:
            stores, said = screen(a["state"], stores, ctx)
            if said:
                say(a["name"], said)
    wanted = f"{ctx['category']} 가게 중에서 " if ctx.get("category") else ""
    finder = "거리" if any(a["name"] == "거리" for a in ready) else "조율자"  # 후보를 찾았다고 말하는 에이전트
    if finder == "거리":
        say("조율자", f"거리 에이전트, 1km 안 {wanted}가까운 가게를 찾아 주세요.")
    candidates = pick_candidates(stores, ctx["area"])
    if not candidates:
        return end(f"1km 안에 {ctx['category'] + ' ' if ctx.get('category') else ''}후보가 없어요.", failed=failed)
    if ctx.get("category") and len(candidates) < CANDIDATES:
        say(finder, f"1km 안에서 찾은 {ctx['category']} 가게가 {len(candidates)}곳뿐이라 있는 곳만 볼게요.")
    say(finder, f"1km 안 {wanted}가까운 후보 {len(candidates)}곳을 찾아봤어요: {', '.join(s['name'] for s in candidates)}.")
    if any(hasattr(a["module"], "share") for a in ready):
        say("조율자", "메뉴 에이전트, 메뉴를 공유해 주세요.")
    for a in ready:
        share = getattr(a["module"], "share", None)
        if share:
            candidates, said = share(a["state"], candidates, ctx)
            if said:
                say(a["name"], said)
    for a in ready:
        hook = getattr(a["module"], "candidates", None)
        if hook:
            a["state"], said = hook(a["state"], candidates, ctx)
            if said:
                say(a["name"], said)

    # ③ 탈락 조건 (가게마다 각 에이전트가 확인한 내용을 한 줄로)
    checkers = [a for a in ready if hasattr(a["module"], "check")]
    section("③ " + (" + ".join(a["name"] for a in checkers) or "탈락") + " 확인")
    say("조율자", (f"{', '.join(a['name'] for a in checkers)} 에이전트, 탈락 조건을 확인해 주세요."
                  if checkers else "탈락 조건을 보는 에이전트가 아직 없어요."))
    survivors, dropped, table = [], [], []
    for store in candidates:
        reasons, facts = [], {}
        for a in ready:
            describe = getattr(a["module"], "describe", None)
            if describe:
                facts[a["name"]] = describe(a["state"], store, ctx)
            check = getattr(a["module"], "check", None)
            if check:
                ok, why = check(a["state"], store, ctx)
                if not ok:
                    reasons.append(f"{a['name']}: {why}")
        (dropped if reasons else survivors).append((store, reasons))
        table.append({"store": store["name"], "facts": facts, "dropped": reasons})
        shown = " · ".join(f"{EMOJI.get(n, '')} {f}" for n, f in facts.items())
        result = "탈락 (" + " / ".join(reasons) + ")" if reasons else "통과"
        lines.append(f"{store['name']}: {shown} → {result}" if shown else f"{store['name']} → {result}")
    survivors = [store for store, _ in survivors]
    if not survivors:
        return end("모든 후보가 탈락했어요.", failed=failed, table=table)

    # ④ 1차 점수
    section("④ 1차 점수")
    weights = weights_for(ready, ctx["hurry"], ctx["pct"], ctx["order"])
    base = weights_for(ready, ctx["hurry"])  # MBTI 퍼센트가 없을 때의 값
    scorers = [a for a in ready if a["name"] in weights]
    rows = []
    for store in survivors:
        scores = {a["name"]: a["module"].score(a["state"], store, ctx) for a in scorers}
        total = sum(scores[name]["score"] * weights[name] / 100 for name in scores)
        rows.append({"store": store, "scores": scores, "total": round(total, 2)})
    rows.sort(key=lambda row: -row["total"])
    say("조율자", f"점수를 합쳐 볼게요. 가중치(총합 {TOTAL_POINTS}) {points_label(weights)}."
                 + (f" 거리는 정해 둔 몫이고, 나머지는 {'정해 주신 순위' if ctx['order'] else '혼밥 MBTI 퍼센트'}대로 나눴어요."
                    if (ctx["order"] or ctx["pct"]) and "거리" in weights else ""))
    for row in rows:
        detail = " · ".join(f"{n} {s['score']:g}" for n, s in row["scores"].items())
        lines.append(f"{row['store']['name']}: {row['total']:g}점  ({detail})")

    # ⑤ 반론 1회: propose()가 있는 에이전트는 자기 규칙으로, 없는 에이전트는 자기 점수가 1순위보다
    #    높은 가게가 있으면 제안한다. 비중이 큰 에이전트부터, 처음 나온 제안 하나만.
    section("⑤ 상의 (반론 1회)")
    top = rows[0]
    say("조율자", f"지금 1순위는 {top['store']['name']}, {top['total']:g}점이에요. 이견 있나요?")
    debate, proposal, together, choice, chosen = [], None, [], None, None
    if len(rows) > 1:
        for a in sorted(scorers, key=lambda a: -weights[a["name"]]):
            propose = getattr(a["module"], "propose", None)
            if propose:
                offer = propose(a["state"], rows, ctx)
                if offer:
                    proposal = {"agent": a, **offer}
            else:
                best = max(rows, key=lambda row: (row["scores"][a["name"]]["score"], row is top))
                mine, theirs = best["scores"][a["name"]]["score"], top["scores"][a["name"]]["score"]
                if best is not top and mine > theirs:
                    proposal = {"agent": a, "proposed": best["store"], "current": top["store"],
                                "message": f"{a['name']} 기준으로는 {best['store']['name']}({mine:g}점) 쪽이 "
                                           f"{top['store']['name']}({theirs:g}점)보다 나아요."}
            if proposal:
                break
        if not proposal:
            proposal = objection(scorers, rows, weights)
    if proposal:
        a, proposed, current = proposal["agent"], proposal["proposed"], proposal["current"]
        debate.append({"agent": a["name"], "stance": "제안", "message": proposal["message"]})
        say(a["name"], proposal["message"], "제안")
        for other in ready:
            if other is a or not hasattr(other["module"], "rebut"):
                continue
            join = getattr(other["module"], "join", None)  # 함께 반론하는 에이전트 (혼밥)
            joined = join(other["state"], rows, proposal, ctx) if join else None
            if joined and joined["proposed"] is proposed:      # 같은 곳을 밀면 그 말이 곧 대답
                answer = {k: v for k, v in joined.items() if k != "proposed"}
                joined = None
            else:
                answer = other["module"].rebut(other["state"], a["name"], proposed, current, ctx)
            debate.append({"agent": other["name"], **answer})
            say(other["name"], answer["message"], answer["stance"])
            if joined:                                         # 다른 곳을 들면 이어서 같이 반론
                together.append((other["name"], joined["proposed"]))
                debate.append({"agent": other["name"], "stance": joined["stance"], "message": joined["message"]})
                say(other["name"], joined["message"], joined["stance"])
            change = answer.get("확실도_낮춤")  # 예: {"가게": "A 국밥집", "확실도": "중간"} — 점수는 그대로
            if change:
                for row in rows:
                    if row["store"]["name"] == change["가게"] and other["name"] in row["scores"]:
                        row["scores"][other["name"]]["확실도"] = change["확실도"]
                        row.setdefault("낮아진확실도", []).append((other["name"], change))
        votes = [d["stance"] for d in debate[1:]]
        say("조율자", f"동의 {votes.count('동의')} · 반대 {votes.count('반대')} · 판단 안 함 {votes.count('판단 안 함')}.")
        choice, _ = ask_user(rows, proposal, [(d["agent"], d["stance"]) for d in debate[1:]], weights, say)
        # 사용자의 답: 'raise:가게' 또는 'keep:가게'. 지금 묻는 가게에 대한 답일 때만 반영한다
        if ctx.get("choice") in [o["value"] for o in choice["options"]]:
            chosen = ctx["choice"].split(":", 1)[0]
            if chosen == "raise":
                raised = apply_raise(rows, proposal, weights)
                rows.sort(key=lambda row: (row["store"] is not proposal["proposed"], -row["total"]))
                say("조율자", f"고르신 대로 {choice['store']}의 점수를 높였어요: {', '.join(raised)}. "
                             f"{josa(choice['store'], '이', '가')} 1순위예요.")
            else:
                say("조율자", f"고르신 대로 점수는 그대로 둘게요. 1순위는 {josa(choice['current'], '이에요', '예요')}.")
    else:
        say("조율자", "이견이 없어서 반론 없이 넘어갈게요.")

    # ⑥ 최종 답
    section("⑥ 최종 추천")
    walker = next((a for a in ready if a["name"] == "거리" and hasattr(a["module"], "describe")), None)
    pricer = next((a for a in ready if a["name"] == "가격" and hasattr(a["module"], "describe")), None)
    final = []
    for place, row in enumerate(rows[:3], 1):
        walk = walker["module"].describe(walker["state"], row["store"], ctx) if walker else None
        price = pricer["module"].describe(pricer["state"], row["store"], ctx) if pricer else None
        notes = []
        best_factors = sorted(row["scores"].items(), key=lambda kv: -kv[1]["score"] * weights[kv[0]])
        whys = [s["why"] for _, s in best_factors[:2] if s.get("why")]
        if whys:
            notes.append(" ".join(whys))
        weak = [s for _, s in best_factors[2:] if s["score"] <= 3 and s.get("why")]
        if weak:
            notes.append(f"다만 {weak[-1]['why']}")
        if proposal and row["store"] is proposal["proposed"]:
            notes.append(f"{proposal['agent']['name']} 에이전트가 1순위 대신 민 곳이에요.")
        for name, pushed in together:
            if row["store"] is pushed:
                notes.append(f"{name} 에이전트도 함께 반론하며 민 곳이에요.")
        for name, change in row.get("낮아진확실도", []):
            notes.append(f"상의에서 {name} 정보의 확실도가 '{change['확실도']}'으로 낮아졌어요"
                         f"{' (' + change['이유'] + ')' if change.get('이유') else ''}.")
        low = [name for name, s in row["scores"].items() if s.get("확실도") == "낮음"]
        if low:
            notes.append(f"확실도 낮음: {', '.join(low)} 정보가 부족해요.")
        if chosen == "raise" and place == 1:
            notes.insert(0, "직접 점수를 높이신 곳이에요.")
        head = f"{place}순위: {label(row['store'], walk, price)} - {row['total']:g}점"
        lines.append(head)
        lines += [f"  {note}" for note in notes]
        final.append({"place": place, "head": head, "notes": notes})

    extra = []
    if chosen == "raise":
        extra.append(f"{choice['store']}의 점수는 직접 높이기로 고르신 것이 반영된 값이에요.")
    elif chosen == "keep":
        extra.append(f"{choice['store']}의 점수는 고르신 대로 그대로 두었어요.")
    if dropped:
        extra.append(f"{josa(', '.join(store['name'] for store, _ in dropped), '은', '는')} 점수와 상관없이 탈락 조건으로 빠졌어요.")
    lowered = [f"{row['store']['name']}의 {name} 확실도가 '{change['확실도']}'"
               for row in rows for name, change in row.get("낮아진확실도", [])]
    if lowered:
        extra.append(f"상의에서 {', '.join(lowered)}으로 낮아져 최종 답에 반영했어요.")
    if chosen != "raise" and len(rows) > 1 and rows[0]["total"] - rows[1]["total"] < CLOSE_GAP:
        extra.append(f"1·2위 점수 차이가 {rows[0]['total'] - rows[1]['total']:.2f}점이라, 조건이 바뀌면 순위가 바뀔 수 있어요.")
    if chosen != "raise" and not ctx["hurry"] and "거리" in weights and len(rows) > 1:
        urgent = weights_for(ready, True, ctx["pct"], ctx["order"])
        again = max(rows, key=lambda row: sum(row["scores"][n]["score"] * urgent[n] / 100 for n in urgent))
        if again is not rows[0]:
            extra.append(f"\"시간이 없어요\"라고 하면 거리 비중이 올라가서 {josa(again['store']['name'], '이', '가')} 1순위가 돼요.")
    if assumed:
        extra.append(f"'(가정)'이 붙은 {', '.join(assumed)} 에이전트는 진짜가 아니라, 설명한 역할을 단순한 규칙으로 흉내 낸 임시 에이전트예요.")
    if missing:
        extra.append(f"아직 없는 에이전트: {', '.join(missing)} (있는 에이전트끼리 비율을 나눠 계산했어요)")
    if failed:
        extra.append(f"이번에 준비하지 못한 에이전트: {', '.join(failed)} (빼고 계산했어요)")
    say("조율자", f"오늘은 {josa(rows[0]['store']['name'], '을', '를')} 추천해요."
                 + (f" 2순위는 {josa(rows[1]['store']['name'], '이에요', '예요')}." if len(rows) > 1 else ""))
    if extra:
        lines.append("\n참고")
        lines += [f"· {note}" for note in extra]
    return {"ok": True, "text": "\n".join(lines), "log": log, "ranking": rows, "dropped": dropped,
            "choice": choice, "chosen": chosen,
            "table": table, "debate": debate, "weights": weights, "missing": missing, "failed": failed,
            "assumed": assumed, "final": final, "notes": extra, "mbti": ctx["mbti"], "pct": ctx["pct"],
            "base_weights": base, "lacking": lacking}


if __name__ == "__main__":
    import sys
    # python coordinator.py 가정  -> 없는 에이전트를 가정해서 채움 / 급함 -> 시간이 없어요
    # python coordinator.py 50 75 60 70 -> 혼밥 MBTI 퍼센트(날씨파·아늑파·탐험파·가성비파 쪽 %)를 직접 정함
    numbers = [float(a) for a in sys.argv[1:] if a.replace(".", "", 1).isdigit()]
    ctx = {"hurry": "급함" in sys.argv, **({"mbti_pct": numbers} if numbers else {})}
    print(run(ctx, assume_missing="가정" in sys.argv)["text"])
