"""
소상공인시장진흥공단 상가(상권)정보 API - 대구 전체 음식점 목록을 CSV로 저장

실행 전:
  pip install requests

인증키는 코드에 쓰지 말고 환경변수로 넣습니다.
  Windows(명령 프롬프트):  set DATA_GO_KR_KEY=여기에_인증키
  Windows(PowerShell):     $env:DATA_GO_KR_KEY="여기에_인증키"
  Mac/Linux:               export DATA_GO_KR_KEY=여기에_인증키

실행:
  python sangga_daegu_all.py

결과: 같은 폴더에 sangga_daegu_all_food.csv 생성
"""
import csv
import os
import sys

import requests

KEY = os.environ.get("DATA_GO_KR_KEY")
if not KEY:
    sys.exit("환경변수 DATA_GO_KR_KEY에 인증키를 넣어 주세요.")

URL = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"
SIGUNGU_CODE = "27"     # 대구광역시 전체 (시도 코드)
FOOD_CODE = "I2"        # 업종 대분류: 음식 (오류가 나면 아래 params에서 이 줄을 빼고 다시 실행)
ROWS = 1000

out = []
page = 1
while True:
    params = {
        "serviceKey": KEY,
        "divId": "ctprvnCd",
        "key": SIGUNGU_CODE,
        "indsLclsCd": FOOD_CODE,
        "numOfRows": ROWS,
        "pageNo": page,
        "type": "json",
    }
    res = requests.get(URL, params=params, timeout=30)
    if res.status_code != 200:
        sys.exit(f"HTTP {res.status_code}: {res.text[:300]}")
    try:
        data = res.json()
    except ValueError:
        sys.exit("JSON이 아닌 응답이 왔습니다. 앞부분:\n" + res.text[:500])

    header = data.get("header", {})
    body = data.get("body", {})
    if header.get("resultCode") not in ("00", None):
        sys.exit(f"API 오류: {header}")

    items = body.get("items") or []
    out.extend(items)
    total = int(body.get("totalCount", 0))
    print(f"{page}페이지: {len(items)}건 (누적 {len(out)} / 전체 {total})")
    if not items or len(out) >= total:
        break
    page += 1

if not out:
    sys.exit("받은 데이터가 없습니다. 위 출력 내용을 Claude에게 보내 주세요.")

fields = list(out[0].keys())
with open("sangga_daegu_all_food.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(out)

print(f"저장 완료: sangga_daegu_all_food.csv ({len(out)}건)")
print("필드:", ", ".join(fields))
