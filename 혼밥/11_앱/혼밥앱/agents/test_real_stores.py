"""실제 가게 데이터(혼밥DB) 변환 시험: python -m unittest test_real_stores"""
import os
import unittest

import real_stores


@unittest.skipUnless(os.path.exists(real_stores.DB), "혼밥DB 파일이 없어요")
class RealStoresTest(unittest.TestCase):
    def test_usable_menu(self):
        self.assertTrue(real_stores.usable({"name": "순대국", "price": 9000, "unit": "단품", "side": False}))
        self.assertFalse(real_stores.usable({"name": "찜닭 반마리", "price": 31000, "unit": "크기·세트", "side": False}))
        self.assertFalse(real_stores.usable({"name": "삼겹살", "price": 15000, "unit": "무게", "side": False}))
        self.assertFalse(real_stores.usable({"name": "공기밥 별도", "price": 1000, "unit": "단품", "side": True}))
        self.assertFalse(real_stores.usable({"name": "가격 모름", "price": None, "unit": "단품", "side": False}))

    def test_price_menus_skip_sets_and_sides(self):
        stores, _ = real_stores.load()
        menus, _ = real_stores.menus()
        names = {m["name"] for items in menus.values() for m in items}
        for s in stores:
            for m in s["menus"]:
                if (m["side"] or m["unit"] not in (None, "단품")) and m["name"] != s["menu"]:
                    self.assertNotIn(m["name"], names, f"{s['name']}의 {m['name']}이 가격 계산에 들어갔어요")

    def test_no_made_up_values(self):
        stores, _ = real_stores.app_stores()
        self.assertEqual(len(stores), 391)
        self.assertTrue(all(s["rate"] is None and s["seat"] is None and s["wait"] is None for s in stores))
        self.assertEqual(sum(s["verified"] for s in stores), 17)
        self.assertEqual(len({s["id"] for s in stores}), len(stores))


class Category(unittest.TestCase):
    def test_every_store_has_one_of_six(self):
        stores = real_stores.agent_stores({"lat": 35.869, "lng": 128.5955})
        self.assertEqual({s["category"] for s in stores}, set(real_stores.CATEGORIES))
        for upjong, expected in (("백반/한정식", "한식"), ("중국집", "중식"), ("일식 회/초밥", "일식"),
                                 ("경양식", "양식"), ("김밥/만두/분식", "분식"), ("베트남식 전문", "기타"), ("파스타/스테이크", "양식"),
                                 ("버거", "기타"), ("토스트/샌드위치/샐러드", "기타"),
                                 ("처음 보는 업종", "기타")):
            self.assertEqual(real_stores.category(upjong), expected)

    def test_only_chosen_category_is_recommended(self):
        import phone_app
        original = phone_app.rough_weather.prepare
        phone_app.rough_weather.prepare = staticmethod(lambda ctx: None)  # 날씨 API는 부르지 않는다
        try:
            result = phone_app.recommend({"location": {"lat": 35.869317, "lng": 128.597574}, "category": "중식"})
        finally:
            phone_app.rough_weather.prepare = original
        names = {s["name"] for s in real_stores.agent_stores({"lat": 35.869317, "lng": 128.597574})
                 if s["category"] == "중식"}
        self.assertTrue(result["table"])
        self.assertTrue({row["store"] for row in result["table"]} <= names)
        self.assertIn("중식 가게 중에서", result["text"])

    def test_nearest_twenty_of_the_category(self):
        import coordinator
        stores = real_stores.agent_stores({"lat": 35.869317, "lng": 128.597574})
        for name in real_stores.CATEGORIES:
            mine = [s for s in stores if s["category"] == name]
            within = sorted(s["dist_m"] for s in mine if s["dist_m"] <= coordinator.RADIUS_M)
            got = [s["dist_m"] for s in coordinator.pick_candidates(mine)]
            self.assertEqual(got, within[:20], name)


if __name__ == "__main__":
    unittest.main()
