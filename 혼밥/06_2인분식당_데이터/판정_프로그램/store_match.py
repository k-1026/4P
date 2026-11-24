"""가게 목록 두 개를 상호·주소로 맞추는 도구 (2026-11-21 2인분 식당 작업에서 정리).

규칙은 같은 폴더의 `매칭규칙.md`에 사람이 읽는 말로 적어 두었다.

쓰는 법 (PowerShell 또는 Git Bash):
  python -I store_match.py 왼쪽파일 오른쪽파일 결과파일 [옵션]

  왼쪽 = 짝을 찾고 싶은 목록(예: 팀원 자료, 인허가 표본). 결과는 왼쪽 줄 순서 그대로 나온다.
  오른쪽 = 기준 목록(예: 상권정보). 보통 상권정보를 쓴다.

옵션 (칸 이름은 파일의 머리줄 그대로):
  --l-name 상호     --l-addr 도로명주소   --l-gu 구군
  --r-name 상호명   --r-branch 지점명     --r-addr 도로명주소   --r-gu 시군구명   --r-id 상가업소번호
  --r-filter 상권업종대분류명=음식     (오른쪽에서 이 조건인 줄만 씀)
  --l-sheet 시트이름 / --r-sheet 시트이름   (xlsx일 때)
  --mode road | jibun   (jibun: 왼쪽 주소가 지번일 때. 오른쪽은 상권정보의 법정동명·지번본번지·지번부번지를 씀)

결과 칸 (왼쪽 원래 칸은 하나도 바꾸지 않고 오른쪽에 붙인다):
  매칭_단계        A_주소+상호 / B_주소+상호일부 / C_상호+도로명 / D_주소만 / 없음_행사·시장임시주소 / 없음
  매칭_ID          오른쪽 ID (A~C만)
  매칭_상호, 매칭_주소
  매칭_같은주소_다른상호   D일 때 같은 주소의 오른쪽 가게들 (손확인용)
  매칭_같은상호_다른주소   없음일 때 같은 구·군에 같은 상호가 다른 주소로 있는 가게들 (손확인용)

D·없음은 자동으로 잇지 않는다. 매칭규칙.md의 '손확인 순서'대로 사람이(또는 지도로) 판정한다.
"""
import argparse, csv, html, json, os, re, sys
from collections import Counter, defaultdict


# ---------- 읽기 ----------
def read_table(path, sheet=None):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        ws = wb[sheet] if sheet else wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
        hdr = [str(h) for h in rows[0]]
        return [dict(zip(hdr, ["" if v is None else str(v) for v in r])) for r in rows[1:] if any(v is not None for v in r)]
    if ext == ".json":
        d = json.load(open(path, encoding="utf-8"))
        return [{k: "" if v is None else str(v) for k, v in x.items()} for x in d]
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc) as f:
                rows = list(csv.DictReader(f))
            # 머리줄 앞에 깨진 글자가 붙은 파일(예: 착한가격업소 원본 '광역')을 정리
            if rows:
                fixed = {}
                for k in rows[0].keys():
                    fixed[k] = re.sub(r"^[^\w가-힣(]+", "", k) if k else k
                rows = [{fixed[k]: v for k, v in r.items()} for r in rows]
            return rows
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"읽을 수 없음: {path}")


# ---------- 정리 규칙 ----------
ROAD_SPACED = re.compile(r"^(대구광역시\s\S+\s(?:\S+[읍면]\s)?\S+(?:로|길))\s(\d+(?:-\d+)?)")
ROAD_JOINED = re.compile(r"^(대구광역시\s\S+\s(?:\S+[읍면]\s)?[^\s\d]+(?:로|길)(?:\d+[번안가]?길)?)\s?(\d+(?:-\d+)?)")


def norm_addr(a):
    """도로명주소를 '대구광역시 구 (읍면) 도로명 건물번호'까지만 남긴다."""
    a = (a or "").strip()
    a = re.sub(r"^대구\s", "대구광역시 ", a)                 # '대구 남구' → '대구광역시 남구'
    a = a.replace(" 지하 ", " ")                               # '달구벌대로 지하 2100' → '달구벌대로 2100'
    a = re.sub(r"\s+", " ", a.split("(")[0].split(",")[0]).strip()  # 괄호·쉼표 뒤(층, 동 이름) 버림
    a = re.sub(r"(로|길) (\d+[번안가]?길)", lambda m: m.group(1) + m.group(2), a)  # '비슬로 512길' → '비슬로512길'
    m = ROAD_SPACED.match(a) or ROAD_JOINED.match(a)           # 건물번호 뒤(상호, '1층') 버림, '선원로34' → '선원로 34'
    return f"{m.group(1)} {m.group(2)}" if m else a


def road_of(a):
    return re.sub(r"\s\d[\d-]*$", "", a)


def norm_name(n):
    """상호 비교용: HTML 기호 풀기, 괄호 안 지우기, 공백·기호 지우기, 영문 소문자."""
    n = html.unescape(n or "")
    n = re.sub(r"\(.*?\)", "", n)
    return re.sub(r"[^0-9A-Za-z가-힣]", "", n).lower()


def jibun_key(gu, a):
    m = re.search(r"(\S+[동가리])\s(?:산\s?)?(\d+)(?:-(\d+))?", re.sub(r"\s+", " ", a or ""))
    return (gu, m.group(1), m.group(2), m.group(3) or "0") if m else None


def is_event_addr(raw):
    return "일원" in (raw or "")


# ---------- 매칭 ----------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("left"); p.add_argument("right"); p.add_argument("out")
    p.add_argument("--l-name", default="상호"); p.add_argument("--l-addr", default="도로명주소"); p.add_argument("--l-gu", default="구군")
    p.add_argument("--r-name", default="상호명"); p.add_argument("--r-branch", default="지점명"); p.add_argument("--r-addr", default="도로명주소")
    p.add_argument("--r-gu", default="시군구명"); p.add_argument("--r-id", default="상가업소번호")
    p.add_argument("--r-filter", default="")
    p.add_argument("--l-sheet"); p.add_argument("--r-sheet")
    p.add_argument("--mode", choices=["road", "jibun"], default="road")
    a = p.parse_args()

    Lrows = read_table(a.left, a.l_sheet)
    R = read_table(a.right, a.r_sheet)
    if a.r_filter:
        k, v = a.r_filter.split("=", 1)
        R = [r for r in R if r.get(k) == v]
    for need, rows, cols in (("왼쪽", Lrows, [a.l_name, a.l_addr, a.l_gu]), ("오른쪽", R, [a.r_name, a.r_addr, a.r_gu, a.r_id])):
        miss = [c for c in cols if rows and c not in rows[0]]
        if miss:
            raise SystemExit(f"{need} 파일에 칸이 없음: {miss}. 있는 칸: {list(rows[0].keys())}")

    rname = lambda r: {norm_name(r[a.r_name] + r.get(a.r_branch, "")), norm_name(r[a.r_name])} - {""}
    rlabel = lambda r: (r[a.r_name] + (" " + r[a.r_branch] if r.get(a.r_branch) else "")).strip()
    by_addr, by_name_gu = defaultdict(list), defaultdict(list)
    for r in R:
        if a.mode == "jibun":
            key = (r[a.r_gu], r.get("법정동명", ""), str(r.get("지번본번지", "")), str(r.get("지번부번지", "") or "0"))
        else:
            key = norm_addr(r[a.r_addr])
        by_addr[key].append(r)
        for k in rname(r):
            by_name_gu[(k, r[a.r_gu])].append(r)

    out = []
    for l in Lrows:
        raw = l[a.l_addr]; gu = l[a.l_gu]; sn = norm_name(l[a.l_name])
        key = jibun_key(gu, raw) if a.mode == "jibun" else norm_addr(raw)
        at = by_addr.get(key, []) if key else []
        hit, lvl = None, "없음"
        for r in at:                                             # A: 주소 + 상호 같음
            if sn and sn in rname(r):
                hit, lvl = r, "A_주소+상호"; break
        if not hit:                                              # B: 주소 같고 한쪽 상호가 다른 쪽에 들어 있음(2글자 이상)
            for r in at:
                if any(len(k) >= 2 and len(sn) >= 2 and (k in sn or sn in k) for k in rname(r)):
                    hit, lvl = r, "B_주소+상호일부"; break
        if not hit and sn and a.mode == "road":                  # C: 상호 같고 같은 도로, 건물번호만 다름. 후보가 1곳일 때만
            same = {r[a.r_id]: r for r in by_name_gu.get((sn, gu), []) if road_of(norm_addr(r[a.r_addr])) == road_of(key)}
            if len(same) == 1:
                hit, lvl = next(iter(same.values())), "C_상호+도로명"
        other_at, other_name = "", ""
        if not hit:
            if at:
                lvl = "D_주소만"
                other_at = " / ".join(f"{rlabel(r)}[{r[a.r_id]}]" for r in at[:8])
            elif is_event_addr(raw):
                lvl = "없음_행사·시장임시주소"
            if lvl.startswith("없음") and sn:
                sames = {r[a.r_id]: r for r in by_name_gu.get((sn, gu), [])}
                other_name = " / ".join(f"{rlabel(r)}@{r[a.r_addr]}[{r[a.r_id]}]" for r in list(sames.values())[:5])
        o = dict(l)
        o.update({"매칭_단계": lvl,
                  "매칭_ID": hit[a.r_id] if hit else "",
                  "매칭_상호": rlabel(hit) if hit else "",
                  "매칭_주소": hit[a.r_addr] if hit else "",
                  "매칭_같은주소_다른상호": other_at,
                  "매칭_같은상호_다른주소": other_name})
        out.append(o)

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    c = Counter(o["매칭_단계"] for o in out)
    ok = sum(1 for o in out if o["매칭_ID"])
    print(f"왼쪽 {len(out)}줄 → 자동 연결(A~C) {ok}줄 ({ok / len(out):.1%})")
    for k in sorted(c):
        print(f"  {k}: {c[k]}")
    dup = Counter(o["매칭_ID"] for o in out if o["매칭_ID"])
    n = sum(1 for v in dup.values() if v > 1)
    if n:
        print(f"  주의: 오른쪽 가게 하나에 왼쪽 두 줄 이상이 이어진 경우 {n}건 (같은 가게 중복 등록일 수 있음)")


if __name__ == "__main__":
    main()
