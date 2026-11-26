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
        self.assertEqual(len(stores), 276)
        self.assertTrue(all(s["rate"] is None and s["seat"] is None and s["wait"] is None for s in stores))
        self.assertEqual(sum(s["verified"] for s in stores), 18)
        self.assertEqual(len({s["id"] for s in stores}), len(stores))


if __name__ == "__main__":
    unittest.main()
