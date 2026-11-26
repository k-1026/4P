"""메뉴 풀기 테스트. 실행: python test_menu_parse.py  (예시는 실제 데이터에서 가져옴)"""
from menu_parse import parse_menus, pick_signature, split_daegufood, split_form


def menus_daegufood(mnu):
    return parse_menus(split_daegufood(mnu))


def test_basic_price():
    r = menus_daegufood("계란김밥 8,000원 <br />차돌깻잎국수 12,000원<br />")
    assert [(x["메뉴명"], x["가격"]) for x in r] == [("계란김밥", 8000), ("차돌깻잎국수", 12000)]


def test_range():
    r = menus_daegufood("아귀찜 45,000원~60,000원<br />")
    assert (r[0]["가격"], r[0]["가격_최대"], r[0]["가격종류"]) == (45000, 60000, "범위")
    r = menus_daegufood("월남쌈 30,000 ~ 39,000원")
    assert (r[0]["메뉴명"], r[0]["가격"], r[0]["가격_최대"]) == ("월남쌈", 30000, 39000)


def test_size_in_name():
    r = menus_daegufood("왕족발(소) 25,000원 <br />왕족발(중) 30,000원")
    assert [(x["메뉴명"], x["크기"]) for x in r] == [("왕족발(소)", "소"), ("왕족발(중)", "중")]


def test_many_sizes_one_item():
    r = menus_daegufood("오리양념주물럭 (중)30,000원 (대)35,000원")
    assert [(x["메뉴명"], x["크기"], x["가격"]) for x in r] == [
        ("오리양념주물럭", "중", 30000), ("오리양념주물럭", "대", 35000)]


def test_serving():
    r = parse_menus(split_form("옻닭 10,000원; 추어탕 8,000원; 추어탕 A(2인상) 30,000원"))
    assert [x["인분"] for x in r] == ["", "", "2인"]
    assert parse_menus(["은복불고기(1인분) 16,000원"])[0]["인분"] == "1인분"
    assert parse_menus(["13첩 정식 2인부터 15,000원"])[0]["인분"] == "2인분부터"


def test_skip_description_and_category():
    assert menus_daegufood("[테라스스시뷔페]는 스시 뷔페 전문점으로 다양한 초밥을 즐길 수 있는 음식점입니다.") == []
    assert parse_menus(split_form("한식")) == []
    assert [x["메뉴명"] for x in parse_menus(split_form("돈까스,우동"))] == ["돈까스", "우동"]
    assert [x["메뉴명"] for x in parse_menus(split_form("아구찜(소),중,대"))] == ["아구찜(소)"]


def test_price_change_word():
    r = parse_menus(split_form("단체도시락 가격 변동; 아메리칸 햄치즈샌드위치 5,800원"))
    assert (r[0]["메뉴명"], r[0]["가격종류"]) == ("단체도시락", "변동")


def test_side_flag():
    r = menus_daegufood("돼지국밥 9,000원<br />공기밥 1,000원<br />순대 추가 3,000원")
    assert [x["곁들이"] for x in r] == ["", "Y", "Y"]


def test_signature_store_name():
    r = menus_daegufood("순대국밥 9,500원<br />돼지국밥 9,000원")
    i, why = pick_signature("할매돼지국밥 본점", r)
    assert (r[i]["메뉴명"], why) == ("돼지국밥", "가게이름")


def test_signature_first_menu():
    r = menus_daegufood("공기밥 1,000원<br />된장찌개 9,000원<br />김치찌개 9,000원")
    i, why = pick_signature("매일식당", r)
    assert (r[i]["메뉴명"], why) == ("된장찌개", "메뉴판첫번째")


def test_signature_skips_price_change():
    r = parse_menus(split_form("단체도시락 가격 변동; 선샤인 샌드위치 6,300원"))
    i, _ = pick_signature("샌드선샤인", r)
    assert r[i]["메뉴명"] == "선샤인 샌드위치"


def test_signature_none():
    assert pick_signature("아무식당", []) == (None, "")


if __name__ == "__main__":
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("통과", name)
        except AssertionError as e:
            failed += 1
            print("실패", name, e)
    print(f"\n{len(tests) - failed}/{len(tests)} 통과")
    raise SystemExit(1 if failed else 0)
