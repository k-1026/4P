# 대구 전역 1차 판정에서 최소주문이 '미상'인 가게(달서구 DS/DC 제외)를 32곳씩 묶어
# Aside 블로그 수집 지시문을 만든다. 형식은 작업기록_20261121/신호수집_Aside/blog_prompt_0.txt와 같다.
# 사용: python -I make_blog_prompts.py  (이 폴더에서)
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "원본자료", "2인분식당_수집양식_대구전역표본_판정_Aside_20261123.csv")
OUT = os.path.join(HERE, "블로그수집")
SIZE = 32

HEAD = """대구 식당을 한 곳씩, 네이버 블로그 후기(search.naver.com 블로그 탭 또는 blog.naver.com)에서 확인해 줘. 네이버가 안 되면 다음(daum) 블로그·티스토리도 괜찮아.
목적: 이 식당이 "2인분부터·2인 이상·첫 주문 3인분"처럼 혼자 1인분만 주문할 수 없는지, "혼자는 안 받는다"는지, 또는 "1인분 주문 가능·혼밥 가능"인지의 근거를 모으는 것.
각 줄은 [수집ID, 상호, 도로명주소, 업종]이야.

가게마다:
1) "상호 + 동네(주소의 도로명이나 구·군 이름)"로 블로그를 찾아. 같은 가게(상호와 주소·지점이 맞는 글)만 써.
2) 최근 글부터 최대 5개 글을 열어서, 본문에 "1인분", "2인분", "3인분", "인분부터", "인분 이상", "첫 주문", "혼자", "혼밥", "1인", "2인 이상"이 들어간 문장을 찾아.
3) 찾은 문장을 원문 그대로(100자 안쪽) 적고, 글 작성일과 글 주소를 적어. 한 가게에 최대 4개.
   - 메뉴판 사진이 글에 있으면 사진 속 글자에서도 같은 낱말을 찾아 적고 메모에 '사진'이라고 표시해.
4) 블로그가 하나도 없으면 근거_종류를 "없음"으로 한 줄.

지킬 것:
- 보이는 것만 적고 추측·판정은 하지 마.
- 블로그 작성자 이름·닉네임·프로필은 적지 마. 문장, 작성일, 글 주소만.
- 협찬·광고 글이면 메모에 '협찬'이라고 적어.
- 가게 사이에 몇 초씩 쉬어. 로그인 화면이 나오면 그 가게는 건너뛰고 메모에 적어.

마지막 답은 CSV만, 머리줄 포함, 모든 칸을 따옴표로 감싸서. 근거마다 한 줄.
머리줄: 수집ID,찾음(예/아니오),플랫폼_상호,대표메뉴,근거_종류(블로그/없음),근거_출처,근거_원문,근거_작성일,근거_URL,확인한_리뷰수,혼자_태그수,동행태그_리뷰수,혼밥키워드수,키워드참여수,메모
(확인한_리뷰수에는 열어 본 블로그 글 수를 적고, 혼자_태그수 등 나머지 숫자 칸은 비워 둬. 근거_출처는 "네이버블로그" 등.)
입력:
"""


def main():
    with open(SRC, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    col = next(c for c in rows[0] if c.startswith("최소주문_판정"))
    targets = [r for r in rows if r[col] == "미상" and not r["수집ID"].startswith(("DS-", "DC-"))]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "대상목록.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["묶음", "수집ID", "상호", "도로명주소", "상권_업종소분류"])
        for i in range(0, len(targets), SIZE):
            batch = targets[i:i + SIZE]
            n = i // SIZE
            items = [[r["수집ID"], r["상호"], r["도로명주소"], r["상권_업종소분류"]] for r in batch]
            with open(os.path.join(OUT, f"prompt_{n:02d}.txt"), "w", encoding="utf-8", newline="\n") as p:
                p.write(HEAD + json.dumps(items, ensure_ascii=False))
            for it in items:
                w.writerow([f"{n:02d}"] + it)
    print(f"대상 {len(targets)}곳, 묶음 {(len(targets) + SIZE - 1) // SIZE}개 -> {OUT}")


if __name__ == "__main__":
    main()
