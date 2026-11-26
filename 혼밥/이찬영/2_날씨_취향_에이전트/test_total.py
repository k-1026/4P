"""가중치 계산 시험."""
import unittest
from unittest import mock

import app
import taste
import test_taste
import total
import weather


def store(name, weather, taste, price):
    return {"name": name, "scores": {"날씨": weather, "취향": taste, "가격": price}}


class TotalTest(unittest.TestCase):
    def test_multiplies_percent_and_sorts(self):
        weights = {"날씨": 10, "취향": 60, "가격": 30}
        result = total.rank([store("B", 10, 2, 5), store("A", 10, 10, 5)], weights)
        # A: 10x0.1 + 10x0.6 + 5x0.3 = 8.5 / B: 1 + 1.2 + 1.5 = 3.7
        self.assertEqual([(s["name"], s["total"], s["place"]) for s in result],
                         [("A", 8.5, 1), ("B", 3.7, 2)])

    def test_same_total_same_place(self):
        weights = {"날씨": 50, "취향": 50, "가격": 0}
        result = total.rank([store("A", 10, 0, 0), store("B", 0, 10, 0)], weights)
        self.assertEqual([s["place"] for s in result], [1, 1])

    def test_rejects_bad_values(self):
        good = [store("A", 10, 10, 10)]
        for weights in ({"날씨": 10, "취향": 10, "가격": 10}, {"날씨": 150, "취향": -50, "가격": 0}):
            with self.assertRaises(ValueError):
                total.rank(good, weights)
        with self.assertRaises(ValueError):
            total.rank([store("A", 10, 11, 10)], {"날씨": 100, "취향": 0, "가격": 0})


class ScreenTest(unittest.TestCase):
    def setUp(self):  # 취향은 샘플 일기(오늘 11/26, 어제 라멘)로 고정
        patcher = mock.patch.object(taste, "load_profile", return_value=test_taste.sample_profile())
        patcher.start()
        self.addCleanup(patcher.stop)
        no_mbti = mock.patch.object(app, "user_mbti", return_value=None)  # 진짜 앱데이터.json의 MBTI에 영향받지 않게
        no_mbti.start()
        self.addCleanup(no_mbti.stop)

    def test_taste_score_is_automatic(self):
        now = {"time": "2026-11-26 12:00", "direction": "따뜻한 국물", "feels_like": 4.0}
        form = {"weight_날씨": ["0"], "weight_취향": ["100"], "weight_가격": ["0"],
                "name1": ["B 라멘집"], "food1": ["따뜻한 국물"], "price1": ["5"],
                "name2": ["A 국밥집"], "food2": ["따뜻한 국물"], "price2": ["5"],
                "name3": ["새 돈까스"], "food3": ["따뜻한 요리"], "kind3": ["튀김·까스"], "price3": ["5"]}
        with mock.patch.object(weather, "main", return_value=now):
            text = app.run_rank(form)
        self.assertIn("1순위 A 국밥집: 10점", text)
        self.assertIn("2순위 새 돈까스: 6점 (취향 기록 없음: 취향은 기본 6점)", text)
        self.assertIn("2순위 B 라멘집: 6점", text)  # 면 9점 - 어제 3점
        self.assertIn("어제에 이어 또 면이에요", text)

    def test_reply_has_both_agents(self):
        now = {"time": "2026-11-26 12:00", "direction": "따뜻한 국물", "feels_like": 4.0}
        form = {"sender": ["거리"], "store": ["B 라멘집"], "food_type": ["따뜻한 국물"],
                "current": ["A 국밥집"], "current_type": ["따뜻한 국물"]}
        with mock.patch.object(weather, "main", return_value=now):
            text = app.run_reply(form)
            self.assertIn("🌡️", text)
            self.assertIn("A 국밥집을 지지합니다", text)
            self.assertIn("급하시면", app.run_reply({**form, "hurry": ["1"]}))
            self.assertNotIn("📒", app.run_reply({**form, "sender": ["취향기록"]}))
            self.assertNotIn("🌡️", app.run_reply({**form, "sender": ["날씨"]}))

    def test_taste_screen_uses_app_mbti(self):
        """앱이 보낸 혼밥 MBTI의 탐험파/단골파가 취향 화면에도 들어가는지"""
        for code, word in (("AORP", "단골파"), ("WBNV", "탐험파")):
            with mock.patch.object(app, "user_mbti", return_value=code):
                self.assertIn(f"{word}시니", app.run_taste())
                answer = app.taste_reply("거리", "A 국밥집", "", "", "", False)
                self.assertIn(word, answer)
        with mock.patch.object(app, "user_mbti", return_value="AORP"):
            regular = app.taste_reply("거리", "A 국밥집", "", "", "", False)
        self.assertIn("가봤던 곳(별점 5점)은 +3점", regular)  # 단골파: 혼밥일기에 있는 가게 기록을 씀

    def test_fetches_weather_every_time(self):
        report = {"time": "2026-11-25 12:00", "direction": "없음", "feels_like": 15.0}
        with mock.patch.object(weather, "main", return_value=report) as fetch:
            app.run_reply({"store": ["A"]})
            app.run_rank({})
        self.assertEqual(fetch.call_count, 2)

    def test_does_not_calculate_when_fetch_fails(self):
        with mock.patch.object(weather, "main", return_value=None):
            for text in (app.run_rank({}), app.run_reply({})):
                self.assertIn("가져오지 못해서", text)

    def test_ranking_marks_unknown_food(self):
        now = {"time": "2026-11-25 12:00", "direction": "따뜻한 국물", "feels_like": 4.0}
        form = {"weight_날씨": ["100"], "weight_취향": ["0"], "weight_가격": ["0"],
                "name1": ["A"], "food1": ["모름"], "taste1": ["1"], "price1": ["1"],
                "name2": ["B"], "food2": ["따뜻한 국물"], "taste2": ["1"], "price2": ["1"]}
        with mock.patch.object(weather, "main", return_value=now):
            lines = app.run_rank(form).splitlines()
        self.assertIn("확인 안 됨", next(line for line in lines if "순위 A" in line))
        self.assertNotIn("확인 안 됨", next(line for line in lines if "순위 B" in line))


if __name__ == "__main__":
    unittest.main()
