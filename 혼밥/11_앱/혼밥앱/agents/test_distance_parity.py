"""파이썬 거리 규칙이 원래 JS(../distance_agent.js)와 같은 결과를 내는지 시험 (node가 있을 때만)."""
import json
import os
import random
import shutil
import subprocess
import unittest

import distance_rules

JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "distance_agent.js")
SCRIPT = r"""
const DA = require(process.argv[1]);
let s = ''; process.stdin.on('data', c => s += c); process.stdin.on('end', () => {
  const out = JSON.parse(s).map(q => {
    const report = DA.buildReport(q.places, q.origin, q.options);
    return { report, objection: DA.objection(report, { first_ranking: q.ranking, weather: q.weather }),
             rebut: DA.rebut(report, '가격', q.proposed, q.current, { weather: q.weather, urgent: q.urgent }) };
  });
  process.stdout.write(JSON.stringify(out));
});
"""
NAMES = ["국밥집", "라멘", "삼덕 백반", "Cafe 12", "돈까스", "칼국수"]


def case(rng):
    n = rng.randint(1, 8)
    places = [{"id": str(i), "place_name": f"{rng.choice(NAMES)}{i}",
               "distance": rng.choice([None, rng.randint(0, 1200), rng.randint(0, 1200)]), "x": "128.5", "y": "35.8",
               "category_name": "음식점 > 한식"} for i in range(n)]
    ranking = [{"id": p["id"], "score": rng.choice([8, 7.5, 7, 6.2, 5])} for p in rng.sample(places, n)]
    urgent = rng.random() < 0.3
    return {"places": places, "origin": {"lat": 35.8, "lng": 128.5, "accuracy_m": rng.choice([None, 10, 500]),
                                         "source": "gps"},
            "options": {"radius_m": 1000, "truncated": False, "urgent": urgent},
            "ranking": sorted(ranking, key=lambda r: -r["score"]),
            "weather": rng.choice([None, {"temp_c": 4}, {"temp_c": 4.5}, {"temp_c": 13.6}, {"temp_c": 4.0}]),
            "proposed": str(rng.randrange(n + 1)), "current": str(rng.randrange(n)), "urgent": urgent}


@unittest.skipUnless(shutil.which("node") and os.path.exists(JS), "node 또는 distance_agent.js가 없어요")
class Parity(unittest.TestCase):
    def test_same_as_js(self):
        rng = random.Random(7)
        cases = [case(rng) for _ in range(1500)]
        done = subprocess.run(["node", "-e", SCRIPT, JS], capture_output=True, timeout=120,
                              input=json.dumps(cases, ensure_ascii=False).encode("utf-8"), check=True)
        seen = {"objection": 0, "반대": 0, "동의": 0, "판단 안 함": 0}
        for q, js in zip(cases, json.loads(done.stdout.decode("utf-8"))):
            report = distance_rules.build_report(q["places"], q["origin"], q["options"])
            for key in ("id", "name", "walk_min", "walk_label", "confidence", "excluded", "distance_score"):
                self.assertEqual([c[key] for c in report["candidates"]],
                                 [c[key] for c in js["report"]["candidates"]], (key, q))
            ours = distance_rules.objection(report, first_ranking=q["ranking"], weather=q["weather"])
            self.assertEqual(ours and (ours["target"], ours["prefer"], ours["message"]),
                             js["objection"] and (js["objection"]["target"], js["objection"]["prefer"],
                                                  js["objection"]["message"]), q)
            answer = distance_rules.rebut(report, "가격", q["proposed"], q["current"], weather=q["weather"],
                                          urgent=q["urgent"])
            self.assertEqual((answer["stance"], answer["message"]),
                             (js["rebut"]["stance"], js["rebut"]["message"]), q)
            seen["objection"] += bool(ours)
            seen[answer["stance"]] += 1
        self.assertTrue(all(seen.values()), seen)   # 모든 갈래를 실제로 지나갔는지


if __name__ == "__main__":
    unittest.main()
