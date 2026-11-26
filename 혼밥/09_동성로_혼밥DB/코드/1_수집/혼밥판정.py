"""동성로 혼밥 판정 (사용자 결정 2026-11-25 저녁). 모은 값은 바꾸지 않고 최종 판정과 이유를 붙인다.

1 혼밥 좋음   : 같은 가게를 찾았고, N인분이 아니고, '혼밥하기 좋아요' 5명 이상 (1인분이 확인되지 않아도)
2 1인분 됨    : 1인분인데 5명 미만이거나 숫자 없음
3 혼밥 어려움 : N인분 (혼밥 수가 많아도)
4 모름        : 나머지 (못 찾음·애매 포함)
주요 메뉴가 모두 소·중·대·세트뿐이면 값과 상관없이 N인분이다.
(11-25의 '가장 싼 크기 메뉴 15,000원 이하면 1인분(추정)' 규칙은 11-26 사용자 결정 '없애'로 뺐다. cheap_size는 참고용으로만 남김.)
"""
import re

KEY, CHEAP = 5, 15000
LUNCH = re.compile(r"점심|런치|특선")


def cheap_size(evidence, dishes):
    """크기·세트로 파는 요리의 가장 싼 값. 단품·곁들임·점심특선 값은 보지 않는다. 없으면 None."""
    v = [int(m["가격_원"]) for m in dishes
         if str(m["가격_원"]).isdigit() and not m["곁들임일_수_있음"] and not LUNCH.search(m["요리명"])
         and (m["가격_단위"] == "크기·세트" or re.search(r"\d+\s*종", m["요리명"]))]
    if not LUNCH.search(evidence):
        v += [int(x.replace(",", "")) for x in re.findall(r"(?<![\d,])(\d{1,3}(?:,\d{3})+)\s*원", evidence)]
    return min(v) if v else None


def decide(found, order, n, sure, evidence, solo, dishes):
    """(주문, N, 확실한 정도, 혼밥 판정, 이유, 따로 볼 것 목록)"""
    flag = []
    if found != "예":
        amb = found == "애매"
        return "모름", "", sure, "4 모름", "같은 가게인지 애매함" if amb else "지도에서 못 찾음", ["같은 가게인지 확인"] if amb else []
    many = solo is not None and solo >= KEY
    if order == "N인분":
        if many and sure == "크기·세트뿐":
            flag.append("N인분(크기·세트)인데 혼밥이 많음")
        return order, n, sure, "3 혼밥 어려움", f"{n}인분부터" if n.isdigit() else "크기·세트뿐(몇 인분부터인지 미확인)", flag
    level = "확인됨" if sure.startswith("확인됨") else "추정"
    if many:
        return order, n, sure, "1 혼밥 좋음", (f"1인분 {level}" if order == "1인분" else "1인분은 확인 안 됨") + f", 혼밥하기 좋아요 {solo}", flag
    if order == "1인분":
        return order, n, sure, "2 1인분 됨", f"1인분 {level}, 혼자 오는 손님은 확인 안 됨", flag
    return order, n, sure, "4 모름", sure or "근거 없음", flag
