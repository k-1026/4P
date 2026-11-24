"""갖고 있는 리뷰·VOC 데이터에서 1인 입장 불가 / N인분 이상 시키면 혼자 가능 / 2인 조건 문장을 찾는다."""
import csv, glob, io, re, sys
from collections import Counter, defaultdict

P = r"C:/Users/Green/Desktop/팀프로젝트/painpoint/리뷰자료_전체모음_1120"
S = sys.argv[1]
PAT = {
    # 혼자 들어가는 것 자체를 막음
    "입장불가": re.compile(r"혼자\s*(는|서는|선|오면|오시면|온|가면|가니|갔더니|갔는데)?\s*(안\s*(받|된|돼|들여|해\s*준|줘)|못\s*(받|들어|먹|앉)|불가|거절|사절|손해|곤란)"
                       r"|1\s*인\s*(손님|고객|입장|방문|은|이면|이라)?\s*(안\s*(받|돼|됨|된)|불가|사절|거절|노|금지)"
                       r"|혼밥\s*(불가|안\s*(돼|됨|되|받)|금지|사절|거절|못\s*해)"
                       r"|(2|두)\s*인\s*(이상|부터)\s*(입장|이용|방문|손님|만\s*받)"),
    # 혼자도 되지만 N인분 이상 시켜야 함
    "N인분조건_혼자": re.compile(r"혼자.{0,15}(2|3|두|세)\s*인\s*분.{0,10}(시켜|주문|먹어야|이상|부터)"
                             r"|(2|3|두|세)\s*인\s*분.{0,10}(시키면|주문하면|시켜야|주문해야).{0,15}(혼자|1\s*인)"
                             r"|혼자.{0,10}(인분\s*이상|이상\s*주문)"),
    # 메뉴·주문 조건으로 2인분 이상(혼자 언급 여부와 무관)
    "2인조건": re.compile(r"(2|두)\s*인\s*분?\s*(이상|부터)|최소\s*(2|두)\s*인|1\s*인\s*분\s*(은|은\s*)?\s*(주문\s*)?(안\s*(돼|됨|팔|파)|불가|없)"),
    # 혼자 가능(대조용)
    "혼자가능": re.compile(r"혼자(서)?\s*(가도|와도|먹기|먹어도|방문|가기|오기)\s*(좋|괜찮|편|가능|부담)|혼밥\s*(가능|하기\S{0,3}\s*(좋|편|괜찮|딱)|환영)|1\s*인\s*(가능|도\s*가능|손님\s*환영)"),
}


def rows_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            t = open(path, encoding=enc).read(); break
        except UnicodeDecodeError:
            continue
    s = t.find('"수집ID"')
    if s > 0:
        t = t[s:].split("```")[0]
    return list(csv.DictReader(io.StringIO(t)))


sources = {
    "오늘_Aside_114곳": sorted(glob.glob(f"{S}/sig_out_[0-3].csv")),
    "네이버리뷰_합본_300곳": [f"{P}/1_네이버리뷰_1118/결과/합본_네이버리뷰.csv"],
    "카카오후기": glob.glob(f"{P}/3_방문객VOC/voc_카카오후기_*.csv"),
    "VOC_분류·질문·댓글": glob.glob(f"{P}/3_방문객VOC/voc_classified.csv") + glob.glob(f"{P}/3_방문객VOC/voc_질문글_30건.csv") + glob.glob(f"{P}/3_방문객VOC/voc_유튜브댓글_87건.csv"),
    "통합비교_VOC": [f for f in glob.glob(f"{P}/4_통합비교_1119/결과/V*.csv")],
}
TEXT_COLS = ("원문_핵심문장", "본문", "사장님답글", "원문 표현", "요약", "근거_원문", "원문", "내용", "댓글", "제목", "text", "본문요약")
out = []
summary = {}
for src, files in sources.items():
    n_rows = 0; hits = Counter(); stores = defaultdict(set)
    for fp in files:
        for r in rows_csv(fp):
            n_rows += 1
            store = r.get("수집ID") or r.get("관리번호") or r.get("상호") or r.get("표본번호") or r.get("voc_id") or ""
            for col in TEXT_COLS:
                txt = r.get(col)
                if not txt:
                    continue
                for k, pat in PAT.items():
                    m = pat.search(txt)
                    if m:
                        hits[k] += 1; stores[k].add(store)
                        s0 = max(0, m.start() - 40)
                        out.append({"출처": src, "파일": fp.split("/")[-1], "칸": col, "가게": store,
                                    "상호": r.get("상호") or r.get("플랫폼_상호", ""), "구분": k, "문장": re.sub(r"\s+", " ", txt[s0:m.end() + 40])})
    summary[src] = (n_rows, dict(hits), {k: len(v) for k, v in stores.items()})
with open(f"{S}/entry_hits.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
for k, v in summary.items():
    print(k, "줄", v[0], "문장", v[1], "가게", v[2])
print("총 일치", len(out))
for o in out:
    if o["구분"] in ("입장불가", "N인분조건_혼자"):
        print(f"[{o['구분']}] {o['출처']}|{o['칸']}|{o['상호']}|{o['문장']}")
