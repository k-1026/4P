"""python3 test_scoring.py — 설계 문서와 role_check.json의 예시가 10점 규칙으로 그대로 나오는지 확인한다."""
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
    def test_rules(self):
        self.assertEqual(s.score_solo("C", single_ok=False)["verdict"], "drop")
        self.assertEqual(s.score_solo("B", single_ok=True, seat="bar")["score"], 10)
        self.assertEqual(s.score_solo("A", single_ok=True)["score"], 6)
        self.assertEqual(s.score_solo("A", single_ok=True, cozy_without_pct=True)["score"], 3)
        self.assertEqual(s.score_solo("Z")["verdict"], "unknown")


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


if __name__ == "__main__":
    unittest.main()
