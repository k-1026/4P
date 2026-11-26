"""앱 데이터 읽기와 조율자 흐름 시험 (가짜 에이전트와 가짜 가게로)."""
import json
import os
import tempfile
import types
import unittest
from datetime import datetime

import app
import app_data
import coordinator
import taste

NOW = datetime(2026, 11, 26, 12, 0)


def ts(text):
    return int(datetime.strptime(text, "%Y-%m-%d %H:%M").timestamp() * 1000)


EXPORT = {
    "version": 1, "nick": "혼밥러", "areas": ["역삼"],
    "restaurants": [
        {"id": 1, "area": 0, "name": "A 국밥집", "cat": "국밥", "rate": 4.5, "dist": 530, "price": 9000,
         "menu": "순대국 정식", "soup": True, "seat": True},
        {"id": 2, "area": 0, "name": "B 라멘집", "cat": "라멘", "rate": 4.6, "dist": 200, "price": 9500,
         "menu": "돈코츠 라멘", "soup": True, "seat": True},
        {"id": 3, "area": 0, "name": "C 찌개집", "cat": "한식", "rate": 4.4, "dist": 400, "price": 9000,
         "menu": "김치찌개", "soup": True, "seat": False},
        {"id": 4, "area": 0, "name": "D 돈까스집", "cat": "돈까스", "rate": 4.3, "dist": 330, "price": 8000,
         "menu": "로스카츠", "soup": False},
        {"id": 5, "area": 0, "name": "먼 냉면집", "cat": "국수", "rate": 4.9, "dist": 1500, "price": 9000,
         "menu": "물냉면", "soup": False},
        {"id": 6, "area": 1, "name": "다른 동네", "cat": "국밥", "rate": 5.0, "dist": 100, "menu": "곰탕"}],
    "posts": [
        {"id": "a", "ts": ts("2026-10-02 12:30"), "rid": 1, "rate": 5, "text": "국물이 진하고 좋았어요",
         "points": ["🍚 양 넉넉"]},
        {"id": "b", "ts": ts("2026-11-25 12:20"), "rid": 2, "rate": 4, "text": "면이 쫄깃해요",
         "points": ["⚡ 빨리 나옴"]},
        {"id": "c", "ts": ts("2026-11-20 12:00"), "rid": 999, "rate": 3, "text": "없어진 가게"}]}


class AppDataTest(unittest.TestCase):
    def test_kinds(self):
        stores = {s["name"]: s for s in app_data.stores(app_data.validate(EXPORT))}
        self.assertEqual(stores["A 국밥집"]["kind"], "국밥·탕")
        self.assertEqual(stores["C 찌개집"]["kind"], "찌개")      # 분류는 한식이지만 메뉴가 찌개
        self.assertEqual(stores["D 돈까스집"]["kind"], "튀김·까스")
        self.assertEqual(stores["먼 냉면집"]["weather_type"], "차가운 요리")
        self.assertEqual(stores["A 국밥집"]["weather_type"], "따뜻한 국물")
        self.assertEqual(stores["A 국밥집"]["walk_min"], 8)          # 530m / 분당 67m

    def test_diary(self):
        entries = app_data.diary(app_data.validate(EXPORT))
        self.assertEqual(entries[0], {"날짜": "2026-10-02 12:30", "가게": "A 국밥집", "별점": 5,
                                      "혼밥포인트": ["양 넉넉"], "후기": "국물이 진하고 좋았어요"})
        self.assertEqual(entries[2]["가게"], "")  # 가게를 못 찾으면 이름이 비어서 '읽지 못한 일기'

    def test_bad_shape(self):
        for bad in (None, [], {"posts": []}, {"posts": "x", "restaurants": []}):
            with self.assertRaises(ValueError):
                app_data.validate(bad)

    def test_taste_reads_app_data(self):
        with tempfile.TemporaryDirectory() as folder:
            app_data.save(EXPORT, folder)
            profile = taste.load_profile(folder, NOW.date())
            self.assertEqual(profile["출처"], "앱 혼밥일기")
            self.assertEqual((profile["기록수"], profile["읽지못한일기"]), (2, 1))
            self.assertIn("어제 B 라멘집에서 면을 드셨어요", taste.opinion(profile))

    def test_origin(self):
        for origin in (None, "null", "http://localhost:8010", "http://127.0.0.1:5500"):
            self.assertTrue(app.app_origin_ok(origin), origin)
        for origin in ("https://evil.example", "http://localhost.evil.com", "http://localhost:80/x"):
            self.assertFalse(app.app_origin_ok(origin), origin)


def fake(name, scores, check=None, fail=False, stance="동의"):
    module = types.SimpleNamespace(
        prepare=lambda ctx: None if fail else {},
        opinion=lambda state, ctx: f"{name} 의견",
        score=lambda state, store, ctx: {"score": scores.get(store["name"], 5), "확실도": "높음",
                                         "why": f"{name} 이유"},
        rebut=lambda state, sender, proposed, current, ctx: {"stance": stance, "확실도": "높음",
                                                             "message": f"{proposed['name']} 생각"})
    if check:
        module.check = check
    return module


class CoordinatorTest(unittest.TestCase):
    def setUp(self):
        self.stores = app_data.stores(app_data.validate(EXPORT))

    def test_missing_agents(self):
        def importer(name):
            if name in ("taste_agent", "weather_agent", "distance_agent"):
                return types.SimpleNamespace()
            raise ModuleNotFoundError(name=name)
        agents, missing = coordinator.load_agents(importer=importer)
        self.assertEqual([a["name"] for a in agents], ["거리", "취향", "날씨"])
        self.assertEqual(missing, ["혼밥", "가격", "메뉴"])

    def test_weights(self):
        module = fake("x", {})
        agents = [{"name": "거리", "weight": 20, "module": module}, {"name": "취향", "weight": 15, "module": module},
                  {"name": "날씨", "weight": 10, "module": module},
                  {"name": "메뉴", "weight": 0, "module": types.SimpleNamespace()}]  # 메뉴는 점수 없음
        w = coordinator.weights_for(agents, hurry=False)
        self.assertAlmostEqual(sum(w.values()), 100)
        self.assertNotIn("메뉴", w)
        self.assertAlmostEqual(w["취향"], 15 * 100 / 45)
        self.assertGreater(coordinator.weights_for(agents, hurry=True)["거리"], w["거리"])

    def test_candidates(self):
        names = [s["name"] for s in coordinator.pick_candidates(self.stores)]
        self.assertNotIn("먼 냉면집", names)   # 1km 밖
        self.assertNotIn("다른 동네", names)   # 다른 동네
        self.assertEqual(names[0], "B 라멘집")  # 평점 순

    def test_full_flow(self):
        seat = lambda state, store, ctx: (bool(store.get("seat")), "1인석 확인 안 됨")
        agents = [
            {"name": "혼밥", "weight": 35, "module": fake("혼밥", {}, check=seat)},
            {"name": "거리", "weight": 20, "module": fake("거리", {"B 라멘집": 10, "A 국밥집": 5})},
            {"name": "취향", "weight": 15, "module": fake("취향", {"A 국밥집": 10, "B 라멘집": 2}, stance="반대")},
            {"name": "날씨", "weight": 10, "module": fake("날씨", {}, fail=True)}]
        result = coordinator.run({"now": NOW}, self.stores, agents, ["가격"])
        self.assertTrue(result["ok"])
        self.assertEqual({s["name"] for s, _ in result["dropped"]}, {"C 찌개집", "D 돈까스집"})
        self.assertEqual(result["failed"], ["날씨"])
        self.assertNotIn("날씨", result["weights"])
        self.assertEqual(result["ranking"][0]["store"]["name"], "A 국밥집")
        self.assertEqual(result["debate"][0]["agent"], "거리")  # 거리가 B를 제안
        self.assertEqual([d["agent"] for d in result["debate"][1:]], ["혼밥", "취향"])
        steps = [entry["step"] for entry in result["log"] if entry["agent"] == "조율자"]
        self.assertEqual(len(set(steps)), 6)  # 조율자가 ①~⑥ 모든 단계에서 말한다
        for part in ("① 에이전트 의견", "② 후보 선정", "③ 혼밥 확인", "④ 1차 점수", "⑤ 상의", "⑥ 최종 추천",
                     "혼밥 MBTI는 아직 없어요", "아직 없는 에이전트: 가격", "준비하지 못한 에이전트: 날씨",
                     "1순위: A 국밥집 (도보 8분, 9,000원)", "🧭 조율자: 오늘은 A 국밥집을 추천해요."):
            self.assertIn(part, result["text"])

    def test_no_app_data(self):
        agents = [{"name": "취향", "weight": 15, "module": fake("취향", {})}]
        original = app_data.load
        app_data.load = lambda folder=app_data.FOLDER: None
        try:
            result = coordinator.run({"now": NOW}, None, agents, [])
        finally:
            app_data.load = original
        self.assertFalse(result["ok"])
        self.assertIn("지금 보내기", result["text"])

    def test_assumed_agents_fill_missing(self):
        """없는 혼밥·가격·메뉴를 가정 에이전트로 채우고, 실제 취향 + 날씨값과 대화가 되는지"""
        with tempfile.TemporaryDirectory() as folder:
            app_data.save({**EXPORT, "mbti": "WBNV"}, folder)
            profile = taste.load_profile(folder, NOW.date())
        import taste_agent
        import weather_agent
        report = {"direction": "따뜻한 국물", "feels_like": 4.0, "comparison": None,
                  "message": "따뜻한 국물요리 추천해요!", "time": "2026-11-26 12:00"}
        parts = ("opinion", "score", "rebut", "propose")
        taste_module = types.SimpleNamespace(**{k: getattr(taste_agent, k) for k in parts}, prepare=lambda ctx: profile)
        weather_module = types.SimpleNamespace(**{k: getattr(weather_agent, k) for k in ("opinion", "score", "rebut")},
                                               prepare=lambda ctx: report)
        agents = [{"name": "취향", "weight": 15, "module": taste_module},
                  {"name": "날씨", "weight": 10, "module": weather_module}]
        result = coordinator.run({"now": NOW, "mbti": "WBNV"}, self.stores, agents, ["혼밥", "거리", "가격", "메뉴"],
                                 assume_missing=True)
        self.assertEqual(result["assumed"], ["혼밥", "거리", "가격", "메뉴"])
        self.assertNotIn("메뉴", result["weights"])
        self.assertAlmostEqual(sum(result["weights"].values()), 100)
        self.assertIn("📋 메뉴(가정)", result["text"])
        self.assertIn("가성비파시니", result["text"])

    @unittest.skipIf(__import__("shutil").which("node") is None, "node가 없어요")
    def test_example_scenario(self):
        """처음 예시 A~E: 실제 날씨·취향·거리 에이전트 + 가정 혼밥·메뉴·가격"""
        import scenario_demo
        result = scenario_demo.run_example()
        names = [row["store"]["name"] for row in result["ranking"]]
        # 어제 같은 종류 감점이 -3으로 줄어서, 어제 라면을 먹었어도 가까운 B 라멘집이 1순위가 된다
        self.assertEqual(names, ["B 라멘집", "A 국밥집", "D 돈까스집"])
        self.assertEqual({s["name"] for s, _ in result["dropped"]}, {"C 찌개집", "E 덮밥집"})
        self.assertEqual(result["debate"][0]["agent"], "가격")  # B가 가장 가까워서 거리는 반론하지 않음
        stance = {d["agent"]: d["stance"] for d in result["debate"][1:]}
        self.assertEqual(stance, {"혼밥": "반대", "거리": "반대", "취향": "판단 안 함", "날씨": "반대"})
        self.assertEqual(next(r for r in result["ranking"] if r["store"]["name"] == "B 라멘집")["scores"]["취향"]["score"], 6)
        self.assertIn("E 덮밥집, C 찌개집은 점수와 상관없이 탈락 조건으로 빠졌어요.", result["text"])
        self.assertEqual(scenario_demo.run_example(hurry=True)["ranking"][0]["store"]["name"], "B 라멘집")

    @unittest.skipIf(__import__("shutil").which("node") is None, "node가 없어요")
    def test_mbti_changes_the_answer(self):
        """같은 가게·같은 날이어도 혼밥 MBTI에 따라 에이전트 판단과 1순위가 달라진다"""
        import scenario_demo
        cozy = scenario_demo.run_person("WBNV")    # 아늑파·탐험파·가성비파
        flex = scenario_demo.run_person("AORP")    # 당당파·단골파·플렉스파
        self.assertEqual(cozy["ranking"][0]["store"]["name"], "B 라멘집")  # 탐험파 +3이 어제 면 -3을 상쇄
        self.assertEqual(flex["ranking"][0]["store"]["name"], "F 샤브집")
        score = lambda result, store, agent: next(r for r in result["ranking"]
                                                  if r["store"]["name"] == store)["scores"][agent]["score"]
        self.assertEqual(score(cozy, "삼덕 백반", "혼밥"), 3)     # 아늑파: 1인석 모르면 크게 감점
        self.assertEqual(score(flex, "삼덕 백반", "혼밥"), 6)
        self.assertEqual(score(cozy, "F 샤브집", "가격"), 2)      # 가성비파: 평균 16,000원은 낮게
        self.assertEqual(score(flex, "F 샤브집", "가격"), 10)     # 플렉스파: 높게
        self.assertGreater(score(cozy, "F 샤브집", "취향"), score(flex, "F 샤브집", "취향"))  # 탐험파 vs 단골파
        self.assertEqual(flex["debate"][0]["agent"], "취향")       # 단골파라 가봤던 A 국밥집을 제안
        self.assertIn("단골파시니 가봤던 A 국밥집은 어떨까요?", flex["debate"][0]["message"])
        self.assertNotIn("H 파스타집", [t["store"] for t in cozy["table"]])  # 1km 밖은 후보에서 빠짐
        self.assertIn('"2인분부터"', next(t for t in cozy["table"] if t["store"] == "C 찌개집")["dropped"][0])

    def test_real_agents_with_app_data(self):
        """실제 취향 에이전트 + 가짜 날씨로 끝까지 돌려 본다."""
        with tempfile.TemporaryDirectory() as folder:
            app_data.save(EXPORT, folder)
            profile = taste.load_profile(folder, NOW.date())
        import taste_agent
        import weather_agent
        report = {"direction": "따뜻한 국물", "feels_like": 4.0, "comparison": None,
                  "message": "따뜻한 국물요리 추천해요!", "time": "2026-11-26 12:00"}
        taste_module = types.SimpleNamespace(**{k: getattr(taste_agent, k) for k in ("opinion", "score", "rebut")},
                                             prepare=lambda ctx: profile)
        weather_module = types.SimpleNamespace(**{k: getattr(weather_agent, k) for k in ("opinion", "score", "rebut")},
                                               prepare=lambda ctx: report)
        agents = [{"name": "취향", "weight": 15, "module": taste_module},
                  {"name": "날씨", "weight": 10, "module": weather_module}]
        result = coordinator.run({"now": NOW}, self.stores, agents, ["혼밥", "거리", "가격"])
        self.assertEqual(result["ranking"][0]["store"]["name"], "A 국밥집")
        self.assertIn("어제에 이어 또 면이에요", result["text"])



class MbtiPercentTest(unittest.TestCase):
    """혼밥 MBTI 퍼센트(사용자가 정한 값)로 비율이 바뀌는지"""
    AGENTS = [{"name": n, "weight": w, "module": types.SimpleNamespace(score=None)}
              for n, w in (("혼밥", 35), ("거리", 20), ("가격", 20), ("취향", 15), ("날씨", 10))]

    def test_parse_pct(self):
        import mbti
        pct, problem = mbti.parse_pct("WBNV", [75, 87.5, 62.5, 75])
        self.assertEqual((pct["W"], pct["B"], problem), (0.75, 0.875, ""))
        self.assertEqual(mbti.parse_pct("WBNV", None), (None, "퍼센트 없음"))
        self.assertIn("1번째 글자 A", mbti.parse_pct("ABNV", [75, 80, 60, 70])[1])
        self.assertIn("모양", mbti.parse_pct("WBNV", [75, 80, 60])[1])
        self.assertEqual(mbti.pct_label(pct), "날씨파 75% · 아늑파 88% · 탐험파 62% · 가성비파 75%")

    def test_weights_follow_user_percent(self):
        base = coordinator.weights_for(self.AGENTS, False)
        self.assertEqual(round(base["혼밥"]), 35)
        half = coordinator.weights_for(self.AGENTS, False, {"W": 0.5, "B": 0.5, "N": 0.5, "V": 0.5})
        self.assertEqual({n: round(v, 6) for n, v in half.items()}, {n: round(v, 6) for n, v in base.items()})
        cozy = coordinator.weights_for(self.AGENTS, False, {"W": 0.75, "B": 0.875, "N": 0.6, "V": 0.7})
        self.assertAlmostEqual(cozy["혼밥"], 35 * 1.375 * 100 / 111.875)
        self.assertAlmostEqual(cozy["날씨"], 10 * 1.25 * 100 / 111.875)
        self.assertAlmostEqual(cozy["취향"], 15 * 0.75 * 100 / 111.875)
        self.assertAlmostEqual(sum(cozy.values()), 100)
        hurry = coordinator.weights_for(self.AGENTS, True, {"W": 0.75, "B": 0.875, "N": 0.6, "V": 0.7})
        self.assertGreater(hurry["거리"], cozy["거리"])

    def test_precheck_says_what_is_missing(self):
        lacking = coordinator.precheck({"mbti": None})
        self.assertIn("혼밥 MBTI가 없어요", lacking[0]["what"])
        lacking = coordinator.precheck({"mbti": "WBNV"}, missing=["가격"])
        self.assertEqual(len(lacking), 2)
        self.assertIn("퍼센트가 없어요", lacking[0]["what"])
        self.assertIn("가격", lacking[1]["what"])
        self.assertEqual(coordinator.precheck({"mbti": "WBNV", "mbti_pct": [75, 80, 60, 70]}), [])

    def test_app_data_keeps_only_matching_percent(self):
        good = app_data.validate({**EXPORT, "mbti": "WBNV", "mbti_pct": [75, 80, 60, 70]})
        self.assertEqual(good["mbti_pct"], [75, 80, 60, 70])
        bad = app_data.validate({**EXPORT, "mbti": "WBNV", "mbti_pct": [25, 80, 60, 70]})
        self.assertIsNone(bad["mbti_pct"])

if __name__ == "__main__":
    unittest.main()
