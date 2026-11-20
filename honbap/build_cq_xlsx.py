import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
T = r"C:\Users\Green\.aside\u\0\sessions\2026-11-19_WxOQKk7ly49OsuuP\tmp"
A = r"C:\Users\Green\.aside\u\0\sessions\2026-11-19_WxOQKk7ly49OsuuP\artifacts"
cq = json.load(open(T + r"\community_q.json", encoding="utf-8"))
ap = json.load(open(T + r"\appstore_hits.json", encoding="utf-8"))
F = "맑은 고딕"; thin = Side(style="thin", color="BFBFBF"); B = Border(left=thin, right=thin, top=thin, bottom=thin)
wb = Workbook()

def sheet(name, title, notes, hdr, rows, widths):
    ws = wb.create_sheet(name); ws.cell(1, 1, title).font = Font(name=F, size=12, bold=True); r = 2
    for n in notes:
        ws.cell(r, 1, n).font = Font(name=F, size=9, italic=True, color="595959"); r += 1
    for j, h in enumerate(hdr, 1):
        c = ws.cell(r, j, h); c.font = Font(name=F, bold=True); c.fill = PatternFill("solid", fgColor="DDEBF7"); c.border = B; c.alignment = Alignment(wrap_text=True, horizontal="center")
    for i, row in enumerate(rows, r + 1):
        for j, v in enumerate(row, 1):
            c = ws.cell(i, j, v); c.font = Font(name=F, size=10); c.border = B; c.alignment = Alignment(wrap_text=True, vertical="top")
    for j, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(r + 1, 1)

def summ(arr):
    y = {}; a = {}
    for x in arr:
        y[x["dateN"][:4]] = y.get(x["dateN"][:4], 0) + 1; a[x["asker"]] = a.get(x["asker"], 0) + 1
    return y, a, sum(x["menu2"] for x in arr), sum(x["twoPlus"] for x in arr), sum(x["seat"] for x in arr)

cy, ca, cm, ct, cs = summ(cq["cafe"]); ky, ka, km, kt, ks = summ(cq["kin"])
srows = [
 ["네이버 카페 (검색 5개 질의 상위 결과)", cq["cafeAll"], len(cq["cafe"]), ca.get("방문객(여행·출장·야구 등)", 0), ca.get("거주·근무", 0), ca.get("불명", 0), cm, ct, cs],
 ["네이버 지식iN (검색 8개 질의 상위 결과)", cq["kinAll"], len(cq["kin"]), ka.get("방문객(여행·출장·야구 등)", 0), ka.get("거주·근무", 0), ka.get("불명", 0), km, kt, ks],
]
sheet("요약_커뮤니티", "커뮤니티 '대구 혼밥 어디' 질문 글 (수집일 2026-11-20)",
      ["질문 글 = 제목이 질문형(추천/있나요/어디/되나요 등)이고 대구 지역어와 혼밥·혼자·1인을 포함한 글. 광고성 템플릿 글은 제외.",
       "분류는 제목+본문 첫 줄의 단어 기준 자동 분류(참고용). 검색 결과 순위가 최신 글을 우대해 연도별 개수는 추세로 쓰면 안 됨."],
      ["출처", "수집 글 수", "대구 혼밥 질문 글", "방문객(여행·출장·야구)", "거주·근무", "불명", "고기·막창·찜 등 메뉴 언급", "'2인분/1인분' 언급", "좌석·눈치 언급"], srows,
      [36, 10, 12, 14, 10, 8, 14, 12, 12])

def qrows(arr, src):
    out = []
    for x in sorted(arr, key=lambda z: z["dateN"], reverse=True):
        out.append([src, x["dateN"], x.get("cafe", ""), x["title"], (x.get("body") or x.get("q") or "")[:250], x["asker"], "O" if x["menu2"] else "", "O" if x["twoPlus"] else "", "O" if x["seat"] else "", x["url"]])
    return out
sheet("질문글_목록", "대구 혼밥 질문 글 전체 목록", ["날짜에 (약)이 붙은 것은 'N주 전' 표기를 2026-11-20 기준으로 환산한 값."],
      ["출처", "날짜", "카페명", "제목", "본문 첫 부분", "질문자 유형(추정)", "고기류", "2인분/1인분", "좌석·눈치", "URL"],
      qrows(cq["cafe"], "네이버 카페") + qrows(cq["kin"], "지식iN"), [10, 13, 22, 40, 60, 16, 7, 9, 8, 40])

key = [
 ["2025-04-25", "네이버 카페(전기차 동호회)", "대구 혼밥 할만한 곳 추천해 주세요~", "\"대창, 뭉티기가 맛집이라던데 2인분 이상 주문해야 되네요ㅠㅠ 혹시 동성로 근처에 혼밥할만한…\"", "11번 직접 근거(방문객)"],
 ["2023-09-11", "지식iN", "대구 달서구 쪽 1인분 식사 되는 고기집 아시는 곳 있나요", "\"1인 식사 되는 고기집 같은곳 있나요? ㅠㅠ 내공 많이 걸겠습니다\"", "달서구·고기·1인분"],
 ["2024-05-12", "지식iN", "1인인데 한우고기 500그람 시키면 고기집 입장 될까요", "\"대구 달서구쪽에 한우집 갈건데 1인도 갈수 있죠?\"", "달서구·입장 가능 여부 불안"],
 ["2022-11-15", "지식iN", "명륜진사갈비 대구 달서구 이곡점, 혼밥 되나요?", "\"안된다면 대구 지점 내에 혼밥 가능 명륜진사갈비 어디 없을까요\"", "달서구·고기"],
 ["2026-06-23", "지식iN", "대구에 1인메뉴 가능한 육류 무한리필집 없나요?", "\"훠궈같은거 말고요\"", "1인 메뉴 탐색"],
 ["2025-08-25", "지식iN", "대구에 막창 혼밥되는집있나요?", "\"혼자가는여행이라 혼밥되는식당 있을까요?\" / 답변: \"혼술은 어느 가게나 모두 가능\"", "막창·방문객"],
 ["2026-10-07", "네이버 카페(돌싱 카페)", "대구 혼밥하기 좋은 곳 추천해주세요", "\"혼자서 고기 구워먹울 수 있는 곳?\"", "고기·성인 1인"],
 ["2025-12-13", "네이버 카페(디젤매니아)", "대구분들 혼밥 식당 추천좀요", "\"30대남자 혼자 가서 먹을만한 졸맛탱 맛집없나요\"", "30대 남성 자기 표기"],
 ["2026-03-25", "네이버 카페(더먹자)", "대구 혼밥 맛집있을까요?", "\"대구 중구에 1인석이나 다찌자리 있어서 혼밥하기 좋은곳 있을까요?\"", "좌석 조건"],
 ["2024-08-08", "네이버 카페", "다들 혼밥하러 어디까지 가보셨나요?", "\"…2인이상 시켜야하는집\"(대구 거주자)", "2인 이상 경험"],
]
sheet("핵심인용", "11번(2인분 장벽)과 직접 연결되는 질문 글", ["작성자 연령·거주는 대부분 확인 불가(D 등급)."], ["날짜", "출처", "제목", "인용", "의미"], key, [12, 22, 44, 70, 22])

arows = []
for app, v in ap.items():
    arows.append([app, v["n"], f'{v["from"]} ~ {v["to"]}', len(v["filter"]), len(v["solo"])])
sheet("요약_앱스토어", "앱스토어(iOS 한국) 최근 리뷰 중 필터·검색 불만 (수집일 2026-11-20)",
      ["애플 공개 리뷰 RSS로 앱별 최근 500건(최대치) 수집. 구글플레이는 이 환경에서 로그인 화면으로 넘어가 수집하지 못함.",
       "'필터·검색' = 필터/조건/분류/정렬/검색 불편 등 단어 포함. 네이버·카카오는 대부분 길찾기·내비 불만이고 음식점 필터 불만은 없음."],
      ["앱", "수집 리뷰", "기간", "필터·검색 단어 포함", "혼밥·혼자·1인 포함"], arows, [14, 10, 26, 16, 16])
rel = [
 ["다이닝코드", "2021-08-24", 3, "혼밥", "혼밥 카테고리가 따로 있으면 좋겠습니다. 도보로 얼마나 걸리는지도 앱내에서 00분으로 알려주면 좋겠습니다.", "혼밥 조건 탐색 불만(직접)"],
 ["다이닝코드", "2019-08-24", 5, "좋아요!", "다만 필터링 기능이 있었으면 좋겠어요! 가격, 테이블 종류등 있으면 더 편하게 찾을 수 있을거같아요", "가격·테이블 필터 요청"],
 ["다이닝코드", "2026-05-22", 5, "맛집 어플 중 최고", "예전처럼 정렬순 설정 기능이 부활했으면 합니다", "정렬 기능 요청"],
 ["다이닝코드", "2017-11-18", 4, "아쉬움에 대한 제안", "20.30대와 40.50대 만이라도 구분하면…", "연령별 구분 요청"],
 ["캐치테이블", "2026-11-05", 3, "필터의 부정확함", "가장 취약한 문제는 가격 필터가 전혀 맞지 않는다는 것입니다.", "가격 필터 정확도"],
 ["캐치테이블", "2026-05-11", 1, "원랴", "필터로 시간 일자 다정해지면 필터적용하면 안나와야지. 점심 시간으로 필터해놓는데 저녁영업만 하는 식당들은 왜 뜨는데?", "시간 필터 정확도"],
 ["캐치테이블", "2026-02-25", 4, "예약 마감 제외 필터", "예약이 마감된 음식점이 있으면 제외하는 필터가 생기면 편리할 것 같아요.", "필터 추가 요청"],
 ["캐치테이블", "2025-12-24", 1, "(욕설)", "예약 마감 제외 필터 만들어라", "필터 추가 요청"],
 ["캐치테이블", "2026-09-29", 5, "날짜 인원수 실시간 예약이 짱", "날짜와 인원수로 원하는 지역의 식당을 필터해서 찾을수 있다는게 정말 엄청난 메리트", "필터 칭찬(반대 사례)"],
 ["네이버지도", "2026-10-06~10-10", "1~5", "예약 추천 카테고리 삭제 희망 외 3건", "검색 기록 중간에 생긴 예약 추천 카테고리 제발 없애주세요", "검색 화면 구성 불만(음식점 필터 아님)"],
 ["카카오맵", "2026-10-31", 3, "잘못된 정보가 너무 많아졌어요", "지방쪽은 더 심한 것 같아요… atm 검색했는데 두 군데나 잘못된 곳", "정보 정확도(필터 아님)"],
]
sheet("앱리뷰_관련", "앱스토어 리뷰 중 필터·조건 탐색 관련 글", [], ["앱", "날짜", "별점", "제목", "내용(요지 인용)", "분류"], rel, [12, 16, 6, 26, 80, 24])
allr = []
for app, v in ap.items():
    for kind, lst in [("필터·검색", v["filter"]), ("혼밥·혼자", v["solo"])]:
        for r in lst:
            allr.append([app, kind, r["date"][:10], r["rating"], r["title"], (r["body"] or "")[:400], r.get("ver")])
sheet("앱리뷰_추출전체", "키워드로 추출한 앱스토어 리뷰 전체", [], ["앱", "추출 기준", "날짜", "별점", "제목", "본문", "앱 버전"], allr, [12, 10, 12, 6, 30, 90, 10])
del wb["Sheet"]
wb.save(A + r"\커뮤니티질문_앱스토어리뷰_자료.xlsx")
print("ok", srows, arows)
