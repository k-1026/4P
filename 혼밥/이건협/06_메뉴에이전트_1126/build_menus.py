"""메뉴 갱신 에이전트 1단계: 메뉴 표 + 대표메뉴 만들기.

입력 (식당목록/ 폴더, 혼밥/07_챗봇/식당목록 과 같은 파일):
  - 대구푸드_맛집DB_905곳.json   (MNU 칸)
  - *수집양식*.csv                (대표메뉴 칸)

출력 (결과/ 폴더):
  - menus.csv            메뉴 한 줄 = 한 행. 대표메뉴에는 대표메뉴=Y
  - stores_signature.csv 가게 한 곳 = 한 행. 가격 에이전트가 바로 쓰는 대표메뉴·대표가격

실행:  python build_menus.py            (식당목록/ 읽기)
       python build_menus.py --src 폴더  (다른 폴더 읽기)
"""
import argparse
import csv
import glob
import json
import os
from collections import Counter

from menu_parse import parse_menus, pick_signature, split_daegufood, split_form

HERE = os.path.dirname(os.path.abspath(__file__))

MENU_COLS = ["store_id", "상호", "구군", "주소", "출처", "순서", "메뉴명", "가격", "가격_최대",
             "가격종류", "크기", "인분", "곁들이", "대표메뉴", "대표_근거", "확인일", "원문"]
STORE_COLS = ["store_id", "상호", "구군", "주소", "출처", "대표메뉴", "대표가격", "대표_근거",
              "메뉴수", "확인일"]


def col(row, prefix):
    """'대표메뉴', '최소주문_판정(…)'처럼 칸 이름 앞부분으로 값을 찾는다."""
    for k, v in row.items():
        if k and k.strip().startswith(prefix):
            return (v or "").strip()
    return ""


def load_stores(src):
    stores = []
    path = os.path.join(src, "대구푸드_맛집DB_905곳.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for x in json.load(f):
                stores.append({
                    "store_id": "F" + str(x["OPENDATA_ID"]), "상호": x["BZ_NM"], "구군": x["gu"],
                    "주소": x["GNG_CS"], "출처": "대구푸드", "확인일": "",
                    "parts": split_daegufood(x["MNU"]),
                })
    for path in sorted(glob.glob(os.path.join(src, "*수집양식*.csv"))):
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                stores.append({
                    "store_id": col(r, "수집ID"), "상호": col(r, "상호"), "구군": col(r, "구군"),
                    "주소": col(r, "도로명주소"), "출처": "수집양식:" + os.path.basename(path),
                    "확인일": col(r, "확인일"), "parts": split_form(col(r, "대표메뉴")),
                })
    return stores


def build(src, out):
    os.makedirs(out, exist_ok=True)
    menu_rows, store_rows = [], []
    why = Counter()

    for s in load_stores(src):
        rows = parse_menus(s.pop("parts"))
        idx, reason = pick_signature(s["상호"], rows)
        why[reason or "대표메뉴 없음"] += 1
        for i, r in enumerate(rows):
            r.update(s)
            r["대표메뉴"] = "Y" if i == idx else ""
            r["대표_근거"] = reason if i == idx else ""
            menu_rows.append(r)
        sig = rows[idx] if idx is not None else {}
        store_rows.append(dict(s, 대표메뉴=sig.get("메뉴명", ""), 대표가격=sig.get("가격", ""),
                               대표_근거=reason, 메뉴수=len(rows)))

    for name, cols, data in (("menus.csv", MENU_COLS, menu_rows),
                             ("stores_signature.csv", STORE_COLS, store_rows)):
        with open(os.path.join(out, name), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(data)

    priced = sum(1 for s in store_rows if s["대표가격"] != "")
    print(f"가게 {len(store_rows)}곳 · 메뉴 {len(menu_rows)}줄")
    print(f"대표메뉴 있음 {len(store_rows) - why['대표메뉴 없음']}곳 (그중 가격 있음 {priced}곳)")
    for k, v in why.most_common():
        print(f"  {k}: {v}")
    print("결과:", os.path.abspath(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "식당목록"))
    ap.add_argument("--out", default=os.path.join(HERE, "결과"))
    a = ap.parse_args()
    build(a.src, a.out)
