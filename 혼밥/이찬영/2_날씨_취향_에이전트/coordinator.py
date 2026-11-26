"""🧭 조율자: 대화의 중심. 에이전트에게 차례로 말을 시키고, 점수를 최종으로 내고, 사용자에게 결과를 알려 준다.

흐름 (예시 ①~⑥과 같음)
  ① 날씨·취향 등 첫 의견         ② 1km 안 후보 5곳 + 메뉴 공유 + 도보 시간
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

# (이름, 파일 이름, 가중치 %) — 메뉴는 점수 없이 정보만 공유해서 0%
PLAN = (("혼밥", "solo_agent", 35), ("거리", "distance_agent", 20), ("가격", "price_agent", 20),
        ("취향", "taste_agent", 15), ("날씨", "weather_agent", 10), ("메뉴", "menu_agent", 0))
EMOJI = {"혼밥": "🪑", "거리": "🚶", "가격": "💰", "취향": "📒", "날씨": "🌡️", "메뉴": "📋", "조율자": "🧭"}
RADIUS_M = 1000      # 후보는 1km 안
CANDIDATES = 5       # 후보 수
CLOSE_GAP = 0.5      # 1·2위 점수 차이가 이보다 작으면 "바뀔 수 있어요"


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


# 혼밥 MBTI 퍼센트로 비율 바꾸기: 기본 비율 x (0.5 + 퍼센트). 50%면 그대로, 100%면 1.5배, 0%면 0.5배
# (3·4번째 글자 탐험파/단골파·가성비파/플렉스파는 취향·가격 에이전트가 점수 안에서 반영한다)
MBTI_TIMES = {"날씨": lambda pct: 0.5 + pct["W"],     # 날씨파일수록 날씨를 크게
              "취향": lambda pct: 1.5 - pct["W"],     # 입맛파일수록 취향을 크게
              "혼밥": lambda pct: 0.5 + pct["B"]}     # 아늑파일수록 1인석(혼밥 편의)을 크게


def mbti_times(name, pct):
    return MBTI_TIMES[name](pct) if pct and name in MBTI_TIMES else 1


def weights_for(agents, hurry, pct=None):
    """점수를 내는 에이전트끼리 가중치를 100으로 다시 나눈다.
    순서: 혼밥 MBTI 퍼센트(pct)로 곱하기 -> 시간이 없으면 거리 2배 -> 합이 100이 되게 나누기."""
    raw = {a["name"]: a["weight"] * mbti_times(a["name"], pct) * (2 if hurry and a["name"] == "거리" else 1)
           for a in agents if a["weight"] > 0 and hasattr(a.get("module"), "score")}
    total = sum(raw.values())
    return {name: value * 100 / total for name, value in raw.items()} if total else {}


def precheck(ctx, missing=(), assumed=(), failed=()):
    """조율자가 시작하기 전에 부족한 것을 찾는다. [{"what": 무엇이, "then": 그래서 이번엔}]"""
    lacking = []
    if not mbti.parse(ctx.get("mbti")):
        lacking.append({"what": "혼밥 MBTI가 없어요 (앱에서 혼밥 MBTI 테스트를 하면 돼요)",
                        "then": "기본 비율로 계산하고 MBTI 보정은 하지 않아요"})
    else:
        _, problem = mbti.parse_pct(ctx["mbti"], ctx.get("mbti_pct"))
        if problem == "퍼센트 없음":
            lacking.append({"what": "혼밥 MBTI 퍼센트가 없어요 (앱에서 '지금 보내기'를 다시 누르거나 직접 정해 주세요)",
                            "then": "비율은 기본값(35·20·20·15·10)으로 계산해요"})
        elif problem:
            lacking.append({"what": f"혼밥 MBTI 퍼센트가 이상해요: {problem}", "then": "비율은 기본값으로 계산해요"})
    if missing:
        lacking.append({"what": f"아직 없는 에이전트: {', '.join(missing)}", "then": "있는 에이전트끼리 비율을 나눠 계산해요"})
    if assumed:
        lacking.append({"what": f"가정 에이전트로 대신함: {', '.join(assumed)}", "then": "단순한 규칙으로 흉내 낸 점수예요"})
    if failed:
        lacking.append({"what": f"준비하지 못한 에이전트: {', '.join(failed)}", "then": "이번 계산에서 빼요"})
    return lacking


def pick_candidates(stores, area=0, radius=RADIUS_M, count=CANDIDATES):
    """같은 동네, 1km 안에서 앱 평점이 높은 순으로 후보를 고른다 (평점이 같으면 가까운 곳)."""
    near = [s for s in stores if s.get("area", 0) == area
            and (s.get("dist_m") is None or s["dist_m"] <= radius)]
    near.sort(key=lambda s: (-(s.get("rate") or 0), s.get("dist_m") or 0))
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
    elif isinstance(store.get("price"), (int, float)):
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
    if ctx["pct"]:
        say("조율자", f"혼밥 MBTI 퍼센트는 {mbti.pct_label(ctx['pct'])}예요. 이 퍼센트로 비율을 정할게요.")
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
    candidates = pick_candidates(stores, ctx["area"])
    if not candidates:
        return end("1km 안에 후보가 없어요.", failed=failed)
    say("조율자", f"1km 안에서 후보 {len(candidates)}곳을 골랐어요: {', '.join(s['name'] for s in candidates)}."
                 + (" 메뉴 에이전트, 메뉴를 공유해 주세요." if any(hasattr(a["module"], "share") for a in ready) else ""))
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
    weights = weights_for(ready, ctx["hurry"], ctx["pct"])
    base = weights_for(ready, ctx["hurry"])
    scorers = [a for a in ready if a["name"] in weights]
    rows = []
    for store in survivors:
        scores = {a["name"]: a["module"].score(a["state"], store, ctx) for a in scorers}
        total = sum(scores[name]["score"] * weights[name] / 100 for name in scores)
        rows.append({"store": store, "scores": scores, "total": round(total, 2)})
    rows.sort(key=lambda row: -row["total"])
    say("조율자", "점수를 합쳐 볼게요. 가중치 " + " · ".join(f"{n} {w:.0f}%" for n, w in weights.items()) + "."
                 + (" (기본 " + " · ".join(f"{n} {w:.0f}%" for n, w in base.items()) + "에서 혼밥 MBTI 퍼센트로 바꿨어요.)"
                    if ctx["pct"] else ""))
    for row in rows:
        detail = " · ".join(f"{n} {s['score']:g}" for n, s in row["scores"].items())
        lines.append(f"{row['store']['name']}: {row['total']:g}점  ({detail})")

    # ⑤ 반론 1회: propose()가 있는 에이전트는 자기 규칙으로, 없는 에이전트는 자기 점수가 1순위보다
    #    높은 가게가 있으면 제안한다. 비중이 큰 에이전트부터, 처음 나온 제안 하나만.
    section("⑤ 상의 (반론 1회)")
    top = rows[0]
    say("조율자", f"지금 1순위는 {top['store']['name']}, {top['total']:g}점이에요. 이견 있나요?")
    debate, proposal = [], None
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
    if proposal:
        a, proposed, current = proposal["agent"], proposal["proposed"], proposal["current"]
        debate.append({"agent": a["name"], "stance": "제안", "message": proposal["message"]})
        say(a["name"], proposal["message"], "제안")
        for other in ready:
            if other is a or not hasattr(other["module"], "rebut"):
                continue
            answer = other["module"].rebut(other["state"], a["name"], proposed, current, ctx)
            debate.append({"agent": other["name"], **answer})
            say(other["name"], answer["message"], answer["stance"])
            change = answer.get("확실도_낮춤")  # 예: {"가게": "A 국밥집", "확실도": "중간"} — 점수는 그대로
            if change:
                for row in rows:
                    if row["store"]["name"] == change["가게"] and other["name"] in row["scores"]:
                        row["scores"][other["name"]]["확실도"] = change["확실도"]
                        row.setdefault("낮아진확실도", []).append((other["name"], change))
        votes = [d["stance"] for d in debate[1:]]
        say("조율자", f"동의 {votes.count('동의')} · 반대 {votes.count('반대')} · 판단 안 함 {votes.count('판단 안 함')}. "
                     "반론은 점수를 바꾸지 않고, 최종 답의 설명과 확실도에 반영할게요.")
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
        for name, change in row.get("낮아진확실도", []):
            notes.append(f"상의에서 {name} 정보의 확실도가 '{change['확실도']}'으로 낮아졌어요"
                         f"{' (' + change['이유'] + ')' if change.get('이유') else ''}.")
        low = [name for name, s in row["scores"].items() if s.get("확실도") == "낮음"]
        if low:
            notes.append(f"확실도 낮음: {', '.join(low)} 정보가 부족해요.")
        head = f"{place}순위: {label(row['store'], walk, price)} - {row['total']:g}점"
        lines.append(head)
        lines += [f"  {note}" for note in notes]
        final.append({"place": place, "head": head, "notes": notes})

    extra = []
    if dropped:
        extra.append(f"{josa(', '.join(store['name'] for store, _ in dropped), '은', '는')} 점수와 상관없이 탈락 조건으로 빠졌어요.")
    lowered = [f"{row['store']['name']}의 {name} 확실도가 '{change['확실도']}'"
               for row in rows for name, change in row.get("낮아진확실도", [])]
    if lowered:
        extra.append(f"반론에서 점수는 그대로였고, {', '.join(lowered)}으로 낮아져 최종 답에 반영했어요.")
    if len(rows) > 1 and rows[0]["total"] - rows[1]["total"] < CLOSE_GAP:
        extra.append(f"1·2위 점수 차이가 {rows[0]['total'] - rows[1]['total']:.2f}점이라, 조건이 바뀌면 순위가 바뀔 수 있어요.")
    if not ctx["hurry"] and "거리" in weights and len(rows) > 1:
        urgent = weights_for(ready, True, ctx["pct"])
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
