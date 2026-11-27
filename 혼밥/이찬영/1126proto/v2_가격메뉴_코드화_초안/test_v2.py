"""python3 test_v2.py — v2 초안. 기존 시험(1126proto/test_scoring.py)에 가격·메뉴 코드화 시험을 더했다."""
# -*- coding: utf-8 -*-
import unittest

import scoring as s


class Budget(unittest.TestCase):
    def test_design_example(self):  # 예산에이전트_설계.md 3.6 표
        stores = [{"store_id": k, "prices": [p]} for k, p in
                  (("A", 9000), ("B", 9500), ("C", 9000), ("D", 8000), ("E", 12000))]
        got = {x["store_id"]: (x["score"], x["verdict"]) for x in s.score_budget(stores, "value")}
        self.assertEqual(got, {"A": (5, "pass"), "B": (3, "pass"), "C": (5, "pass"),
                               "D": (10, "pass"), "E": (None, "drop")})

    def test_premium_and_few(self):
        two = [{"store_id": "A", "prices": [7000]}, {"store_id": "B", "prices": [9500]}]
        self.assertEqual([x["score"] for x in s.score_budget(two, "value")], [10, 5])
        self.assertEqual([x["score"] for x in s.score_budget(two, "premium")], [10, 10])

    def test_unknown_price(self):
        self.assertEqual(s.score_budget([{"store_id": "X", "prices": []}], "value")[0]["verdict"], "unknown")


class Distance(unittest.TestCase):
    def test_role_check(self):  # 3분·6분·8분 -> 10·7·5, 급함이면 8분은 0
        stores = [{"store_id": k, "walk_min": w} for k, w in (("B", 3), ("F", 6), ("A", 8))]
        self.assertEqual([x["score"] for x in s.score_distance(stores)], [10, 7, 5])
        self.assertEqual(s.score_distance(stores, True)[2]["score"], 0)

    def test_drop_far(self):
        self.assertEqual(s.score_distance([{"store_id": "H", "walk_min": 20}])[0]["verdict"], "drop")


class Weather(unittest.TestCase):
    def test_table(self):
        self.assertEqual(s.weather_direction(4), "따뜻한 국물")
        self.assertEqual(s.score_weather("A", "따뜻한 국물", "차가운 요리")["score"], 0)
        self.assertEqual(s.score_weather("A", "없음", "모름")["verdict"], "unknown")


class Preference(unittest.TestCase):
    def test_role_check(self):
        # 어제 면 -> 라멘집 9점에서 -3 = 6점 (별점 4.5 평균 = 10점 환산 9)
        self.assertEqual(s.score_preference("B", kind_avg10=9, kind_count=3, repeat_days=1)["score"], 6)
        # 탐험파: 안 가본 F 6 -> 9, 가본 A 10 -> 8
        self.assertEqual(s.score_preference("F", mbti_axis="N")["score"], 9)
        self.assertEqual(s.score_preference("A", shop_avg10=10, mbti_axis="N", visited=True)["score"], 8)
        # 단골파: 가본 삼덕 9 -> 10 (상한), 안 가본 F 6 -> 5
        self.assertEqual(s.score_preference("S", shop_avg10=9, mbti_axis="R", visited=True)["score"], 10)
        self.assertEqual(s.score_preference("F", mbti_axis="R")["score"], 5)

    def test_star10(self):
        self.assertEqual(s.star10(5, +1), 10)
        self.assertEqual(s.star10(1, -1), 2)


class Solo(unittest.TestCase):
    """최종본 test_db.py의 점수 시험과 같은 값"""

    def test_20_buckets(self):
        self.assertEqual([p for _, p in s.review_points(list(range(20, 0, -1)))],
                         s.C["solo"]["review_points_20"])

    def test_ties_and_single(self):
        self.assertEqual(s.review_points([76, 76, 10]), [(1, 8), (1, 8), (3, 3)])
        self.assertEqual(s.review_points([5]), [(1, 8)])

    def test_seat_drop_unknown(self):
        got = {x["store_id"]: (x["verdict"], x["score"]) for x in s.score_solo([
            {"store_id": "B1", "solo_review_count": 40, "solo_seat": "있음"},
            {"store_id": "B2", "solo_review_count": 640, "solo_seat": "있음"},
            {"store_id": "C", "single_ok": False, "solo_review_count": 900},
            {"store_id": "Z"}])}
        self.assertEqual(got, {"B2": ("pass", 10), "B1": ("pass", 6), "C": ("drop", None), "Z": ("unknown", None)})

    def test_same_as_final_db(self):  # data/honbap_db_final/혼밥점수.py와 가까운 20곳 점수가 같은지
        import json, os, sqlite3, sys
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "honbap_db_final")
        if not os.path.exists(os.path.join(d, "혼밥_동성로.db")):
            self.skipTest("최종본 DB 없음")
        sys.path.insert(0, d)
        import 혼밥점수
        con = sqlite3.connect("file:" + os.path.join(d, "혼밥_동성로.db") + "?mode=ro", uri=True)
        ids = 혼밥점수.nearest(con, 35.8690, 128.5955)
        want = {x["식당ID"]: x["혼밥점수"] for x in 혼밥점수.score(con, ids)[0]}
        with open(os.path.join(d, "..", "stores_동성로391.json"), encoding="utf-8") as f:
            by = {x["store_id"]: x for x in json.load(f)["stores"]}
        got = {x["store_id"]: x["score"] for x in s.score_solo([by[i] for i in ids])}
        self.assertEqual(got, want)


class Coordinator(unittest.TestCase):
    def test_weights_sum_100(self):
        for tp in (False, True):
            for pr in (False, True):
                self.assertAlmostEqual(sum(s.weights_for(tp, pr).values()), 100)
        self.assertAlmostEqual(sum(s.weights_for(pct={"W": 0.75, "B": 0.9}).values()), 100)

    def test_total_is_10_scale(self):
        w = s.weights_for()
        self.assertEqual(s.total_score({k: 10 for k in w}, w), 10.0)
        self.assertEqual(s.total_score({"solo": 10, "distance": 5, "budget": None,
                                        "preference": 6, "weather": 5}, w), 5.9)  # 590 ÷ 100

    def test_debate_and_gap(self):
        self.assertTrue(s.should_debate([7.2, 6.8, 5.0]))
        self.assertFalse(s.should_debate([7.2, 6.6]))
        self.assertEqual(s.gap_stance(7, 5), "판단 안 함")
        self.assertEqual(s.gap_stance(8, 5), "동의")


class V2Budget(unittest.TestCase):
    def test_prefilter_keeps_unknown_price(self):
        stores = [{"store_id": "A", "price": 9000}, {"store_id": "B", "price": 12000}, {"store_id": "C", "price": None}]
        keep, out = s.budget_prefilter(stores, "value")
        self.assertEqual([x["store_id"] for x in keep], ["A", "C"])
        self.assertEqual([x["store_id"] for x in out], ["B"])

    def test_prefilter_premium_and_user_budget(self):
        stores = [{"store_id": "A", "price": 30000}]
        self.assertEqual(len(s.budget_prefilter(stores, "premium")[0]), 1)
        self.assertEqual(len(s.budget_prefilter([{"store_id": "A", "price": 9000}], "value", 8000)[1]), 1)

    def test_price_facts_does_not_change_score(self):
        stores = [{"store_id": k, "prices": [p]} for k, p in (("A", 6900), ("B", 10000), ("C", 8000), ("D", 9000), ("E", 7000))]
        res = s.score_budget(stores, "value")
        f = s.price_facts({"store_id": "A", "price": 6900}, {"store_id": "B", "price": 10000}, res)
        self.assertEqual(f["price_diff"], -3100)
        self.assertEqual((f["a"]["score"], f["b"]["score"]), (10, 0))
        self.assertEqual(f["stance"], "동의")


class V2Prepare(unittest.TestCase):
    def setUp(self):
        import prepare
        self.p = prepare

    def test_kind_and_weather(self):
        k = self.p.kind_of
        self.assertEqual(k("순대국밥", "백반/한정식")[0], "국밥·탕")
        self.assertEqual(k("참치김밥", "김밥/만두/분식")[0], "분식")
        self.assertEqual(k("탕수육", "중국집"), ("면", "업종"))
        self.assertEqual(k("소소 샤부샤부", "백반/한정식")[0], "찌개")
        self.assertEqual(self.p.weather_type_of("물냉면", "면"), "차가운 요리")
        self.assertEqual(self.p.weather_type_of("메밀칼국수", "면"), "따뜻한 국물")
        self.assertEqual(self.p.weather_type_of("팥죽", "가벼운 식사"), "따뜻한 요리")

    def test_price(self):
        self.assertEqual(self.p.median_price([9000, 10000, None]), 9500)
        self.assertIsNone(self.p.median_price([None]))


if __name__ == "__main__":
    unittest.main()
