"""매주 갱신 0단계: 공공데이터포털 '행정안전부_식품_일반음식점 조회서비스'에서 대구 중구 자료를 받아 CSV로 저장한다.
그 CSV를 인허가_비교.py --file 에 넣는다.

python -B -I 인허가_받기.py [--since 20261119] [--out 인허가_대구중구.csv]

- 주소(apis.data.go.kr/1741000/general_restaurants/info)와 조건 이름은 2026-11-26 포털의 API 안내 화면에서 확인함.
- 인증키: 포털에서 '활용신청'(자동승인)으로 받은 키. 환경변수 HONBAP_DATA_KEY 또는 이 폴더의 인증키.txt(한 줄).
  키는 깃에 올리지 않는다(.gitignore). 포털이 주는 두 키 중 '디코딩(Decoding)' 키를 넣는다.
- --since: 이 날짜 이후에 '바뀐' 자료만 받는다(새 인허가와 폐업이 모두 잡힘). 비우면 대구 중구 전체를 받는다(처음 한 번).
- --from-json: 시험용. 인터넷 없이 저장해 둔 응답 JSON 파일들로 CSV를 만든다.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://apis.data.go.kr/1741000/general_restaurants/info"
FIELDS = ["MNG_NO", "BPLC_NM", "LCPMT_YMD", "SALS_STTS_CD", "SALS_STTS_NM", "DTL_SALS_STTS_NM", "CLSBIZ_YMD", "ROAD_NM_ADDR", "LOTNO_ADDR",
          "BZSTAT_SE_NM", "OPN_ATMY_GRP_CD", "DAT_UPDT_SE", "DAT_UPDT_PNT", "CRD_INFO_X", "CRD_INFO_Y"]
PER = 100   # API 최대


def dotenv(name):
    """이 폴더의 .env에서 NAME=값 한 줄을 읽는다(따옴표는 벗김). 없으면 ''."""
    p = os.path.join(HERE, ".env")
    if not os.path.exists(p):
        return ""
    for line in open(p, encoding="utf-8-sig"):
        k, _, v = line.strip().partition("=")
        if k.strip() == name:
            return v.strip().strip("'\"")
    return ""


def url():
    return dotenv("RESTAURANT_API_URL") or URL


ADDR = ""   # --addr로 바꿀 수 있다(좌표 검사 등)


def region():
    return ADDR or dotenv("REGION_ADDR") or "대구광역시 중구"


def key():
    k = os.environ.get("HONBAP_DATA_KEY", "").strip() or dotenv("HONBAP_DATA_KEY")
    p = os.path.join(HERE, "인증키.txt")
    if not k and os.path.exists(p):
        k = open(p, encoding="utf-8").read().strip()
    if "%" in k:   # 인코딩된 키를 넣었으면 풀어서 쓴다(주소를 만들 때 다시 인코딩하므로)
        k = urllib.parse.unquote(k)
    if not k:
        raise SystemExit("인증키가 없음: 공공데이터포털 '행정안전부_식품_일반음식점 조회서비스' 활용신청 후 받은 디코딩 키를 이 폴더의 .env 파일 HONBAP_DATA_KEY= 뒤에 넣으세요.")
    return k


def items(doc):
    """응답 JSON에서 (가게 목록, 전체 수). 오류면 멈춘다."""
    r = doc.get("response", doc)
    head = r.get("header", {})
    if str(head.get("resultCode", "00")) not in ("00", "0", "INFO-000"):
        raise SystemExit(f"API 오류: {head.get('resultCode')} {head.get('resultMsg')}")
    body = r.get("body", {})
    it = (body.get("items") or {})
    it = it.get("item", []) if isinstance(it, dict) else it
    if isinstance(it, dict):
        it = [it]
    return it, int(body.get("totalCount") or 0)


def fetch(page, since):
    q = {"serviceKey": key(), "pageNo": page, "numOfRows": PER, "returnType": "json", "cond[ROAD_NM_ADDR::LIKE]": region()}
    if since:
        q["cond[DAT_UPDT_PNT::GTE]"] = since + "000000"
    full = url() + "?" + urllib.parse.urlencode(q)
    for n in range(3):
        try:
            with urllib.request.urlopen(full, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except (OSError, ValueError) as e:
            if n == 2:
                raise SystemExit(f"받기 실패({page}쪽): {type(e).__name__}")
            time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="", help="YYYYMMDD")
    ap.add_argument("--out", default=os.path.join(HERE, "인허가_대구중구.csv"))
    ap.add_argument("--from-json", nargs="*", default=None)
    ap.add_argument("--addr", default="", help="주소에 들어갈 글자(비우면 .env의 REGION_ADDR)")
    a = ap.parse_args()
    global ADDR
    ADDR = a.addr
    since = "".join(ch for ch in a.since if ch.isdigit())[:8]
    rows = []
    if a.from_json is not None:
        for p in a.from_json:
            rows += items(json.load(open(p, encoding="utf-8")))[0]
    else:
        page, total = 1, None
        while True:
            got, total = items(fetch(page, since))
            rows += got
            print(f"{page}쪽 {len(got)}줄 (모두 {total})", flush=True)
            if not got or len(rows) >= total:
                break
            page += 1
            time.sleep(0.5)
    rows = [r for r in rows if "중구" in (r.get("ROAD_NM_ADDR") or "") and "대구" in (r.get("ROAD_NM_ADDR") or "")]
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows({k: ("" if r.get(k) is None else r.get(k)) for k in FIELDS} for r in rows)
    print(f"대구 중구 {len(rows)}줄 → {a.out}")


if __name__ == "__main__":
    main()
