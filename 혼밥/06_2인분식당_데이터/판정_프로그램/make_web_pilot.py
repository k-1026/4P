"""달서구 웹데이터 시범 100곳 지도 수집 지시문을 만든다.

python -I make_web_pilot.py --web 원본자료/웹데이터_달서구_v0_20261124.csv --outdir <폴더> [--seed 20261124]

뽑기: 기존 판정이 없는 가게 중 '2인분 의심' 50곳, '한 그릇 업종'+'그 밖' 50곳(두 갈래 곳 수 비율대로).
출력: 대상목록.csv, prompt_NN.txt (25곳씩), run_all.sh
지시문은 11-23 대구 전역 지도 수집(작업기록_20261123_대구전역/지도수집/head.txt)과 같고,
대표 메뉴 가격과 메뉴 정보 상태 두 칸을 더했다(한 그릇 단위 가격 규칙용).
"""
import argparse
import csv
import json
import os
import random

HEAD = """대구 식당을 한 곳씩 네이버 지도(map.naver.com, 플레이스)에서 확인하고, 카카오맵(map.kakao.com)에서도 확인해 줘.
목적: 이 식당이 매장에서 1인분(한 그릇·1인 메뉴)을 파는지, "2인분부터·2인 이상"처럼 혼자서는 주문할 수 없는 조건이 있는지, 혼자 오는 손님이 있는지의 근거를 모으는 것.
각 줄은 [수집ID, 상호, 도로명주소, 업종]이야. 상호+주소로 같은 가게인지 꼭 확인해(체인은 지점 주소까지).

가게마다 이 순서로 봐:
1) 메뉴 탭(네이버·카카오 둘 다): 메뉴 이름·설명에 "2인", "2인분", "2인 이상", "2인부터", "2~3인", "(소)/(중)/(대) 몇 인", "1인", "1인분", "1인 메뉴", "1인 1메뉴", "1인 세트", "혼밥", "나홀로"가 있는 줄을 원문 그대로 적어.
   - 대표 메뉴 1~3개는 이름과 가격을 화면에 적힌 그대로 대표메뉴 칸에 적어(예: "돼지국밥 9,000원; 순대국밥 10,000원"). 가격 옆에 "1인분", "(2인)", "소/중/대" 같은 말이 있으면 그것도 그대로.
   - 메뉴정보 칸: 가게가 직접 올린 매장 메뉴가 있으면 "매장메뉴", 배민·요기요·쿠팡이츠 같은 배달앱 메뉴만 있으면 "배달메뉴만", 메뉴가 전혀 없으면 "없음".
   - 그 메뉴가 배달앱 메뉴이면 근거_출처를 "네이버(배달메뉴)" 또는 "카카오(배달메뉴)"로 적어. 가게가 직접 올린 매장 메뉴는 "네이버" 또는 "카카오".
   - 메뉴 탭 글에서 위 낱말을 하나도 못 찾았을 때만 메뉴판 사진(메뉴판 이미지)을 1장 열어서 같은 낱말이 있는지 읽고, 있으면 원문을 적고 근거_출처를 "네이버(메뉴판사진)" 또는 "카카오(메뉴판사진)"로 적어. 메뉴 탭에서 이미 찾았으면 사진은 보지 마.
   - 해당 줄이 하나도 없으면 근거를 적지 말고 메모에 "메뉴에 인분 표기 없음"(또는 "메뉴 정보 없음").
2) 사장님 답글: 최근 리뷰 30개 정도의 사장님 답글에서 "1인", "혼자", "혼밥", "2인분", "2인 이상", "1인분", "1인 1메뉴"가 들어간 문장만 적어.
3) 방문자 리뷰: 최근 30개 정도에서 같은 낱말("혼자", "혼밥", "1인", "1인분", "1인 1메뉴", "2인분", "2인 이상", "2인부터", "혼자는 안")이 들어간 리뷰 문장을 최대 3개, 문장 하나(100자 안쪽)씩 적고 날짜(화면에 보이는 날짜)를 적어. 문장 없이 고른 키워드("혼밥하기 좋아요" 등)는 근거로 적지 말고 아래 키워드 칸에만 반영해.
4) 숫자 칸(네이버 방문자 리뷰 기준):
   - 확인한_리뷰수: 실제로 훑은 방문자 리뷰 수
   - 혼자_태그수: 그중 리뷰에 '혼자' 동행 태그가 붙은 리뷰 수
   - 동행태그_리뷰수: 그중 동행 태그(혼자·친구·연인·가족 등 아무거나)가 붙은 리뷰 수
   - 혼밥키워드수 / 키워드참여수: '이런 점이 좋았어요'의 "혼밥하기 좋아요" 수와 전체 참여 인원(안 보이면 비워)
5) 좌석: 가게 정보·편의시설·메뉴·리뷰에서 "1인석", "바 좌석", "바 테이블", "혼밥석", "1인 좌석", "칸막이"가 보이면 메모 칸 맨 앞에 "좌석: 보인 낱말"로 적어(예: "좌석: 바 좌석, 1인석"). 안 보이면 적지 마. 좌석을 찾으려고 따로 오래 뒤지지는 마.

지킬 것:
- 보이는 것만 적고 추측·해석·판정은 하지 마(판정은 내가 한다).
- 리뷰 작성자 이름·닉네임·프로필·사진은 절대 적지 마. 리뷰는 문장과 날짜만.
- 가게마다 몇 초씩 쉬어. 로그인이 필요한 화면이 나오면 그 가게는 건너뛰고 메모에 적어.
- 같은 가게를 못 찾으면 찾음=아니오로 적고 넘어가.

마지막 답은 CSV만, 머리줄 포함, 모든 칸을 따옴표로 감싸서. 근거마다 한 줄씩(수집ID 같게). 근거가 하나도 없으면 근거_종류를 "없음"으로 한 줄. 숫자 칸·대표메뉴·메뉴정보는 그 가게의 모든 줄에 같은 값.
머리줄: 수집ID,찾음(예/아니오),플랫폼_상호,대표메뉴,메뉴정보(매장메뉴/배달메뉴만/없음),근거_종류(메뉴표기/사장답글/방문자리뷰/없음),근거_출처,근거_원문,근거_작성일,근거_URL,확인한_리뷰수,혼자_태그수,동행태그_리뷰수,혼밥키워드수,키워드참여수,메모
입력:
"""

RUN = r"""#!/usr/bin/env bash
# 시범 지도 수집을 Aside로 PAR개씩 동시에 돌린다. 결과(CSV 머리줄)가 있는 묶음은 건너뛴다.
cd "$(dirname "$0")"
run_one() {
  p="$1"; i="${p#prompt_}"; i="${i%.txt}"
  out="out_${i}.csv"; err="err_${i}.txt"
  if [ -s "$out" ] && grep -q '"수집ID"' "$out"; then echo "건너뜀 $i"; return; fi
  aside exec --effort medium "$(cat "$p")" > "$out" 2> "$err"
  echo "끝 $i exit=$?"
}
export -f run_one
ls prompt_*.txt | xargs -P "${PAR:-4}" -I{} bash -c 'run_one "$@"' _ {}
echo "모두 끝"
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--seed", type=int, default=20261124)
    ap.add_argument("--per", type=int, default=25)
    ap.add_argument("--all", action="store_true", help="시범 대신 남은 가게 전부(기존 판정·--skip 목록 제외)")
    ap.add_argument("--skip", nargs="*", default=[], help="이미 수집한 대상목록.csv (시범 등)")
    a = ap.parse_args()
    with open(a.web, encoding="utf-8-sig", newline="") as f:
        R = [r for r in csv.DictReader(f) if not r["내부_수집ID"]]
    rnd = random.Random(a.seed)
    if a.all:
        done = set()
        for p in a.skip:
            with open(p, encoding="utf-8-sig", newline="") as f:
                done |= {r["수집ID"] for r in csv.DictReader(f)}
        pick = [r for r in R if r["상가업소번호"] not in done]
        rnd.shuffle(pick)   # 묶음마다 업종이 섞이게
        write(a, pick)
        print(f"전체 {len(pick)}곳 (제외: 기존 판정, 이미 수집 {len(done)}곳) -> {a.outdir}")
        return
    sus = [r for r in R if r["업종_갈래"] == "2인분 의심"]
    bowl = [r for r in R if r["업종_갈래"] == "한 그릇 업종"]
    other = [r for r in R if r["업종_갈래"] == "그 밖"]
    nb = round(50 * len(bowl) / (len(bowl) + len(other)))
    pick = rnd.sample(sus, 50) + rnd.sample(bowl, nb) + rnd.sample(other, 50 - nb)
    rnd.shuffle(pick)
    write(a, pick)
    print(f"시범 {len(pick)}곳: 2인분 의심 50, 한 그릇 {nb}, 그 밖 {50 - nb} -> {a.outdir}")


def write(a, pick):
    os.makedirs(a.outdir, exist_ok=True)
    with open(os.path.join(a.outdir, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["수집ID", "상호", "도로명주소", "업종_소분류", "업종_갈래"])
        for r in pick:
            w.writerow([r["상가업소번호"], r["상호"], r["도로명주소"], r["업종_소분류"], r["업종_갈래"]])
    for k in range(0, len(pick), a.per):
        rows = [[r["상가업소번호"], (r["상호"] + " " + r["지점명"]).strip(), r["도로명주소"], r["업종_소분류"]] for r in pick[k:k + a.per]]
        with open(os.path.join(a.outdir, f"prompt_{k // a.per:03d}.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(HEAD + json.dumps(rows, ensure_ascii=False))
    with open(os.path.join(a.outdir, "run_all.sh"), "w", encoding="utf-8", newline="\n") as f:
        f.write(RUN)


if __name__ == "__main__":
    main()
