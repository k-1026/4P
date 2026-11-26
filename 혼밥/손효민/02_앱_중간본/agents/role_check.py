"""거리·날씨·취향 에이전트가 맡은 역할을 제대로 하는지 실제 코드로 하나씩 확인한다.

실행: python role_check.py   (결과를 표로 출력, role_check.json에도 저장)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime

import app_data
import distance_agent
import taste
import weather
import weather_agent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = date(2026, 11, 26)
CHECKS = []


def check(agent, role, how, run):
    """run()은 (통과 여부, 실제로 나온 값)을 돌려준다"""
    try:
        ok, got = run()
    except Exception as error:  # 실패도 결과로 남긴다
        ok, got = False, f"오류: {type(error).__name__} {error}"
    CHECKS.append({"agent": agent, "role": role, "how": how, "ok": bool(ok), "got": got})


# ───────── 🌡️ 날씨 ─────────
check("날씨", "추운 날에는 따뜻한 국물을 추천", "체감 4도",
      lambda: (weather.recommend(4)[0] == "따뜻한 국물", weather.recommend(4)[1]))
check("날씨", "더운 날에는 차가운 음식을 추천", "체감 30도",
      lambda: (weather.recommend(30)[0] == "차가운 요리", weather.recommend(30)[1]))
check("날씨", "날씨에 안 맞는 가게에는 '안 맞아요'", "추운 날 냉면집",
      lambda: (lambda r: (r["fits"] is False, r["message"]))(
          weather.reply({"direction": "따뜻한 국물", "feels_like": 4.0}, "거리", "냉면집", "차가운 요리")))
check("날씨", "반론: 날씨에 더 맞는 쪽을 지지", "국밥집 vs 냉면집 제안",
      lambda: (lambda r: (r["stance"] == "반대", r["message"]))(
          weather.rebut({"direction": "따뜻한 국물", "feels_like": 4.0}, "거리", "냉면집", "차가운 요리",
                        "국밥집", "따뜻한 국물")))
check("날씨", "어제와 비교해서 말하기", "오늘 4도, 어제 10도",
      lambda: (weather.compare(4.0, 10.0, "ASOS") == "어제 같은 시각보다 6.0도 낮아요.",
               weather.compare(4.0, 10.0, "ASOS")))


def live_weather():
    report = weather_agent.prepare({"now": datetime.now()})
    if report is None:
        return False, "기상청 API에서 가져오지 못했어요 (인터넷·API 키 확인)"
    return True, f"{report['time']} 체감 {report['feels_like']}도 → {report['message']}"


check("날씨", "실제 기상청 날씨를 가져오기", "지금 대구", live_weather)

# ───────── 🚶 거리 ─────────
STORES = [{"id": "A", "name": "A 국밥집", "dist_m": int(8 * 70 / 1.3)},
          {"id": "B", "name": "B 라멘집", "dist_m": int(3 * 70 / 1.3)},
          {"id": "F", "name": "F 샤브집", "dist_m": int(6 * 70 / 1.3)}]
state, said = distance_agent.candidates({}, STORES, {})
by = {c["name"]: c for c in state["report"]["candidates"]}
check("거리", "도보 시간 계산", "직선 161m / 430m",
      lambda: (by["B 라멘집"]["walk_min"] == 3 and by["A 국밥집"]["walk_min"] == 8,
               f"B {by['B 라멘집']['walk_label']}, A {by['A 국밥집']['walk_label']}"))
check("거리", "가까울수록 높은 점수", "3분 · 6분 · 8분",
      lambda: (by["B 라멘집"]["distance_score"] > by["F 샤브집"]["distance_score"] > by["A 국밥집"]["distance_score"],
               f"B {by['B 라멘집']['distance_score']}점 > F {by['F 샤브집']['distance_score']}점 > "
               f"A {by['A 국밥집']['distance_score']}점"))
rows = [{"store": {"id": "A", "name": "A 국밥집"}, "total": 8.7},
        {"store": {"id": "B", "name": "B 라멘집"}, "total": 8.45}]
check("거리", "1순위가 멀고 가까운 대안이 있으면 반론", "A 8분(8.7점) vs B 3분(8.45점), 체감 4도",
      lambda: (lambda p: (p is not None and p["proposed"]["name"] == "B 라멘집", p and p["message"]))(
          distance_agent.propose(state, rows, {"temp_c": 4.0})))
check("거리", "1순위가 가까우면 반론하지 않음", "F 6분이 1순위",
      lambda: (lambda p: (p is None, "반론 없음" if p is None else p["message"]))(
          distance_agent.propose(state, [{"store": {"id": "F", "name": "F 샤브집"}, "total": 8.5},
                                         {"store": {"id": "B", "name": "B 라멘집"}, "total": 8.0}], {"temp_c": 4.0})))
check("거리", "다른 에이전트 제안에 동의·반대", "A(8분)를 F(6분) 대신 제안",
      lambda: (lambda r: (r["stance"] == "반대", r["message"]))(
          distance_agent.rebut(state, "취향", STORES[0], STORES[2], {"temp_c": 4.0})))
urgent, _ = distance_agent.candidates({}, STORES, {"hurry": True})
ub = {c["name"]: c for c in urgent["report"]["candidates"]}
check("거리", "'시간이 없어요'면 1분 차이를 더 크게", "보통 vs 급함 (A 8분)",
      lambda: (ub["A 국밥집"]["distance_score"] < by["A 국밥집"]["distance_score"],
               f"보통 {by['A 국밥집']['distance_score']}점 → 급함 {ub['A 국밥집']['distance_score']}점"))


def js_tests():
    done = subprocess.run(["node", "--test", "distance_agent.test.js"], capture_output=True,
                          cwd=os.path.dirname(distance_agent.JS), timeout=120)
    out = done.stdout.decode("utf-8", "replace")
    passed = next((line.split()[-1] for line in out.splitlines() if line.startswith("ℹ pass")), "?")
    failed = next((line.split()[-1] for line in out.splitlines() if line.startswith("ℹ fail")), "?")
    return done.returncode == 0, f"통과 {passed}개, 실패 {failed}개"


check("거리", "거리 에이전트 자체 테스트", "distance_agent.test.js", js_tests)

# ───────── 📒 취향 ─────────
profile = taste.build_profile(taste.load_diary(taste.FOLDER), taste.load_stores(taste.FOLDER), TODAY)
check("취향", f"어제 먹은 음식과 겹치면 감점 (-{taste.REPEAT_PENALTY[1]}점)", "어제 라면 → 오늘 B 라멘집",
      lambda: (taste.score(profile, "B 라멘집", "면")["score"]
               == profile["종류별"]["면"]["평균별점"] * 2 - taste.REPEAT_PENALTY[1],
               taste.reason(profile, "B 라멘집", "면") + f" → {profile['종류별']['면']['평균별점'] * 2:g}점에서 "
               f"-{taste.REPEAT_PENALTY[1]} = {taste.score(profile, 'B 라멘집', '면')['score']:g}점"))
check("취향", "별점·후기로 좋아하는 음식 분석", "일기 9개",
      lambda: (profile["좋아하는종류"][0] == "국밥·탕", taste.opinion(profile).split(". ")[0] + "."))
check("취향", "부정문은 앞뒤 문맥을 보고 판단", "'맛있지 않아요' / '안 짜서 좋았어요'",
      lambda: (taste.analyze_review("맛있지 않아요")["느낌"] == -1 and taste.analyze_review("안 짜서 좋았어요")["느낌"] == 1,
               f"맛있지 않아요 → 나쁨 / 안 짜서 좋았어요 → 좋음"))
check("취향", "판단이 어려우면 별점을 우선", "'맛있지만 좀 짜요' (별점 5)",
      lambda: (taste.analyze_review("맛있지만 좀 짜요")["느낌"] == 0, "섞인 후기 → 후기 보정 0, 별점 그대로"))


def service_split():
    p = taste.build_profile([{"날짜": "2026-11-20 12:00", "가게": "x", "별점": 2,
                              "후기": "맛은 좋았지만 직원이 불친절해요"}], {"x": "면"}, TODAY)
    return (p["종류별"]["면"]["평균별점"] == 4 and p["가게별"]["x"]["평균별점"] == 2,
            f"면 종류 {p['종류별']['면']['평균별점']:g}점(맛 좋음) / 그 가게 {p['가게별']['x']['평균별점']:g}점")


check("취향", "맛과 서비스 불만을 나눠서 봄", "별점 2 + '맛은 좋았지만 직원이 불친절'", service_split)
check("취향", "탐험파면 안 가본 가게 위주", "WBNV: 안 가본 F 샤브집 vs 가본 A 국밥집",
      lambda: (taste.score(profile, "F 샤브집", "찌개", "WBNV")["score"] > taste.score(profile, "F 샤브집", "찌개")["score"]
               and taste.score(profile, "A 국밥집", "국밥·탕", "WBNV")["score"] < taste.score(profile, "A 국밥집", "국밥·탕")["score"],
               f"F {taste.score(profile, 'F 샤브집', '찌개')['score']:g}→{taste.score(profile, 'F 샤브집', '찌개', 'WBNV')['score']:g}점, "
               f"A {taste.score(profile, 'A 국밥집', '국밥·탕')['score']:g}→{taste.score(profile, 'A 국밥집', '국밥·탕', 'WBNV')['score']:g}점"))
check("취향", "단골파면 가봤던 곳의 기록을 씀", "AORP: 가본 삼덕 백반 vs 안 가본 F 샤브집",
      lambda: (taste.score(profile, "삼덕 백반", "밥·덮밥", "AORP")["score"] > taste.score(profile, "삼덕 백반", "밥·덮밥")["score"]
               and taste.score(profile, "F 샤브집", "찌개", "AORP")["score"] < taste.score(profile, "F 샤브집", "찌개")["score"],
               f"삼덕 {taste.score(profile, '삼덕 백반', '밥·덮밥')['score']:g}→{taste.score(profile, '삼덕 백반', '밥·덮밥', 'AORP')['score']:g}점, "
               f"F {taste.score(profile, 'F 샤브집', '찌개')['score']:g}→{taste.score(profile, 'F 샤브집', '찌개', 'AORP')['score']:g}점"))
check("취향", "반박할 때 기록(날짜·별점·후기)을 근거로", "B 라멘집 제안 vs A 국밥집",
      lambda: (lambda r: (r["stance"] == "반대" and "10월 2일" in r["message"] and "별점 5점" in r["message"],
                          r["message"].split(": ", 1)[-1]))(
          taste.rebut(profile, "거리", "B 라멘집", "면", "A 국밥집", "국밥·탕")))


def daily_refresh():
    with tempfile.TemporaryDirectory() as folder:
        for name in (taste.DIARY, taste.STORES):
            shutil.copy(os.path.join(taste.FOLDER, name), folder)
        first = taste.load_profile(folder, TODAY)
        nxt = taste.load_profile(folder, date(2026, 11, 27))
    return (first["만든날"] != nxt["만든날"] and nxt["최근"][0]["며칠전"] == 2,
            f"{first['만든날']} 요약표 → {nxt['만든날']}에 다시 만듦 (라면은 '어제'→'그제')")


check("취향", "매일 혼밥일기를 최신화", "날짜가 바뀌면", daily_refresh)


def from_app():
    export = {"posts": [{"id": "1", "ts": int(datetime(2026, 11, 25, 12).timestamp() * 1000), "rid": 1, "rate": 4,
                         "text": "면이 쫄깃해요", "points": ["🪑 1인석 있음"]}],
              "restaurants": [{"id": 1, "name": "멘야 하나비", "cat": "라멘", "menu": "마제소바"}]}
    with tempfile.TemporaryDirectory() as folder:
        app_data.save(export, folder)
        p = taste.load_profile(folder, TODAY)
    return p["출처"] == "앱 혼밥일기" and p["최근"][0]["종류"] == "면", f"{p['출처']} {p['기록수']}개 → 어제 {p['최근'][0]['가게']}({p['최근'][0]['종류']})"


check("취향", "앱 혼밥일기에서 읽기", "앱이 보낸 일기 1개", from_app)


if __name__ == "__main__":
    for agent in ("날씨", "거리", "취향"):
        items = [c for c in CHECKS if c["agent"] == agent]
        print(f"\n{agent}: {sum(c['ok'] for c in items)}/{len(items)} 통과")
        for c in items:
            print(f"  {'✅' if c['ok'] else '❌'} {c['role']} ({c['how']}) → {c['got']}")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "role_check.json"), "w", encoding="utf-8") as file:
        json.dump(CHECKS, file, ensure_ascii=False, indent=2)
