"""혼밥 MBTI로 점수를 모으는 시뮬레이션: 같은 날·같은 가게, MBTI가 다른 두 사람.

점수를 모으는 에이전트는 5개: 🪑 혼밥 · 🚶 거리 · 💰 가격 · 📒 취향 · 🌡️ 날씨 (📋 메뉴는 정보만 공유)

MBTI는 한 번만 반영한다.
  - 날씨파/입맛파(1번째)·구석자리파/아무자리파(2번째) 퍼센트 -> 조율자가 비율(가중치)을 바꾼다
        비율을 서로 주고받아서 합은 늘 100 (퍼센트가 50%에서 멀어진 만큼 x 10점을 옮긴다)
          1번째: 날씨 <-> 취향 끼리 주고받음   2번째: 혼밥 <-> 거리·가격(반씩) 끼리 주고받음
  - 탐험파/단골파(3번째)·알뜰파/맛우선파(4번째) 글자 -> 취향·가격 에이전트가 점수 안에서 보정
        취향 에이전트 설계(taste.py)와 같은 방식: 기본 점수 - 감점 + MBTI 보정

실행: python mbti_percent_demo.py
"""
import sys

import coordinator
import mock_agents
import scenario_demo as demo
import taste
import weather

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = {"혼밥": 35, "거리": 20, "가격": 20, "취향": 15, "날씨": 10}
EMOJI = {"혼밥": "🪑", "거리": "🚶", "가격": "💰", "취향": "📒", "날씨": "🌡️", "메뉴": "📋"}
# 앱 혼밥 MBTI 결과: 축마다 8문제 중 앞쪽 글자(W·B·N·V)를 고른 비율
PEOPLE = {
    "WBNV": {"W": 6 / 8, "B": 7 / 8, "N": 5 / 8, "V": 6 / 8},   # 날씨파·구석자리파·탐험파·알뜰파
    "AORP": {"W": 2 / 8, "B": 3 / 8, "N": 2 / 8, "V": 3 / 8},   # 입맛파·아무자리파·단골파·맛우선파
}
STATUS = [  # (에이전트, 파일, 상태, 이번 시뮬레이션에서 쓴 것)
    ("🌡️ 날씨", "weather.py", "완성", "실제 규칙. 날씨 값만 '체감 2.5도, 어제보다 4도 낮음'으로 넣음"),
    ("📒 취향", "taste.py", "완성", "실제 규칙 + 샘플 혼밥일기 (국밥 좋아함, 어제 라면)"),
    ("🚶 거리", "../distance_agent.js", "완성", "실제 규칙 (내 위치는 아직 시험값)"),
    ("🪑 혼밥", "mock_agents.py", "가정", "1인석·1인분 데이터를 있다고 가정"),
    ("💰 가격", "mock_agents.py", "가정", "메뉴 평균 가격 규칙을 가정"),
    ("📋 메뉴", "mock_agents.py", "가정", "메뉴를 공유만 함 (점수 없음)"),
    ("🧭 조율자", "coordinator.py", "완성", "MBTI 퍼센트 비율은 이 시뮬레이션에만 있음 (아직 조율자에 안 넣음)"),
]


def p(x):
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%"


MOVE = 10  # 퍼센트가 50%에서 100%(또는 0%)까지 가면 최대 5점을 옮긴다


def mbti_weights(pct):
    """옮기는 점수: 1번째 축 (날씨파% - 50%) x 10 은 취향 -> 날씨,
    2번째 축 (구석자리파% - 50%) x 10 은 거리·가격(반씩) -> 혼밥. 주고받기만 해서 합은 늘 100."""
    w1 = (pct["W"] - 0.5) * MOVE
    w2 = (pct["B"] - 0.5) * MOVE
    change = {"혼밥": w2, "거리": -w2 / 2, "가격": -w2 / 2, "취향": -w1, "날씨": w1}
    w = {n: BASE[n] + change[n] for n in BASE}
    return change, w


# ── 에이전트마다 "기본 → 감점/보정 → 점수"를 글로 풀어 준다 ──
def taste_steps(profile, store, code):
    """taste.score()와 같은 계산을 단계별로 보여 준다."""
    name, kind = store["name"], store["kind"]
    shop, kinds = profile["가게별"].get(name), profile["종류별"].get(kind)
    if shop:
        base, src = shop["평균별점"] * 2, f"이 가게 별점 {shop['평균별점']:g} x 2"
    elif kinds and kind != "기타":
        base, src = kinds["평균별점"] * 2, f"{kind} 평균 별점 {kinds['평균별점']:g} x 2 (안 가본 곳)"
    else:
        base, src = 5, "기록 없음"
    days = taste._repeat(profile, kind)
    minus = taste.REPEAT_PENALTY.get(days, 0)
    bonus, why = taste.mbti_bonus(profile, name, code)
    result = taste.score(profile, name, kind, code)
    text = f"{src} = {base:g}"
    if minus:
        text += f" - {minus} ({taste.REPEAT_WORDS[days]} {kind})"
    if bonus:
        text += f" {'+' if bonus > 0 else '-'} {abs(bonus)} ({why})"
    if result["score"] != base - minus + bonus:
        text += f" -> 0~10 안으로 맞춰 {result['score']:g}"
    return result["score"], text


def price_steps(store, code):
    price = mock_agents.avg_price(store)
    score = mock_agents.price_score(store, code)
    if mock_agents.mbti.has(code, "알뜰파"):
        rule = "알뜰파: 1만 원 이하 10 / 1.2만 원 이하 6 / 그 위 2"
    else:
        rule = "맛우선파: 1.2만 원 이상 10 / 1만 원 이상 6 / 그 아래 4"
    return score, f"평균 {price:,}원 -> {rule}"


def weather_steps(report, store):
    return weather.score(report, store["weather_type"])["score"], f"체감 {report['feels_like']}도 x {store['weather_type']}"


def solo_steps(state, store):
    info = mock_agents._solo(state, store)
    if info["seat"]:
        return 10, f"1인석 확인 ({mock_agents.solo_describe(state, store, {})}) -> 10"
    return 6, "1인석 확인 못 함 -> 6 (구석자리파 정도는 비율에서 반영)"


def run_person(code, pct):
    diary, agents = demo.agents_for(demo.COLD)
    module = {a["name"]: a["module"] for a in agents}
    ctx = {"now": demo.TODAY, "hurry": False, "budget": None, "mbti": code, "diary": diary,
           "menus": demo.MENUS, "solo_data": demo.SOLO, "temp_c": demo.COLD["feels_like"]}
    state = {n: m.prepare(ctx) for n, m in module.items()}
    stores = coordinator.pick_candidates([dict(s) for s in demo.STORES])
    stores, _ = module["메뉴"].share(state["메뉴"], stores, ctx)
    state["거리"], _ = module["거리"].candidates(state["거리"], stores, ctx)
    words = " · ".join(f"{name} {p(v if first else 1 - v)}" for (first, name), v in
                       zip([(code[0] == "W", "날씨파" if code[0] == "W" else "입맛파"),
                            (code[1] == "B", "구석자리파" if code[1] == "B" else "아무자리파"),
                            (code[2] == "N", "탐험파" if code[2] == "N" else "단골파"),
                            (code[3] == "V", "알뜰파" if code[3] == "V" else "맛우선파")], pct.values()))
    print(f"\n████████ 혼밥 MBTI {code}  ({words}) ████████")

    # ① 비율
    change, w = mbti_weights(pct)
    w1, w2 = change["날씨"], change["혼밥"]
    print("\n① 비율 정하기: 서로 주고받기만 해서 합은 늘 100")
    print(f"  1번째 축: (날씨파 {p(pct['W'])} - 50%) x 10 = {w1:+.2f}점  -> 날씨 {w1:+.2f}, 취향 {-w1:+.2f}")
    print(f"  2번째 축: (구석자리파 {p(pct['B'])} - 50%) x 10 = {w2:+.2f}점  -> 혼밥 {w2:+.2f}, 거리·가격 각 {-w2 / 2:+.3f}")
    print(f"  {'':8}{'기본':>5}{'옮김':>9}{'최종 비율':>10}")
    for n in BASE:
        print(f"  {EMOJI[n]} {n:4}{BASE[n]:>6}{change[n]:>+10.3f}{w[n]:>10.3f}%")
    print(f"  {'합':6}{sum(BASE.values()):>7}{sum(change.values()):>+10.3f}{sum(w.values()):>10.3f}%")

    # ② 탈락
    print("\n② 탈락 확인 (점수 전에 빠짐)")
    alive = []
    for store in stores:
        out = [f"{n}: {r}" for n in ("혼밥", "거리", "가격") for ok, r in [module[n].check(state[n], store, ctx)] if not ok]
        print(f"  {store['name']}: " + ("탈락 (" + " / ".join(out) + ")" if out else "통과"))
        alive += [] if out else [store]

    # ③ 점수
    print("\n③ 에이전트별 점수 (0~10): 기본 -> 감점/보정 -> 점수")
    rows = []
    for store in alive:
        steps = {
            "혼밥": solo_steps(state["혼밥"], store),
            "거리": (module["거리"].score(state["거리"], store, ctx)["score"],
                     next(c["score_reason"] for c in state["거리"]["report"]["candidates"] if c["id"] == str(store["id"]))),
            "가격": price_steps(store, code),
            "취향": taste_steps(state["취향"], store, code),
            "날씨": weather_steps(state["날씨"], store),
        }
        total_score = sum(steps[n][0] * w[n] / 100 for n in BASE)
        rows.append({"store": store, "steps": steps, "total": total_score})
        print(f"\n  [{store['name']}] {store['menu']} · {store['kind']} · {store['weather_type']}")
        for n in BASE:
            print(f"    {EMOJI[n]} {n} {steps[n][0]:>4g}점  {steps[n][1]}")

    # ④ 합계
    rows.sort(key=lambda r: -r["total"])
    print("\n④ 합계 = 점수 x 비율을 모두 더하기")
    print(f"  {'가게':10}" + "".join(f"{EMOJI[n]}{n}{w[n]:>6.2f}%  " for n in BASE) + "  합계")
    for r in rows:
        cells = "".join(f"{r['steps'][n][0]:>4g} -> {r['steps'][n][0] * w[n] / 100:<5.2f} " for n in BASE)
        print(f"  {r['store']['name']:10}{cells}  {r['total']:.2f}점")
    print("\n  최종: " + " / ".join(f"{i}순위 {r['store']['name']} {r['total']:.2f}점" for i, r in enumerate(rows[:3], 1)))
    return rows


def main():
    print("상황: 체감 2.5도 (어제보다 4도 낮음) · 샘플 혼밥일기: 국밥 좋아함, 어제 동성로 라멘")
    print("\n━━ 에이전트 완성 여부")
    for agent, file, status, used in STATUS:
        print(f"  {agent:7} {'✅' if status == '완성' else '🟡'} {status}  {file:22} {used}")
    results = {code: run_person(code, pct) for code, pct in PEOPLE.items()}
    print("\n━━ 두 사람 비교")
    for code, rows in results.items():
        print(f"  {code}: " + " > ".join(f"{r['store']['name']}({r['total']:.2f})" for r in rows))
    return results


if __name__ == "__main__":
    main()
