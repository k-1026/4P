"""Desktop·Downloads의 모든 표·문서 파일에서 1인 입장 불가 / N인분 조건 문장을 찾는다(복사본 문장은 하나로)."""
import os, re, sys, csv, json
from collections import defaultdict

ROOTS = [r"C:/Users/Green/Desktop", r"C:/Users/Green/Downloads"]
SKIP_DIR = {"node_modules", ".git", ".venv", "venv", "site-packages", ".next", "__pycache__", "dist", "build", ".cache", ".claude", ".codex"}
EXT = {".csv", ".json", ".jsonl", ".txt", ".md", ".xlsx", ".tsv"}
MAXB = 60 * 1024 * 1024
SKIP_NAME = re.compile(r"상가상권정보|시간대_전체|생활시간조사")
PAT = {
    "입장불가": re.compile(
        r"혼자\s*(는|서는|선|라서|라고|오면|오시면|온|가면|가니|갔더니|갔는데|왔다고|이라고)?\s*(안\s*(받|된|돼|들여|해\s*준|줘|된대|된다)|못\s*(받|들어|먹|앉|가|갑)|불가|거절|사절|손해|곤란|쫓겨)"
        r"|1\s*인\s*(손님|고객|입장|방문|은|이면|이라|식사는?)?\s*(안\s*(받|돼|됨|된|되)|불가|사절|거절|못\s*(가|갑|들어|받))"
        r"|혼밥\s*(은|는)?\s*(불가|안\s*(돼|됨|되|받)|금지|사절|거절|못\s*해|안\s*받)"
        r"|(2|두)\s*인\s*(이상|부터)\s*(입장|이용\s*가능|방문|손님만|만\s*받)|입장\s*불가"),
    "N인분조건": re.compile(
        r"첫\s*주문\S{0,3}\s*[2-4]\s*인\s*분|[2-4]\s*인\s*분?\s*이상\s*(주문|부터|시켜|만)|최소\s*[2-4]\s*인|[2-4]\s*인\s*부터\s*(주문|적용|가능)"
        r"|인당\s*1\s*인\s*분|1\s*인\s*1\s*메뉴|1\s*인분\s*(은|만)?\s*(주문\s*)?(안\s*(돼|됨|팔|파|된)|불가)"
        r"|혼자.{0,20}[2-4]\s*인\s*분.{0,10}(시켜야|주문해야|이상|시키라|시키래)"),
}
hits = defaultdict(lambda: {"files": set(), "kind": set()})
nfiles = 0; nhitfiles = set()


def scan_text(txt, path):
    for k, p in PAT.items():
        for m in p.finditer(txt):
            seg = re.sub(r"\s+", " ", txt[max(0, m.start() - 60): m.end() + 60])
            key = re.sub(r"[^가-힣0-9]", "", txt[max(0, m.start() - 25): m.end() + 25])
            h = hits[key]; h["files"].add(path); h["kind"].add(k); h.setdefault("seg", seg)
            nhitfiles.add(path)


for root in ROOTS:
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIR and not d.startswith(".")]
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in EXT or SKIP_NAME.search(fn):
                continue
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > MAXB:
                    continue
                if ext == ".xlsx":
                    import openpyxl
                    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
                    parts = []
                    for ws in wb.worksheets:
                        for row in ws.iter_rows(values_only=True):
                            parts.extend(str(v) for v in row if isinstance(v, str))
                    txt = "\n".join(parts)
                else:
                    raw = open(p, "rb").read()
                    try:
                        txt = raw.decode("utf-8-sig")
                    except UnicodeDecodeError:
                        txt = raw.decode("cp949", errors="ignore")
                    if ext in (".json", ".jsonl"):
                        txt = txt.encode().decode("unicode_escape", errors="ignore") if "\\u" in txt[:5000] else txt
                nfiles += 1
                scan_text(txt, p.replace("\\", "/"))
            except Exception as e:
                pass

out_p = sys.argv[1]
with open(out_p, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["구분", "문장", "나온_파일수", "파일_예시"])
    for key, h in sorted(hits.items(), key=lambda kv: sorted(kv[1]["kind"])):
        files = sorted(h["files"])
        w.writerow(["/".join(sorted(h["kind"])), h["seg"], len(files), files[0]])
print("읽은 파일", nfiles, "문장이 나온 파일", len(nhitfiles), "서로 다른 문장", len(hits))
