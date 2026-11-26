"""샘플 혼밥일기로 취향기록 에이전트의 규칙을 시험한다."""
import json
import os
import shutil
import tempfile
import unittest
from datetime import date

import taste

TODAY = date(2026, 11, 26)  # 샘플 일기에서 어제(11/25)는 동성로 라멘(면)


def sample_profile():
    return taste.build_profile(taste.load_diary(taste.FOLDER), taste.load_stores(taste.FOLDER), TODAY)


class ReviewTest(unittest.TestCase):
    def test_words(self):
        self.assertEqual(taste.review_words("너무 짜고 별로였어요"), ([], ["짜다", "별로다"]))
        self.assertEqual(taste.review_words("진짜 맛있어요"), (["맛있다"], []))  # '진짜'는 짜다가 아님
        self.assertEqual(taste.review_words(""), ([], []))

    def test_context(self):
        # 후기 -> (좋은 쪽인가 +1 / 나쁜 쪽인가 -1 / 판단 어려움 0)
        cases = {"국물이 안 짜서 좋았어요": 1, "맛있지 않아요": -1, "느끼하지 않고 깔끔해요": 1,
                 "별로 안 맛있어요": -1, "별로 안 짜요": 1, "다시는 안 갈래요": -1,
                 "불친절해요": -1, "비추천합니다": -1,
                 "맛있다던데 그냥 그래요": -1,        # '맛있다던데'는 남의 말이라 빼고 판단
                 "맛있을 줄 알았는데": 0,            # 기대했던 말이라 판단 미룸
                 "맛있지만 좀 짜요": 0,              # 좋은 말과 나쁜 말이 섞임 -> 별점을 믿음
                 "생각보다 평범했어요": 0}
        for text, expected in cases.items():
            self.assertEqual(taste.analyze_review(text)["느낌"], expected, text)

    def test_taste_vs_service(self):
        cases = {"맛은 좋았지만 직원이 불친절해요": True, "맛있는데 웨이팅이 길어요": True,
                 "맛은 좋은데 좀 짜요": False,           # 맛 불만도 있음
                 "직원이 불친절해요": False,             # 맛 칭찬이 없음
                 "맛있지만 다시는 안 갈래요": False,     # 이유를 알 수 없는 불만
                 "맛있고 친절해요": False}               # 불만이 없음
        for text, expected in cases.items():
            self.assertIs(taste.analyze_review(text)["맛은좋음_서비스탓"], expected, text)
        self.assertEqual(taste.review_words("웨이팅 없이 바로 앉았어요"), (["안 오래 기다림"], []))

    def test_low_stars_for_service_stay_with_store(self):
        diary = [{"날짜": "2026-11-20 12:00", "가게": "x", "별점": 2, "후기": "맛은 좋았지만 직원이 불친절해요"}]
        p = taste.build_profile(diary, {"x": "면"}, TODAY)
        self.assertEqual(p["종류별"]["면"]["평균별점"], 4)   # 면 자체는 맛 좋음
        self.assertEqual(p["가게별"]["x"]["평균별점"], 2)    # 그 가게는 별점 그대로
        self.assertNotIn("면", p["덜좋아하는종류"])
        self.assertEqual(taste.score(p, "x", "면")["score"], 4)        # 그 가게는 낮게
        self.assertEqual(taste.score(p, "다른 면집", "면")["score"], 8)  # 다른 면집은 괜찮게
        self.assertIn("서비스(불친절하다) 때문에", taste.reason(p, "x", "면"))

    def test_regular_bonus_by_stars(self):
        """단골파: 가봤던 곳 별점 4점 이상 +3, 3점 이상 +1, 3점 미만 0, 안 가본 곳 -1"""
        diary = [{"날짜": "2026-11-01 12:00", "가게": name, "별점": stars, "후기": ""}
                 for name, stars in (("좋은집", 4), ("보통집", 3), ("별로집", 2))]
        p = taste.build_profile(diary, {"좋은집": "분식", "보통집": "분식", "별로집": "분식"}, TODAY)
        for store, expected in (("좋은집", 3), ("보통집", 1), ("별로집", 0), ("처음집", -1)):
            self.assertEqual(taste.mbti_bonus(p, store, "AORP")[0], expected, store)
        self.assertEqual(taste.score(p, "보통집", "분식", "AORP")["score"], 7)  # 3점 x2 + 1

    def test_stars_come_first(self):
        self.assertEqual(taste.adjusted_stars(5, -1), 4.5)  # 후기는 반 별만 움직인다
        self.assertEqual(taste.adjusted_stars(5, 1), 5)
        self.assertEqual(taste.adjusted_stars(1, -1), 1)
        self.assertEqual(taste.adjusted_stars(3, 0), 3)

    def test_dates(self):
        for value in ("2026-11-25 12:20", "2026-11-25T12:20:00+09:00", "2026-11-25", "2026/11/25",
                      "2026.11.25", "2026-11-25 12:20:05", "2026-11-25T03:20:00Z"):
            self.assertEqual(taste.read_date(value), date(2026, 11, 25), value)
        for value in ("어제", "", None, "25/11/2026"):
            self.assertIsNone(taste.read_date(value), value)

    def test_josa(self):
        self.assertEqual(taste.josa("국밥", "은", "는"), "국밥은")
        self.assertEqual(taste.josa("튀김·까스", "은", "는"), "튀김·까스는")
        self.assertEqual(taste.josa("면", "이에요", "예요"), "면이에요")


class ProfileTest(unittest.TestCase):
    def test_profile(self):
        p = sample_profile()
        self.assertEqual(p["기록수"], 9)
        self.assertEqual(p["종류별"]["면"], {"횟수": 3, "평균별점": 4.5})  # 별점 4 + 좋은 후기
        self.assertEqual(p["좋아하는종류"][0], "국밥·탕")
        self.assertEqual(p["덜좋아하는종류"], ["분식"])
        self.assertEqual(p["최근"], [{"며칠전": 1, "가게": "동성로 라멘", "종류": "면"}])
        self.assertIn("양 넉넉", p["자주고른포인트"])

    def test_future_and_unknown_store(self):
        diary = [{"날짜": "2026-11-27 12:00", "가게": "A 국밥집", "별점": 1, "후기": ""},
                 {"날짜": "2026-11-26 12:00", "가게": "처음 보는 집", "별점": 3, "후기": ""}]
        p = taste.build_profile(diary, {}, TODAY)
        self.assertEqual(p["기록수"], 1)  # 내일 날짜는 빼기
        self.assertEqual(p["가게별"]["처음 보는 집"]["종류"], "기타")
        self.assertNotIn("후순위", taste.opinion(p))  # 기타는 겹침 판단 안 함

    def test_bad_entries_are_skipped(self):
        diary = [{"날짜": "이상한 날짜", "가게": "x", "별점": 5},
                 {"날짜": "2026-11-20", "가게": "x", "별점": 9},
                 {"날짜": "2026-11-20", "가게": "", "별점": 3},
                 {"날짜": "2026-11-20T12:00:00+09:00", "가게": "A 국밥집", "별점": 4}]
        p = taste.build_profile(diary, {"A 국밥집": "국밥·탕"}, TODAY)
        self.assertEqual((p["기록수"], p["읽지못한일기"]), (1, 3))
        self.assertIn("3개는 빼고", taste.opinion(p))

    def test_unknown_store_lowers_certainty(self):
        diary = [{"날짜": "2026-11-25 12:00", "가게": "새로 생긴 라멘", "별점": 4},
                 {"날짜": "2026-11-01 12:00", "가게": "B 라멘집", "별점": 4}]
        p = taste.build_profile(diary, {"B 라멘집": "면"}, TODAY)
        self.assertEqual(p["종류를모르는가게"], ["새로 생긴 라멘"])
        self.assertEqual(taste.score(p, "B 라멘집", "면")["확실도"], "중간")
        self.assertIn("몰라서 겹치는지 확인하지 못했어요", taste.opinion(p))
        self.assertIn("몰라서", taste.reply(p, "거리", "B 라멘집", "면")["message"])

    def test_opinion(self):
        text = taste.opinion(sample_profile())
        self.assertIn("국밥·탕을 좋아하세요", text)
        self.assertIn("어제 동성로 라멘에서 면을 드셨어요. 면은 후순위로 할게요.", text)
        self.assertEqual(taste.opinion(taste.build_profile([], {}, TODAY)),
                         "아직 혼밥일기가 없어서 취향을 판단할 수 없어요.")


class ScoreTest(unittest.TestCase):
    def test_example_scores(self):
        p = sample_profile()
        self.assertEqual(taste.score(p, "A 국밥집", "국밥·탕")["score"], 10)   # 가게 기록 5점
        self.assertEqual(taste.score(p, "B 라멘집", "면")["score"], 6)         # 면 4.5점 x2 - 어제 3
        d = taste.score(p, "D 돈까스집", "튀김·까스")
        self.assertEqual((d["score"], d["confirmed"], d["확실도"]), (6, False, "낮음"))  # 기록 없음 = 기본 6점

    def test_penalty_by_day(self):
        diary = [{"날짜": f"2026-11-{day} 12:00", "가게": "x", "별점": 5, "후기": ""}
                 for day in (10, 11, 12)]
        stores = {"x": "면"}
        for day, expected in ((26, 7), (25, 7), (24, 9), (23, 10)):  # 오늘·어제 -3, 그제 -1
            p = taste.build_profile([dict(diary[0], 날짜=f"2026-11-{day} 12:00")] + diary, stores, TODAY)
            self.assertEqual(taste.score(p, "새 면집", "면")["score"], expected, day)

    def test_reply(self):
        p = sample_profile()
        self.assertIs(taste.reply(p, "거리", "B 라멘집", "면")["fits"], False)
        self.assertIs(taste.reply(p, "거리", "A 국밥집", "국밥·탕")["fits"], True)
        self.assertIsNone(taste.reply(p, "거리", "D 돈까스집", "튀김·까스")["fits"])
        self.assertIs(taste.reply(p, "거리", "중앙로 김밥", "분식")["fits"], False)


class RebutTest(unittest.TestCase):
    def test_rebut(self):
        p = sample_profile()
        r = taste.rebut(p, "거리", "B 라멘집", "면", "A 국밥집", "국밥·탕")
        self.assertEqual((r["stance"], r["확실도"]), ("반대", "높음"))
        self.assertIn("어제에 이어 또 면이에요", r["message"])
        self.assertIn("A 국밥집을 지지합니다", r["message"])

        r = taste.rebut(p, "날씨", "A 국밥집", "국밥·탕", "B 라멘집", "면")
        self.assertEqual(r["stance"], "동의")

        r = taste.rebut(p, "거리", "B 라멘집", "면", "A 국밥집", "국밥·탕", hurry=True)
        self.assertEqual(r["stance"], "동의")
        self.assertIn("급하시면 B 라멘집도 괜찮아요. 다만", r["message"])

        r = taste.rebut(p, "예산", "D 돈까스집", "튀김·까스", "C 찌개집", "찌개")
        self.assertEqual(r["stance"], "판단 안 함")

        r = taste.rebut(p, "예산", "교동 돼지국밥", "국밥·탕", "A 국밥집", "국밥·탕")
        self.assertEqual(r["stance"], "판단 안 함")  # 9점 대 10점: 차이가 작음


class RefreshTest(unittest.TestCase):
    def test_daily_refresh(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in (taste.DIARY, taste.STORES):
                shutil.copy(os.path.join(taste.FOLDER, name), folder)
            first = taste.load_profile(folder, TODAY)
            self.assertEqual(first["만든날"], "2026-11-26")

            # 같은 날에는 저장된 요약표를 그대로 쓴다
            path = os.path.join(folder, taste.PROFILE)
            with open(path, encoding="utf-8") as file:
                saved = json.load(file)
            saved["기록수"] = 999
            with open(path, "w", encoding="utf-8") as file:
                json.dump(saved, file, ensure_ascii=False)
            self.assertEqual(taste.load_profile(folder, TODAY)["기록수"], 999)

            # 다음 날에는 혼밥일기를 다시 읽는다
            nxt = taste.load_profile(folder, date(2026, 11, 27))
            self.assertEqual((nxt["만든날"], nxt["기록수"]), ("2026-11-27", 9))
            self.assertEqual(nxt["최근"][0]["며칠전"], 2)  # 라멘은 이제 그제

    def test_wrong_category(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, taste.STORES), "w", encoding="utf-8") as file:
                file.write("가게,음식종류\nx,라멘\n")
            with self.assertRaises(ValueError):
                taste.load_stores(folder)


if __name__ == "__main__":
    unittest.main()
