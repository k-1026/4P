"""인터넷과 API 키 없이, 가짜 값으로 판단 규칙을 시험한다."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta

import weather


def fake(temp):
    return {"T1H": temp, "REH": 50.0, "WSD": 0.0}


class WeatherTest(unittest.TestCase):
    def test_rules(self):
        cases = {-3: "따뜻한 국물", 5: "따뜻한 국물", 5.1: "따뜻한 요리", 10: "따뜻한 요리",
                 10.1: "없음", 25: "없음", 25.9: "없음", 26: "차가운 요리", 33: "차가운 요리"}
        for temp, expected in cases.items():
            self.assertEqual(weather.recommend(temp)[0], expected, temp)

    def test_reply(self):
        # (지금 날씨 방향, 가게 음식 종류) -> 날씨에 맞는지 (None은 판단할 것이 없음)
        cases = {("따뜻한 국물", "따뜻한 국물"): True, ("따뜻한 국물", "따뜻한 요리"): True,
                 ("따뜻한 국물", "차가운 요리"): False, ("따뜻한 요리", "따뜻한 국물"): True,
                 ("차가운 요리", "차가운 요리"): True, ("차가운 요리", "따뜻한 국물"): False,
                 ("차가운 요리", "따뜻한 요리"): True,  # 점수 5점: 국물이 아니면 괜찮음
                 ("없음", "차가운 요리"): None, ("따뜻한 국물", "모름"): None}
        for (direction, food), expected in cases.items():
            report = {"direction": direction, "feels_like": 4.0}
            answer = weather.reply(report, "거리", "B 라멘", food)
            self.assertIs(answer["fits"], expected, (direction, food))
            self.assertIn("B 라멘", answer["message"])
            self.assertIn("거리", answer["message"])

    def test_compare_sentence(self):
        self.assertEqual(weather.compare(4.0, 10.0, "ASOS"), "어제 같은 시각보다 6.0도 낮아요.")
        self.assertEqual(weather.compare(10.3, -0.1, "ASOS"), "어제 같은 시각보다 10.4도 높아요.")
        self.assertEqual(weather.compare(4.0, 4.0, "ASOS"), "어제 같은 시각과 같아요.")
        # 대체값이나 전날 값이 없으면 비교하는 말을 하지 않는다
        self.assertIsNone(weather.compare(4.0, 10.0, "대체값"))
        self.assertIsNone(weather.compare(4.0, None, None))

    def test_score(self):
        foods = ("따뜻한 국물", "따뜻한 요리", "차가운 요리")
        table = {"따뜻한 국물": (10, 5, 0), "따뜻한 요리": (10, 10, 0),
                 "없음": (5, 5, 5), "차가운 요리": (0, 5, 10)}
        for direction, expected in table.items():
            report = {"direction": direction}
            got = tuple(weather.score(report, food)["score"] for food in foods)
            self.assertEqual(got, expected, direction)
            unknown = weather.score(report, "모름")
            self.assertEqual((unknown["score"], unknown["confirmed"]), (5, False))
        self.assertTrue(weather.score({"direction": "없음"}, foods[0])["confirmed"])

    def test_rebut(self):
        # (날씨 방향, 상대가 미는 가게 음식, 지금 1순위 음식) -> 날씨 에이전트의 입장
        cases = {("따뜻한 국물", "차가운 요리", "따뜻한 국물"): "반대",
                 ("따뜻한 국물", "따뜻한 요리", "따뜻한 국물"): "반대",
                 ("따뜻한 국물", "따뜻한 국물", "따뜻한 국물"): "동의",
                 ("따뜻한 국물", "따뜻한 국물", "따뜻한 요리"): "동의",
                 ("따뜻한 요리", "따뜻한 요리", "따뜻한 국물"): "동의",
                 ("차가운 요리", "따뜻한 국물", "차가운 요리"): "반대",
                 ("차가운 요리", "따뜻한 국물", "따뜻한 요리"): "반대",  # 둘 다 안 맞음
                 ("없음", "차가운 요리", "따뜻한 국물"): "판단 안 함",
                 ("따뜻한 국물", "모름", "따뜻한 국물"): "판단 안 함"}
        for (direction, proposed, current), expected in cases.items():
            report = {"direction": direction, "feels_like": 4.0}
            answer = weather.rebut(report, "거리", "B 라멘", proposed, "A 국밥", current)
            self.assertEqual(answer["stance"], expected, (direction, proposed, current))
            self.assertIn("B 라멘", answer["message"])

    def test_feels_like(self):
        self.assertEqual(weather.feels_like(fake(20.0), 11), 20.0)
        self.assertLess(weather.feels_like({"T1H": 4.0, "REH": 50.0, "WSD": 3.0}, 11), 4.0)
        self.assertTrue(25 < weather.feels_like(fake(30.0), 8) < 35)

    def test_compares_same_hour_of_previous_day(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "api_key.txt"), "w", encoding="utf-8") as file:
                file.write("testkey")
            asked = []

            def past(key, when):
                asked.append(when)
                return fake(14.0)

            now = datetime(2026, 11, 2, 12, 20)
            report = weather.main(now, lambda key, when: fake(11.0), folder, past)
            self.assertEqual((asked[0].day, asked[0].hour), (1, 12))
            self.assertEqual(report["yesterday"], 14.0)
            self.assertEqual(report["direction"], "없음")

            self.assertEqual(report["yesterday_source"], "ASOS")

            # ASOS가 안 되면 23시간 전 실황값으로 대체
            asked.clear()

            def current(key, when):
                asked.append(when)
                return fake(11.0)

            report = weather.main(datetime(2026, 11, 2, 9, 20), current, folder, lambda key, when: None)
            self.assertEqual((asked[-1].day, asked[-1].hour), (1, 10))
            self.assertEqual(report["yesterday_source"], "대체값")

            # 23시대에는 대체값도 없다
            report = weather.main(datetime(2026, 11, 2, 23, 20), current, folder, lambda key, when: None)
            self.assertIsNone(report["yesterday"])
            self.assertIsNone(report["yesterday_source"])

    def test_missing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "api_key.txt"), "w", encoding="utf-8") as file:
                file.write("여기에 API 키를 넣으세요")
            self.assertIsNone(weather.main(datetime(2026, 11, 1, 12, 0), None, folder))


if __name__ == "__main__":
    unittest.main()
