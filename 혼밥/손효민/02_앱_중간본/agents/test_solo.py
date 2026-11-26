"""혼밥 에이전트 시험: python -m unittest test_solo
기준: 혼밥팀 최종본(2026-11-26)의 혼밥 점수 = 후기 순위 8점 + 1인석 2점"""
import unittest
from datetime import datetime

import coordinator
import solo_agent as s

NOW = datetime(2026, 11, 26, 12, 10)


def store(i, cnt, **more):
    return {"id": i, "name": f"가게{i}", "cnt": cnt, **more}


def prepared(counts, diary=None, **ctx):
    ctx = {"now": NOW, "diary": diary or [], **ctx}
    stores = [store(i, c) for i, c in enumerate(counts, 1)]
    state, _ = s.candidates(s.prepare(ctx), stores, ctx)
    return state, stores, ctx


class Score(unittest.TestCase):
    def test_twenty_stores_make_eight_steps(self):  # 넘겨주기 문서의 표
        state, stores, ctx = prepared(range(2000, 0, -100))
        got = [s.score(state, x, ctx)["score"] for x in stores]
        self.assertEqual(got, [8, 8, 8, 7, 7, 6, 6, 6, 5, 5, 4, 4, 4, 3, 3, 2, 2, 2, 1, 1])

    def test_ties_and_single_store(self):
        state, stores, ctx = prepared([50, 50, 10, 5])
        self.assertEqual([s.score(state, x, ctx)["score"] for x in stores], [8, 8, 4, 2])
        state, stores, ctx = prepared([7])
        self.assertEqual(s.score(state, stores[0], ctx)["score"], 8)

    def test_seat_adds_two_from_data_or_diary(self):
        state, stores, ctx = prepared([30, 20, 10], diary=[{"가게": "가게3", "혼밥포인트": ["1인석 있음"]}])
        self.assertEqual(s.score(state, {**stores[0], "solo_seat": "있음"}, ctx)["score"], 10)
        self.assertEqual(s.score(state, {**stores[0], "solo_seat": "없음"}, ctx)["score"], 8)
        got = s.score(state, stores[2], ctx)
        self.assertEqual(got["score"], 3 + 2)
        self.assertIn("1인석", got["why"])

    def test_unknown_count_and_two_person_only(self):
        state, stores, ctx = prepared([30, None])
        self.assertEqual((s.score(state, stores[1], ctx)["score"], s.score(state, stores[1], ctx)["확실도"]), (0, "낮음"))
        self.assertFalse(s.check(state, {**stores[0], "single_ok": False}, ctx)[0])
        self.assertTrue(s.check(state, stores[0], ctx)[0])


class Debate(unittest.TestCase):
    def test_rebut_by_points(self):
        state, stores, ctx = prepared([80, 70, 60, 50, 40, 30, 20, 10])  # 8,7,6,5,4,3,2,1점
        against = s.rebut(state, "거리", stores[5], stores[0], ctx)
        self.assertEqual(against["stance"], "반대")
        for word in ("거리", "30명", "80명"):
            self.assertIn(word, against["message"])
        self.assertEqual(s.rebut(state, "거리", stores[0], stores[5], ctx)["stance"], "동의")
        self.assertEqual(s.rebut(state, "거리", stores[1], stores[0], ctx)["stance"], "판단 안 함")

    def test_seat_difference_is_enough_to_take_a_side(self):
        state, stores, ctx = prepared([80, 70, 60, 50, 40, 30, 20, 10])
        seated = {**stores[1], "solo_seat": "있음"}          # 7 + 2 = 9점 vs 8점
        got = s.rebut(state, "거리", seated, stores[0], ctx)
        self.assertEqual(got["stance"], "동의")
        self.assertIn("1인석 있음", got["message"])

    def test_join_with_my_own_store_or_agree(self):
        state, stores, ctx = prepared([80, 70, 60, 50, 40, 30, 20, 10])
        rows = [{"store": stores[i]} for i in (3, 5, 0)]     # 1순위 5점, 상대 제안 3점, 내가 보는 곳 8점
        own = s.join(state, rows, {"proposed": stores[5], "current": stores[3]}, ctx)
        self.assertIs(own["proposed"], stores[0])
        self.assertEqual(own["stance"], "제안")
        self.assertIn("저도", own["message"])
        same = s.join(state, rows, {"proposed": stores[0], "current": stores[3]}, ctx)
        self.assertEqual(same["stance"], "동의")
        best_first = [{"store": stores[0]}, {"store": stores[3]}]
        self.assertIsNone(s.join(state, best_first, {"proposed": stores[3], "current": stores[0]}, ctx))

    def test_propose_only_on_clear_gap(self):
        state, stores, ctx = prepared([80, 70, 60, 50, 40, 30, 20, 10])
        rows = [{"store": stores[i]} for i in (5, 1, 0)]
        offer = s.propose(state, rows, ctx)
        self.assertIs(offer["proposed"], stores[0])
        self.assertIsNone(s.propose(state, [{"store": stores[0]}, {"store": stores[1]}], ctx))


class WithCoordinator(unittest.TestCase):
    def test_solo_objects_together_with_another_agent(self):
        import types
        stores = [store(i, c, area=0, dist_m=100 * i) for i, c in enumerate((50, 10, 300), 1)]
        other = types.SimpleNamespace(
            prepare=lambda ctx: {}, opinion=lambda a, c: "",
            score=lambda a, x, c: {"score": {1: 10, 2: 9, 3: 0}[x["id"]], "확실도": "높음", "why": ""},
            propose=lambda a, rows, c: {"proposed": next(r["store"] for r in rows if r["store"]["id"] == 2),
                                      "current": rows[0]["store"], "message": "거리 반론"})
        agents = [{"name": "혼밥", "weight": 10, "module": s}, {"name": "거리", "weight": 90, "module": other}]
        result = coordinator.run({"now": NOW, "order": None}, stores, agents, [])
        said = [(d["agent"], d["stance"]) for d in result["debate"]]
        self.assertEqual(said[0], ("거리", "제안"))
        self.assertIn(("혼밥", "제안"), said[1:])
        self.assertIn("혼밥 에이전트도 함께 반론하며 민 곳이에요.", result["text"])

    def test_loaded_by_file_name_and_scores_differ(self):
        agents, _ = coordinator.load_agents((("혼밥", "solo_agent", 35),))
        self.assertIs(agents[0]["module"], s)
        stores = [store(i, c, area=0, dist_m=100 * i) for i, c in enumerate((10, 300, 40), 1)]
        result = coordinator.run({"now": NOW}, stores, agents, [])
        self.assertEqual([r["store"]["name"] for r in result["ranking"]], ["가게2", "가게3", "가게1"])


if __name__ == "__main__":
    unittest.main()
