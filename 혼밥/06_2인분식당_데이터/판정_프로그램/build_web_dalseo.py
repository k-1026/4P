"""달서구 웹데이터 초안(v0)을 만든다. 규칙: 매칭도구/작업기록_20261124_웹데이터_달서구/웹데이터_판정규칙_v0.md

python -I 매칭도구/build_web_dalseo.py --root . --out 원본자료/웹데이터_달서구_v0_20261124.csv

입력(읽기만, --root 아래 원본자료/):
  달서구_음식점_전체_202609.csv            바탕 가게 목록 (상가업소번호, 좌표)
  대구_2인분후보업종_202609.csv            '2인분 의심' 갈래 (프로젝트 기존 정의)
  2인분식당_최종판정_대구전역_20261124.csv  기존 판정 (수집ID)
  2인분식당_수집양식_대구전역표본_사전입력.csv  수집ID → 관리번호(인허가)
  가게목록_표본_상권정보연결_202609.csv    관리번호 → 상가업소번호
  2인분식당_수집양식_대구전역표본_판정_Aside_20261123.csv  1차 확인일
"""
import argparse
import csv
import os
from collections import Counter

EXCLUDE = {"카페", "빵/도넛", "일반 유흥 주점", "무도 유흥 주점", "구내식당", "떡/한과", "아이스크림/빙수", "생맥주 전문"}
ONE_BOWL = {
    "백반/한정식", "국/탕/찌개류", "김밥/만두/분식", "국수/칼국수", "냉면/밀면", "중국집",
    "일식 카레/돈가스/덮밥", "일식 면 요리", "경양식", "버거", "토스트/샌드위치/샐러드", "베트남식 전문",
    "파스타/스테이크", "전/부침개", "기타 한식 음식점", "기타 서양식 음식점", "그 외 기타 간이 음식점",
}
JUDGED = {  # 기존 판정 → (1인분_여부, 근거_수준)
    "2인분이상_확정": ("2인분 이상", "확인됨"),
    "2인분이상_추정": ("2인분 이상", "추정"),
    "1인분가능_확정": ("1인분 가능", "확인됨"),
}
ENTRY = {"가능": "가능", "불가": "불가"}
TYPE = {
    ("1인분 가능", "가능"): "① 혼밥 가능",
    ("1인분 가능", "불가"): "② 1인분 있지만 혼자 불가",
    ("1인분 가능", "모름"): "1인분 가능 (혼자 입장 모름)",
    ("2인분 이상", "가능"): "③ 혼자 가서 2인분 주문",
    ("2인분 이상", "불가"): "④ 혼밥 불가",
    ("2인분 이상", "모름"): "2인분 이상 (혼자 입장 모름)",
    ("모름", "가능"): "혼자 입장 가능 (1인분 모름)",
    ("모름", "불가"): "혼자 입장 불가 (1인분 모름)",
    ("모름", "모름"): "모름",
}
COLS = ["상가업소번호", "상호", "지점명", "업종_중분류", "업종_소분류", "업종_갈래", "행정동", "도로명주소", "층정보", "위도", "경도",
        "1인분_여부", "근거_수준", "조건_인분", "조건_범위", "혼자_입장", "시간대_제한", "혼밥_유형",
        "근거_URL1", "근거_URL2", "판정_출처", "확인일", "내부_수집ID"]


def rd(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    D = lambda n: os.path.join(a.root, "원본자료", n)

    base = rd(D("달서구_음식점_전체_202609.csv"))
    cand = {r["상가업소번호"] for r in rd(D("대구_2인분후보업종_202609.csv")) if r["시군구명"] == "달서구"}
    pre = {r["수집ID"]: r["관리번호(인허가)"] for r in rd(D("2인분식당_수집양식_대구전역표본_사전입력.csv"))}
    first = {r["수집ID"]: r["확인일"] for r in rd(D("2인분식당_수집양식_대구전역표본_판정_Aside_20261123.csv"))}
    link = {}
    for r in rd(D("가게목록_표본_상권정보연결_202609.csv")):
        if r["상가업소번호"]:
            link.setdefault(r["관리번호"], r["상가업소번호"])

    judged, dup = {}, []
    for r in rd(D("2인분식당_최종판정_대구전역_20261124.csv")):
        if r["구군"] != "달서구":
            continue
        sno = link.get(pre.get(r["수집ID"], ""))
        if not sno:
            continue
        if sno in judged:
            dup.append((sno, judged[sno]["수집ID"], r["수집ID"]))
            continue
        judged[sno] = r

    out, ids = [], set()
    for b in base:
        sno = b["상가업소번호"]
        sub = b["상권업종소분류명"]
        if sno in ids:
            raise SystemExit(f"상가업소번호 중복: {sno}")
        if sub in EXCLUDE and sno not in cand:
            continue
        ids.add(sno)
        group = "2인분 의심" if sno in cand else ("한 그릇 업종" if sub in ONE_BOWL else "그 밖")
        row = dict(상가업소번호=sno, 상호=b["상호명"], 지점명=b["지점명"], 업종_중분류=b["상권업종중분류명"].strip(),
                   업종_소분류=sub, 업종_갈래=group, 행정동=b["행정동명"], 도로명주소=b["도로명주소"], 층정보=b["층정보"],
                   위도=b["위도"], 경도=b["경도"], 조건_인분="", 조건_범위="", 시간대_제한="",
                   근거_URL1="", 근거_URL2="", 확인일="", 내부_수집ID="")
        j = judged.get(sno)
        entry = "모름"
        if j:
            entry = ENTRY.get(j["최종_1인입장"], "모름")
            row.update(시간대_제한=j["최종_시간대제한"], 근거_URL1=j["근거1_URL"], 근거_URL2=j["근거2_URL"], 내부_수집ID=j["수집ID"])
            path = j["판정경로"]
            if path.startswith("달서구 최종"):
                row.update(판정_출처="달서구 표본 11-21", 확인일="2026-11-21")
            else:
                row.update(판정_출처="대구 표본 11-24", 확인일="2026-11-24" if path.startswith("손확인") else first.get(j["수집ID"], ""))
        if j and j["최종_최소주문"] in JUDGED:
            yn, lv = JUDGED[j["최종_최소주문"]]
            row.update({"1인분_여부": yn, "근거_수준": lv})
            if yn == "2인분 이상":
                row.update(조건_인분=j["최종_인분"], 조건_범위=j["최종_범위"])
        elif group == "한 그릇 업종":
            row.update({"1인분_여부": "1인분 가능", "근거_수준": "업종 기준"})
            if not j:
                row["판정_출처"] = "업종 기준"
        else:
            row.update({"1인분_여부": "모름", "근거_수준": "없음"})
            if not j:
                row["판정_출처"] = "없음"
        row["혼자_입장"] = entry
        row["혼밥_유형"] = TYPE[(row["1인분_여부"], entry)]
        out.append(row)

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out)

    print(f"{len(out)}곳 -> {a.out}  (기존 판정 연결 {sum(1 for r in out if r['내부_수집ID'])}곳)")
    for sno, k1, k2 in dup:
        print(f"  같은 상가업소번호 {sno}: {k1} 사용, {k2} 건너뜀")
    print("업종_갈래:", dict(Counter(r["업종_갈래"] for r in out)))
    print("1인분_여부×근거_수준:", dict(Counter((r["1인분_여부"], r["근거_수준"]) for r in out)))
    print("혼밥_유형:", dict(Counter(r["혼밥_유형"] for r in out)))


if __name__ == "__main__":
    main()
