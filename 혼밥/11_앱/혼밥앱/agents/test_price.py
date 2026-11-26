"""가격 에이전트 시험: python -m unittest test_price
기준: 1126proto (prompts/budget.md, criteria.json의 budget)"""
import unittest
from datetime import datetime

import coordinator
import price_agent as p

NOW = datetime(2026, 11, 26, 12, 10)
EXAMPLE = (("A 국밥", 9000), ("B 라멘", 9500), ("C 찌개", 9000), ("D 돈까스", 8000), ("E 덮밥", 12000))


def store(i, name, price, **more):
    return {"id": i, "name": name, "price": price, **more}


def prepared(prices=EXAMPLE, **ctx):
    ctx = {"now": NOW, "mbti": "WBNV", "budget": None, **ctx}
    stores = [store(i, n, v) for i, (n, v) in enumerate(prices, 1)]
    state, _ = p.candidates(p.prepare(ctx), stores, ctx)
    return state, {s["name"]: s for s in stores}, ctx


class Score(unittest.TestCase):
    def test_design_example(self):  # 설계 문서 3.6 표 (상한 1만 원)
        state, s, ctx = prepared()
        got = {n: p.score(state, s[n], ctx)["score"] for n in ("A 국밥", "B 라멘", "C 찌개", "D 돈까스")}
        self.assertEqual(got, {"A 국밥": 5, "B 라멘": 3, "C 찌개": 5, "D 돈까스": 10})
        self.assertFalse(p.check(state, s["E 덮밥"], ctx)[0])

    def test_caps(self):
        for code, budget, ok in (("WBNV", None, False), (None, None, True), ("WBNP", None, True),
                                 (None, 11000, False), ("WBNP", 11000, False)):
            state, s, ctx = prepared(mbti=code, budget=budget)
            self.assertEqual(p.check(state, s["E 덮밥"], ctx)[0], ok, (code, budget))

    def test_any_budget_drops_nothing(self):
        state, s, ctx = prepared(budget_any=True)
        self.assertTrue(p.check(state, s["E 덮밥"], ctx)[0])
        self.assertEqual(p.score(state, s["D 돈까스"], ctx)["score"], 10)   # 싼 곳 점수는 그대로
        self.assertIn("상관없", p.opinion(state, ctx))
        self.assertNotIn("이내", p.rebut(state, "거리", s["B 라멘"], s["A 국밥"], ctx)["message"])

    def test_median_of_menus(self):
        state, _ = p.candidates({}, [], {"now": NOW})
        menus = [{"name": "a", "price": 5000}, {"name": "b", "price": 9000}, {"name": "c", "price": 20000}]
        self.assertEqual(p.person_price(store(1, "x", 1000, menus=menus)), 9000)
        self.assertEqual(p.person_price(store(1, "x", 7000, menus=[])), 7000)
        self.assertIsNone(p.person_price(store(1, "x", None)))

    def test_piece_prices_are_not_a_meal(self):
        for name in ("항정살 꼬치", "삼겹살 3ea", "노란 접시", "초밥류", "롤 & 군함류"):
            self.assertIsNone(p.person_price(store(1, "x", 2000, menu=name, menus=[{"name": name, "price": 2000}])), name)
        for name, price in (("신천궁전떡볶이", 2500), ("마실김밥", 3000), ("양꼬치 10개", 15000), ("모둠초밥", 3900)):
            self.assertEqual(p.person_price(store(1, "x", price, menu=name)), price, name)
        mixed = [{"name": "항정살 꼬치", "price": 1300}, {"name": "마라탕", "price": 9000}]
        self.assertEqual(p.person_price(store(1, "x", 1300, menu="항정살 꼬치", menus=mixed)), 9000)

    def test_piece_price_store_is_unknown_everywhere(self):
        state, s, ctx = prepared()
        skewer = store(9, "꼬치집", 1300, menu="항정살 꼬치", walk_min=2)
        self.assertEqual(p.score(state, skewer, ctx)["score"], 0)
        self.assertIn("낱개", p.score(state, skewer, ctx)["why"])
        self.assertEqual(coordinator.label(skewer, price=p.describe(state, skewer, ctx)), "꼬치집 (도보 2분)")

    def test_few_priced_uses_absolute_rule(self):
        state, s, ctx = prepared((("싼", 8000), ("중", 9500), ("모름", None)))
        self.assertEqual(p.score(state, s["싼"], ctx)["score"], 10)
        self.assertEqual(p.score(state, s["중"], ctx)["score"], 5)

    def test_unknown_price_is_zero_not_drop(self):
        state, s, ctx = prepared(EXAMPLE + (("F", None),))
        result = p.score(state, s["F"], ctx)
        self.assertEqual((result["score"], result["확실도"]), (0, "낮음"))
        self.assertTrue(p.check(state, s["F"], ctx)[0])
        self.assertEqual(p.describe(state, s["F"], ctx), "가격 모름")

    def test_confidence_by_date(self):
        state, _, ctx = prepared()
        for seen, sure in (("2026-11-20", "높음"), ("2025-01-02", "중간"), (None, "중간")):
            self.assertEqual(p.score(state, store(1, "A 국밥", 9000, seen=seen), ctx)["확실도"], sure, seen)


class Debate(unittest.TestCase):
    def test_small_gap(self):
        state, s, ctx = prepared()
        answer = p.rebut(state, "거리", s["B 라멘"], s["A 국밥"], ctx)
        self.assertEqual(answer["stance"], "판단 안 함")
        self.assertIn("1만 원 이내", answer["message"])
        self.assertIn("차이는 작아요", answer["message"])

    def test_oppose_and_agree_with_numbers_and_sender(self):
        state, s, ctx = prepared()
        against = p.rebut(state, "거리", s["B 라멘"], s["D 돈까스"], ctx)
        self.assertEqual(against["stance"], "반대")
        for word in ("거리", "9,500원", "8,000원", "1,500원"):
            self.assertIn(word, against["message"])
        self.assertEqual(p.rebut(state, "취향", s["D 돈까스"], s["B 라멘"], ctx)["stance"], "동의")

    def test_unknown_price_no_judgement(self):
        state, s, ctx = prepared(EXAMPLE + (("F", None),))
        self.assertEqual(p.rebut(state, "거리", s["F"], s["A 국밥"], ctx)["stance"], "판단 안 함")

    def test_old_price_lowers_confidence_only_when_gap_matters(self):
        state, s, ctx = prepared()
        old = {**s["D 돈까스"], "seen": "2024-05-01"}
        answer = p.rebut(state, "거리", s["B 라멘"], old, ctx)
        self.assertEqual(answer["확실도_낮춤"]["가게"], "D 돈까스")
        self.assertNotIn("확실도_낮춤", p.rebut(state, "거리", s["B 라멘"], s["D 돈까스"], ctx))

    def test_propose_only_on_clear_gap(self):
        state, s, ctx = prepared()
        rows = [{"store": s[n], "total": t} for n, t in (("B 라멘", 8.0), ("A 국밥", 7.8), ("D 돈까스", 7.0))]
        offer = p.propose(state, rows, ctx)
        self.assertIs(offer["proposed"], s["D 돈까스"])
        self.assertIs(offer["current"], s["B 라멘"])
        self.assertIn("1,500원", offer["message"])
        self.assertIsNone(p.propose(state, [{"store": s["A 국밥"]}, {"store": s["B 라멘"]}], ctx))

    def test_premium_stays_out(self):
        state, s, ctx = prepared(mbti="WBNP")
        self.assertTrue(p.weightless(state, ctx))
        self.assertEqual(p.rebut(state, "거리", s["E 덮밥"], s["A 국밥"], ctx)["stance"], "판단 안 함")
        self.assertIsNone(p.propose(state, [{"store": s["E 덮밥"]}, {"store": s["D 돈까스"]}], ctx))


class WithCoordinator(unittest.TestCase):
    def run_one(self, code, budget=None):
        stores = [store(i, n, v, dist_m=100 * i, walk_min=i) for i, (n, v) in enumerate(EXAMPLE, 1)]
        agents = [{"name": "가격", "weight": 20, "module": p},
                  {"name": "날씨", "weight": 10, "module": _flat()}]
        return coordinator.run({"now": NOW, "mbti": code, "budget": budget}, stores, agents, [])

    def test_loaded_by_file_name(self):
        agents, _ = coordinator.load_agents((("가격", "price_agent", 20),))
        self.assertIs(agents[0]["module"], p)

    def test_over_budget_dropped(self):
        result = self.run_one("WBNV")
        self.assertEqual([s["name"] for s, _ in result["dropped"]], ["E 덮밥"])
        self.assertEqual(result["ranking"][0]["store"]["name"], "D 돈까스")

    def test_premium_weight_goes_to_others(self):
        result = self.run_one("WBNP")
        self.assertEqual(result["weights"], {"날씨": 100})
        self.assertEqual(result["dropped"], [])
        self.assertIn("가격으로 가게를 가르지 않", result["text"])

    def test_premium_with_spoken_budget_still_scores(self):
        self.assertIn("가격", self.run_one("WBNP", 10000)["weights"])


def _flat():
    import types
    return types.SimpleNamespace(prepare=lambda ctx: {}, opinion=lambda s, c: "",
                                 score=lambda s, store, c: {"score": 5, "확실도": "높음", "why": ""})


if __name__ == "__main__":
    unittest.main()
