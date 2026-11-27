# -*- coding: utf-8 -*-
"""시장 규모 시트(market_model.xlsx '시장규모')를 만든다.

python3 도구/make_market_model.py 재료/시장규모/market_model.xlsx
  숫자 입력값은 아래 코드 안에 출처와 함께 있다. 고칠 때는 이 파일을 고치고 다시 돌린다.
  openpyxl이 필요하다 (pip install openpyxl).
  계산 결과는 저장되지 않으므로 엑셀·구글 시트로 열면 계산된다.
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
out = sys.argv[1]
wb = Workbook(); ws = wb.active; ws.title = "시장규모"
F = "Arial"
BLUE = Font(name=F, color="0000FF"); BLACK = Font(name=F); BOLD = Font(name=F, bold=True)
H1 = Font(name=F, bold=True, size=14); GREY = Font(name=F, color="666666", size=9)
YEL = PatternFill("solid", fgColor="FFFF00"); HEAD = PatternFill("solid", fgColor="E8F4F1"); KEY = PatternFill("solid", fgColor="FDE7DF")
thin = Border(bottom=Side(style="thin", color="D9E0DE"))
PPL = '#,##0;(#,##0);-'; PCT = '0.0%;(0.0%);-'; WON = '#,##0;(#,##0);-'; EOK = '#,##0.0"억";(#,##0.0"억");-'; X = '0.0;(0.0);-'

def row(r, label, val=None, unit="", src="", fmt=None, inp=False, low=None, high=None, bold=False):
    ws.cell(r, 1, label).font = BOLD if bold else BLACK
    for col, v in ((2, val), (3, low), (4, high)):
        if v is None: continue
        c = ws.cell(r, col, v)
        c.font = BLUE if inp and not (isinstance(v, str) and v.startswith("=")) else (Font(name=F, bold=bold))
        if fmt: c.number_format = fmt
    ws.cell(r, 5, unit).font = BLACK
    ws.cell(r, 6, src).font = GREY
    for col in range(1, 7): ws.cell(r, col).border = thin

ws["A1"] = "혼밥 밥친구 · 시장 규모 (TAM · SAM · SOM)"; ws["A1"].font = H1
ws["A2"] = "2026-11-26 · 시장 = 혼밥 방문 외식을 하는 사람(지난 일주일 점심·저녁 혼자 3회 이상, KREI 원자료 정의). 전국 → 경상도 → 대구. 우리 수익(BM)은 이 시트에 없음."; ws["A2"].font = GREY
ws["A3"] = "범례: 파란 글씨 = 입력값(출처 있음) · 노란 칸 = 가정, 팀이 바꿔 볼 칸 · 검정 = 수식 · 분홍 줄 = 결과. 입력을 바꾸면 아래가 모두 다시 계산됨."; ws["A3"].font = GREY
hdr = ["항목", "값", "하한(95%)", "상한(95%)", "단위", "출처 · 가정"]
def header(r, title):
    ws.cell(r, 1, title).font = Font(name=F, bold=True, size=11)
    for i, h in enumerate(hdr, 1):
        c = ws.cell(r + 1, i, h); c.font = BOLD; c.fill = HEAD

# 1. 입력
header(5, "1. 입력 — 인구 (20세 이상, 2025)")
src_pop = "국가데이터처 인구총조사(등록센서스) DT_1IN1503, 2025, 합계 − 0~19세 · KOSIS 직접 확인 (A) · 11-23 팀 문서 값"
row(7, "전국", 44277133, "명", src_pop, PPL, True)
for r, (n, v) in enumerate((("부산", 2804619), ("대구", 2017888), ("울산", 929238), ("경북", 2219730), ("경남", 2767256)), 8):
    row(r, n, v, "명", src_pop, PPL, True)
row(13, "경상도 합", "=SUM(B8:B12)", "명", "수식 · 부산+대구+울산+경북+경남", PPL)

header(15, "2. 입력 — 혼밥 비율 (KREI 식품소비행태조사 2023·2024·2025 성인 원자료 통합)")
src_r = "KREI 식품소비행태조사 원자료 3개년, 개인 가중치 · Claude 계산 · 2025 전국 29.2%가 보고서 <표 6-2>·<표 6-4>와 일치 · 비율은 19세 이상"
row(17, "전국 혼밥 비율", 0.311, "", src_r + " · 응답 17,536명", PCT, True)
row(18, "전국 ± (95% 신뢰구간)", 0.009, "%p", "", PCT, True)
row(19, "경상도 혼밥 비율", 0.361, "", "응답 4,842명 · 연도별 33.8 · 37.7 · 36.7%", PCT, True)
row(20, "경상도 ±", 0.017, "%p", "", PCT, True)
row(21, "대구 혼밥 비율", 0.380, "", "응답 1,036명 · 연도별 42.9 · 37.9 · 33.3%", PCT, True)
row(22, "대구 ±", 0.035, "%p", "", PCT, True)

header(24, "3. 입력 — 지출 (상향식용)")
row(26, "1인당 연 식당 혼밥 횟수", 23.1, "회/년", "KREI 2025 원자료, 혼밥하는 사람의 연 식당 혼밥 횟수(편의점·카페·길거리 제외) · Claude 계산 · 11-23 팀 문서", X, True)
row(27, "1회 객단가", 12500, "원", "aT 2025 국내외 외식트렌드, 혼밥 1회 지출 최빈 구간 1만~1.5만 원(38.6%)의 가운데 값 · 가정", WON, True)
ws["B27"].fill = YEL
row(28, "하향식 참고: 대구 혼밥 방문 외식 규모", 8088, "억 원", "11-23 팀 문서 결정 기록 값(외식 매출 × aT '혼자' 10.5%). 원 계산표는 이 폴더에 없음 → verify.md 확인 필요", EOK, True)

# 4. TAM SAM SOM 인원
header(30, "4. 결과 — 인원 (20세 이상 인구 × 혼밥 비율)")
for r, lab, pop, rate, pm in ((32, "TAM 전국 혼밥하는 사람", "B7", "B17", "B18"),
                              (33, "SAM 경상도 혼밥하는 사람", "B13", "B19", "B20"),
                              (34, "SOM 대구 혼밥하는 사람", "B9", "B21", "B22")):
    row(r, lab, f"={pop}*{rate}", "명", "수식", PPL, low=f"={pop}*({rate}-{pm})", high=f"={pop}*({rate}+{pm})", bold=True)
    for col in range(1, 5): ws.cell(r, col).fill = KEY
    for col in (3, 4): ws.cell(r, col).number_format = PPL
row(35, "SAM ÷ TAM", "=B33/B32", "", "원 그림의 크기는 비율이 아님", PCT)
row(36, "SOM ÷ SAM", "=B34/B33", "", "", PCT)

# 5. 금액 (상향식)
header(38, "5. 결과 — 혼밥 외식 지출 (상향식: 인원 × 연 횟수 × 객단가)")
for r, lab, src in ((40, "TAM 지출", 32), (41, "SAM 지출", 33), (42, "SOM 지출 (대구)", 34)):
    row(r, lab, f"=B{src}*$B$26*$B$27/100000000", "억 원", "수식", EOK,
        low=f"=C{src}*$B$26*$B$27/100000000", high=f"=D{src}*$B$26*$B$27/100000000", bold=(r == 42))
    for col in (3, 4): ws.cell(r, col).number_format = EOK
row(43, "교차 확인: 상향식 대구 ÷ 하향식 대구", "=B42/B28", "", "크게 다르면(예: 50% 미만·150% 초과) 가정 하나가 틀린 것 → verify.md", PCT, bold=True)

# 6. 첫해 닿을 수 있는 고객 (시나리오)
header(45, "6. 첫해 닿을 수 있는 고객 (시나리오, 대구 기준)")
ws.cell(46, 2, "보수").font = BOLD; ws.cell(46, 3, "기준").font = BOLD; ws.cell(46, 4, "낙관").font = BOLD
for col in (2, 3, 4): ws.cell(46, col).fill = HEAD
ws.cell(47, 1, "이용률 (대구 혼밥하는 사람 중 첫해 써 보는 비율)").font = BLACK
for col, v in ((2, 0.01), (3, 0.05), (4, 0.10)):
    c = ws.cell(47, col, v); c.font = BLUE; c.fill = YEL; c.number_format = PCT
ws.cell(47, 6, "가정 · 11-23 팀 결정(1·5·10%). 위쪽 한계 참고: 혼밥족 앱 이용 의향 청년 59.6%(서울, B) · 설문으로 확인 필요").font = GREY
ws.cell(48, 1, "첫해 이용자").font = BOLD
ws.cell(49, 1, "그 이용자의 연 혼밥 외식 지출 (우리 매출 아님)").font = BLACK
for col, L in ((2, "B"), (3, "C"), (4, "D")):
    c = ws.cell(48, col, f"=$B$34*{L}47"); c.number_format = PPL; c.font = BOLD; c.fill = KEY
    c = ws.cell(49, col, f"={L}48*$B$26*$B$27/100000000"); c.number_format = EOK
ws.cell(48, 5, "명"); ws.cell(49, 5, "억 원")
ws.cell(48, 6, "수식 = SOM 인원 × 이용률").font = GREY
ws.cell(49, 6, "수식 = 이용자 × 연 횟수 × 객단가. 우리 매출은 BM(수익원) 결정 후 '단위경제' 시트로").font = GREY
for r in (47, 48, 49):
    for col in range(1, 7): ws.cell(r, col).border = thin

ws.cell(51, 1, "주의").font = BOLD
notes = ["앱 데이터는 동성로(성내1~3동) 391곳뿐이다. 대구 전체를 SOM으로 두면 첫해 서비스 범위보다 크다 → 7절 제안, verify.md 2절.",
         "혼밥 비율은 19세 이상, 인구는 20세 이상이라 기준 나이가 1살 다르다.",
         "BM·레드팀·원페이지 전이라 수익·비용·단위경제는 넣지 않았다."]
for i, n in enumerate(notes, 52):
    ws.cell(i, 1, "· " + n).font = GREY


# 7. 제안 (2026-11-26): TAM 경상도 · SAM 대구 · SOM 동성로
header(56, "7. 제안 — TAM 경상도 · SAM 대구 · SOM 동성로 (첫해 서비스 범위로 좁힘)")
row(58, "대구 음식점 수", 36592, "곳", "국가데이터처 서비스업조사 2024 (A) · 팀 11-26 문서 수익 장의 값", PPL, True)
row(59, "동성로(성내1~3동) 식당 수", 1134, "곳", "혼밥팀 최종본 0_먼저읽기.md '동성로 1,134곳을 모두 보고' (인허가 목록 기준, 2026-11-26)", PPL, True)
row(60, "그중 혼밥 DB에 든 가게 (1인분 + 혼밥 후기 5명 이상)", 391, "곳", "혼밥팀 최종본 DB", PPL, True)
row(61, "동성로 비중 (식당 수 기준)", "=B59/B58", "", "가정: 대구의 혼밥 외식이 식당 수에 비례해 동네별로 나뉜다. 동성로 낮 시간 인구·종사자 통계를 찾으면 이 칸을 바꾼다", PCT)
ws["B61"].fill = YEL
row(62, "혼밥 DB 가게 비중 (동성로 안)", "=B60/B59", "", "수식", PCT)
row(64, "TAM (제안) 경상도 혼밥하는 사람", "=B33", "명", "4절 SAM과 같은 값. 같은 수집 방법(인허가 목록 → 지도 확인)으로 넓혀 갈 영남권 대도시의 끝", PPL, low="=C33", high="=D33", bold=True)
row(65, "TAM (제안) 지출", "=B41", "억 원", "5절 SAM 지출과 같은 값", EOK, low="=C41", high="=D41")
row(66, "SAM (제안) 대구 혼밥하는 사람", "=B34", "명", "4절 SOM과 같은 값. 서비스 지역이 대구라 SAM으로 올림", PPL, low="=C34", high="=D34", bold=True)
row(67, "SAM (제안) 지출", "=B42", "억 원", "5절 SOM 지출과 같은 값", EOK, low="=C42", high="=D42")
row(68, "SOM (제안) 동성로 혼밥 — 사람 환산", "=B34*$B$61", "명", "대구 혼밥하는 사람 × 동성로 비중. 연 23.1회를 모두 동성로에서 먹는 사람으로 환산한 수(실제로 동성로에서 한 번이라도 먹는 사람은 더 많음)", PPL, low="=C34*$B$61", high="=D34*$B$61", bold=True)
row(69, "SOM (제안) 동성로 혼밥 지출", "=B42*$B$61", "억 원", "대구 혼밥 지출 × 동성로 비중", EOK, low="=C42*$B$61", high="=D42*$B$61", bold=True)
row(70, "  그중 혼밥 DB 391곳에서 일어나는 지출", "=B69*$B$62", "억 원", "가정: 동성로 안에서 식당 수에 비례", EOK)
row(71, "SAM ÷ TAM (제안)", "=B66/B64", "", "단계마다 줄어드는 비율", PCT)
row(72, "SOM ÷ SAM (제안)", "=B68/B66", "", "", PCT)
for r in (64, 66, 68, 69):
    for col in range(1, 5): ws.cell(r, col).fill = KEY
for r in range(64, 70):
    for col in (3, 4): ws.cell(r, col).number_format = ws.cell(r, 2).number_format
ws.cell(74, 1, "첫해 이용자 (동성로, 시나리오)").font = BOLD
ws.cell(74, 2, "보수").font = BOLD; ws.cell(74, 3, "기준").font = BOLD; ws.cell(74, 4, "낙관").font = BOLD
for col in (2, 3, 4): ws.cell(74, col).fill = HEAD
ws.cell(75, 1, "이용률 (6절과 같은 값을 씀)")
ws.cell(76, 1, "첫해 이용자 (사람 환산)").font = BOLD
ws.cell(77, 1, "그 이용자의 연 혼밥 외식 지출 (우리 매출 아님)")
for col, L in ((2, "B"), (3, "C"), (4, "D")):
    c = ws.cell(75, col, f"={L}47"); c.number_format = PCT
    c = ws.cell(76, col, f"=$B$68*{L}75"); c.number_format = PPL; c.font = BOLD; c.fill = KEY
    c = ws.cell(77, col, f"={L}76*$B$26*$B$27/100000000"); c.number_format = EOK
ws.cell(75, 6, "6절 이용률을 그대로 가져옴").font = GREY
ws.cell(78, 1, "비교: 6절 기준(대구 5%) 이용자 ÷ 동성로 SOM").font = BLACK
c = ws.cell(78, 2, "=C48/B68"); c.number_format = '0.0"배"'; c.font = BOLD
ws.cell(78, 6, "1배를 넘으면 대구 기준 시나리오가 동성로 혼밥 시장 전체보다 크다는 뜻").font = GREY
for r in range(74, 79):
    for col in range(1, 7): ws.cell(r, col).border = thin

for col, w in zip("ABCDEF", (44, 16, 16, 16, 8, 90)):
    ws.column_dimensions[col].width = w
ws.freeze_panes = "A5"
ws["B27"].comment = Comment("가정: aT 2025 최빈 구간 1만~1.5만 원의 가운데 값. 우리 앱 실제 1인 가격(동성로 391곳)으로 바꿔 볼 수 있음.", "Claude")
ws["B28"].comment = Comment("11-23 팀 HTML 결정 기록의 '교차 확인 참고값'. 계산 원본 파일 확인 필요.", "Claude")
wb.save(out)
