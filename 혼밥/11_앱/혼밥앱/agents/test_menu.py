"""메뉴 에이전트: 가게 메뉴를 읽고 정리해서 다른 에이전트에게 알려 주는지 시험한다."""
import json
import os
import tempfile
import types
import unittest
from datetime import datetime

import menu_agent

NOW = datetime(2026, 11, 26, 12, 0)
STORES = [
    {"id": "A", "name": "A 국밥집", "cat": "국밥", "menu": "순대국", "price": 9000, "soup": True},
    {"id": "C", "name": "C 찌개집", "cat": "한식", "menu": "김치찌개", "price": 9000, "soup": True},
    {"id": 7, "name": "냉면집", "cat": "한식", "menu": "물냉면", "price": 10000, "soup": False},
]
MENUS = {
    "A": [{"name": "순대국", "price": 9000, "soup": True}, {"name": "내장탕", "price": 10000, "soup": True}],
    "C": [{"name": "김치찌개 (2인)", "price": 18000, "soup": True}],
}


def shared(menus=MENUS, stores=STORES):
    state = menu_agent.prepare({"now": NOW, "menus": menus})
    return menu_agent.share(state, stores, {"now": NOW})


class ShareTest(unittest.TestCase):
    def test_attaches_menu_list(self):
        stores, said = shared()
        a = stores[0]
        self.assertEqual([m["name"] for m in a["menus"]], ["순대국", "내장탕"])
        self.assertEqual(a["menu"], "순대국")  # 첫 메뉴가 대표 메뉴
        self.assertEqual((a["price_min"], a["price_avg"], a["price_max"]), (9000, 9500, 10000))
        self.assertTrue(a["soup"])
        self.assertEqual(a["kind"], "국밥·탕")
        self.assertEqual(a["weather_type"], "따뜻한 국물")
        self.assertEqual(len(stores), 2)  # C 찌개집은 2인분 메뉴뿐이라 빠짐
        self.assertIn("2곳", said)
        self.assertIn("메뉴 3개", said)

    def test_fallback_to_main_menu(self):
        """메뉴 목록이 없는 가게는 가게 데이터의 대표 메뉴 하나로 알려 준다"""
        cold = shared()[0][1]
        self.assertEqual(cold["menus"], [{"name": "물냉면", "price": 10000, "soup": False}])
        self.assertTrue(cold["menu_from_main"])
        self.assertEqual(cold["kind"], "면")
        self.assertEqual(cold["weather_type"], "차가운 요리")

    def test_two_person_menus_are_removed(self):
        """혼밥 앱이라 2인분 이상 메뉴는 모두 뺀다. 1인 메뉴가 하나도 없는 가게(C)는 가게째 빠진다."""
        menus = {**MENUS, "A": MENUS["A"] + [{"name": "모둠순대 (2~3인)", "price": 20000}],
                 7: [{"name": "1인 냉면 세트", "price": 11000}, {"name": "냉면 2인 세트", "price": 19000}]}
        stores, said = shared(menus)
        self.assertEqual([s["name"] for s in stores], ["A 국밥집", "냉면집"])
        a, cold = stores
        self.assertEqual([m["name"] for m in a["menus"]], ["순대국", "내장탕"])
        self.assertEqual(a["removed_menus"], ["모둠순대 (2~3인)"])
        self.assertEqual(a["price_max"], 10000)       # 뺀 메뉴 가격은 가격 범위에 안 들어간다
        self.assertFalse(a["solo_menu"])              # 숫자가 없는 메뉴는 1인분으로 보지만 '1인 메뉴'는 아님
        self.assertTrue(cold["solo_menu"])
        self.assertEqual(cold["kind"], "면")          # 숫자 키(7)도 찾는다
        self.assertIn("C 찌개집", said)

    def test_people(self):
        for name, expected in {"순대국": 1, "1인 샤브": 1, "김치찌개 (2인)": 2, "모둠 2~3인": 2,
                               "3인 세트": 3, "1인분": 1}.items():
            self.assertEqual(menu_agent.people(name), expected, name)

    def test_main_menu_two_person(self):
        """메뉴 목록이 없고 대표 메뉴가 2인분인 가게도 뺀다"""
        state = menu_agent.prepare({"menus": {}})
        stores = [{"id": 1, "name": "부대찌개집", "menu": "부대찌개 2인분"}, {"id": 2, "name": "김밥집"}]
        kept, said = menu_agent.before_candidates(state, stores, {})
        self.assertEqual([s["name"] for s in kept], ["김밥집"])
        self.assertIn("부대찌개집", said)

    def test_before_candidates(self):
        """후보를 고르기 전에 1인 메뉴가 없는 가게를 전체 가게 데이터에서 뺀다"""
        state = menu_agent.prepare({"menus": MENUS})
        kept, said = menu_agent.before_candidates(state, STORES, {})
        self.assertEqual([s["name"] for s in kept], ["A 국밥집", "냉면집"])
        self.assertEqual(said, "1인 메뉴가 없는 1곳(C 찌개집)은 2인분부터라 후보에서 뺐어요.")
        self.assertEqual(menu_agent.before_candidates(state, STORES[:1], {}), (STORES[:1], ""))

    def test_does_not_change_input(self):
        before = json.dumps(STORES, ensure_ascii=False)
        shared()
        self.assertEqual(json.dumps(STORES, ensure_ascii=False), before)

    def test_no_score(self):
        """메뉴 에이전트는 알려만 준다: 점수·탈락·반론을 하지 않는다"""
        for name in ("score", "check", "rebut", "propose"):
            self.assertFalse(hasattr(menu_agent, name), name)
        self.assertEqual(menu_agent.opinion({}, {}), "")

    def test_describe(self):
        stores = shared({**MENUS, "A": MENUS["A"] + [{"name": "모둠순대 (2인)", "price": 20000}]})[0]
        self.assertEqual(menu_agent.describe({}, stores[0], {}), "순대국 외 1개 · 9,000~10,000원 (2인분 1개 뺌)")
        self.assertEqual(menu_agent.describe({}, stores[1], {}), "물냉면 · 10,000원")


class CoordinatorTest(unittest.TestCase):
    def test_two_person_store_never_becomes_candidate(self):
        """조율자가 후보를 고르기 전에 메뉴 에이전트가 빼서, 그 자리는 다음 가게가 채운다"""
        import coordinator
        rates = {"A": 4.5, "C": 4.9, 7: 4.0}
        stores = [{**s, "area": 0, "dist_m": 300, "rate": rates[s["id"]]} for s in STORES]
        scorer = types.SimpleNamespace(prepare=lambda ctx: {}, opinion=lambda state, ctx: "",
                                       score=lambda state, store, ctx: {"score": 5, "확실도": "중간", "why": ""})
        agents = [{"name": "거리", "weight": 20, "module": scorer},
                  {"name": "메뉴", "weight": 0, "module": menu_agent}]
        result = coordinator.run({"now": NOW, "menus": MENUS}, stores, agents, [])
        self.assertNotIn("C 찌개집", [row["store"]["name"] for row in result["ranking"]])
        self.assertIn("후보 2곳을 찾아봤어요: A 국밥집, 냉면집", result["text"])
        self.assertIn("C 찌개집", result["text"])  # 뺐다고 알려 줌


class FileTest(unittest.TestCase):
    def test_reads_menu_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, menu_agent.FILE), "w", encoding="utf-8") as file:
                json.dump({"7": [{"name": "비빔냉면", "price": 10000}]}, file, ensure_ascii=False)
            state = menu_agent.prepare({"now": NOW}, folder)
        self.assertEqual(state["menus"]["7"][0]["name"], "비빔냉면")
        self.assertTrue(state["updated"])
        stores, _ = menu_agent.share(state, STORES, {})
        self.assertEqual(stores[-1]["menu"], "비빔냉면")

    def test_no_file_or_broken_file(self):
        """파일이 없거나 깨져도 빠지지 않고 대표 메뉴로 알려 준다"""
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(menu_agent.prepare({}, folder)["menus"], {})
            with open(os.path.join(folder, menu_agent.FILE), "w", encoding="utf-8") as file:
                file.write("{깨진 파일")
            self.assertEqual(menu_agent.prepare({}, folder)["menus"], {})

    def test_bad_entries_are_skipped(self):
        state = menu_agent.prepare({"menus": {"A": [{"name": ""}, "순대국", {"name": "내장탕", "price": "비쌈"}]}})
        self.assertEqual(state["menus"]["A"], [{"name": "내장탕", "price": None, "soup": False}])


if __name__ == "__main__":
    unittest.main()
