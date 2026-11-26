"""반론이 나오면 사용자가 점수를 높일지 정하는지 시험: python -m unittest test_persuade
반론 에이전트가 사용자에게 장점을 말하고, 다른 에이전트는 그대로 두자고 설득한 뒤, 사용자가 고른다."""
import types
import unittest
from datetime import datetime

import coordinator

NOW = datetime(2026, 11, 26, 12, 10)
NAMES = ("일등집", "제안집")


def agent(name, scores, stance=None):
    table = dict(zip(NAMES, scores))
    parts = {"prepare": lambda ctx: {}, "opinion": lambda s, c: "",
             "score": lambda s, store, c: {"score": table[store["name"]], "확실도": "높음", "why": f"{name} 이유."}}
    if stance:
        parts["propose"] = lambda s, rows, c: None
        parts["rebut"] = lambda s, sender, proposed, current, c: {"stance": stance, "확실도": "높음",
                                                                  "message": f"{stance}예요."}
    return {"name": name, "weight": 20, "module": types.SimpleNamespace(**parts)}


def proposer(scores):
    made = agent("거리", scores)
    made["module"].propose = lambda s, rows, c: {"proposed": next(r["store"] for r in rows if r["store"]["id"] == 2),
                                                 "current": rows[0]["store"], "message": "제안집 어때요?"}
    return made


def run(choice=None):
    stores = [{"id": i, "area": 0, "name": NAMES[i - 1], "dist_m": 100 * i} for i in (1, 2)]
    return coordinator.run({"now": NOW, "choice": choice}, stores,
                           [proposer((5, 9)), agent("취향", (10, 5), "반대")], [])


class AskUser(unittest.TestCase):
    def test_both_sides_talk_to_the_user_then_ask(self):
        result = run()
        said = [(e["agent"], e["stance"], e["text"]) for e in result["log"] if e["text"].startswith("사용자님")]
        self.assertEqual([(a, s) for a, s, _ in said], [("거리", "반론"), ("취향", "설득")])
        self.assertIn("거리 점수가 제안집 9점, 일등집 5점이라 이 부분에서 더 나아요.", said[0][2])
        self.assertIn("그대로 가는 게 좋다고 생각해요", said[1][2])
        self.assertIn("취향 점수가 제안집 5점, 일등집 10점", said[1][2])
        self.assertEqual(result["choice"]["question"], "제안집의 점수를 높일까요?")
        self.assertEqual([o["value"] for o in result["choice"]["options"]], ["raise:제안집", "keep:제안집"])
        self.assertIsNone(result["chosen"])
        self.assertEqual(result["ranking"][0]["store"]["name"], "일등집")   # 고르기 전에는 점수 그대로
        self.assertEqual(result["ranking"][1]["scores"]["취향"]["score"], 5)

    def test_raise_changes_scores_and_rank(self):
        after = run("raise:제안집")
        self.assertEqual(after["chosen"], "raise")
        self.assertEqual(after["ranking"][0]["store"]["name"], "제안집")
        self.assertEqual({n: s["score"] for n, s in after["ranking"][0]["scores"].items()}, {"거리": 9, "취향": 10})
        self.assertIn("취향 5→10점", after["text"])
        self.assertIn("1순위: 제안집", after["text"])
        self.assertIn("직접 점수를 높이신 곳이에요.", after["text"])

    def test_keep_changes_nothing(self):
        before, after = run(), run("keep:제안집")
        self.assertEqual(after["chosen"], "keep")
        self.assertEqual(after["ranking"][0]["store"]["name"], "일등집")
        self.assertEqual([r["total"] for r in after["ranking"]], [r["total"] for r in before["ranking"]])
        self.assertIn("점수는 그대로 둘게요", after["text"])

    def test_answer_for_another_store_is_ignored(self):
        for choice in ("raise:없는집", "raise", "제안집"):
            result = run(choice)
            self.assertIsNone(result["chosen"], choice)
            self.assertEqual(result["ranking"][0]["store"]["name"], "일등집")

    def test_no_question_without_a_proposal(self):
        result = coordinator.run({"now": NOW}, [{"id": 1, "area": 0, "name": "일등집", "dist_m": 100}],
                                 [agent("취향", (10, 5))], [])
        self.assertIsNone(result["choice"])


if __name__ == "__main__":
    unittest.main()
