"""시범 지도 수집 결과를 판정해서 웹데이터 값으로 바꾼다. 규칙: 웹데이터_판정규칙_v0.md 3장.

python -I judge_web_pilot.py --dir <시범100 폴더> --web 원본자료/웹데이터_달서구_v0_20261124.csv --judge 매칭도구/judge_signals.py --date 2026-11-24

1) 대상목록.csv로 수집양식(빈 판정)을 만들고 judge_signals.py(1차 판정 도구, 수집안내 3장)로 최소주문·1인입장을 판정한다.
2) 웹 값으로 바꾼다:
   - 네이버·카카오 모두 못 찾음 → 모름 (지도_못찾음=예)
   - 2인분이상_확정/추정 → 2인분 이상 (확인됨/추정), 1인분가능_확정 → 1인분 가능 (확인됨)
   - 미상이면서: 매장 메뉴가 있고, 대표 메뉴에 가격이 있고, 2인분 조건 신호(리뷰 1건·양/크기 표기·배달 메뉴 인분 표기 등 검토필요)가 없고,
     업종이 '1인분 가격 표기 불신 업종'이 아니면 → 1인분 가능 (추정)
   - 그 밖 미상: 한 그릇 업종이면 1인분 가능 (업종 기준), 아니면 모름
출력: <dir>/판정_1차.csv, <dir>/근거전체.csv, <dir>/웹판정_시범.csv
"""
import argparse
import csv
import glob
import os
import re
import subprocess
import sys
from collections import Counter

DISTRUST = {"돼지고기 구이/찜", "소고기 구이/찜", "닭/오리고기 구이/찜", "곱창 전골/구이", "요리 주점", "횟집",
            "해산물 구이/찜", "족발/보쌈", "복 요리 전문", "마라탕/훠궈"}
PRICE = re.compile(r"\d{1,3}(,\d{3})+\s*원?|\d{4,6}\s*원|\d+(\.\d)?\s*만\s*원")
SIDE_NOTE = "곁들임 메뉴(볶음밥·사리 등)에만 조건"      # judge_signals.py 비고 문구
STORE_NOTE = "첫 주문·기본 주문 규칙이라 가게 전체"     # judge_signals.py 비고 문구
# 포장·배달 메뉴는 매장 단품 근거가 아님. 소/중/대 크기 메뉴도 단품이 아님(Codex 검증 11-24: 조암회 '막회(소)')
MULTI = re.compile(r"[2-9]\s*(~\s*\d\s*)?인|두\s*명|세\s*명|\(\s*[소중대]\s*\)|[小中大]|\s[소중대]\s|세트|모듬|모둠|코스|포장|배달|마리")  # 마리: Codex 2라운드(별빛포차 '닭도리탕(1마리)')
# 원문 어디에든 가게 전체에 거는 주문 규칙이 있으면 '일부 메뉴'로 낮추지 않는다(Codex 검증 11-24: 샤브샤브마루 '주문은 2인부터')
STORE_RAW = re.compile(r"주문\s*은\s*[2-9]\s*인|[2-9]\s*인\s*(분\s*)?(이상\s*)?부터\s*(주문|가능)|인원\s*수?\s*대로|인원\s*수\s*만큼|첫\s*주문|기본\s*[2-9]\s*인")
# '1.5kg 이상 기본 주문 받습니다(3인)'처럼 1차 도구 조건식(COND2)이 놓치는 가게 전체 기본 주문 규칙 (Codex 3라운드: 예감쪽갈비)
BASE_ORDER = re.compile(r"기본\s*주문[^/|;]{0,15}?\(\s*([2-9])\s*인\s*\)|\(\s*([2-9])\s*인\s*\)\s*기본\s*주문")
COND_RAW = re.compile(r"[2-9]\s*인\s*분?\s*(이상|부터)")


def single_items(menu, raw=()):
    """대표메뉴 칸에서 2인 이상·크기·세트·포장 표기가 없고 가격이 있는 단품 메뉴.
    raw(그 가게 원문 줄들)에서 같은 메뉴 이름이 2인 조건과 함께 나오면 단품으로 보지 않는다."""
    out = []
    cond_lines = [t for t in raw if COND_RAW.search(t)]
    for x in re.split(r";", menu or ""):
        if not PRICE.search(x) or MULTI.search(x):
            continue
        key = re.sub(r"\s+", "", re.split(r"[\(\[（\d]", re.sub(r"^\s*\[[^\]]*\]\s*", "", x))[0])[:4]
        if len(key) >= 2 and any(key in re.sub(r"\s+", "", t) for t in cond_lines):
            continue
        out.append(x.strip())
    return out


def num(s):
    try:
        return int(str(s).strip() or 0)
    except ValueError:
        return 0


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def signals(paths):
    """수집 결과에서 가게별 찾음·대표메뉴·메뉴정보·숫자 칸을 읽는다."""
    meta = {}
    for p in paths:
        txt = open(p, encoding="utf-8", errors="replace").read()
        s = txt.find('"수집ID"')
        if s < 0:
            continue
        for r in csv.DictReader(txt[s:].split("```")[0].splitlines()):
            k = {kk.split("(")[0]: (v or "") for kk, v in r.items() if kk}
            sid = k.get("수집ID", "").strip()
            if sid:
                m = meta.setdefault(sid, dict(k, 찾음들=set(), 원문들=[]))
                m["찾음들"].add(k.get("찾음", "").strip())
                if k.get("근거_원문"):
                    m["원문들"].append(k["근거_원문"])
    return meta


JS = None   # judge_signals 모듈 (main에서 --judge 경로로 읽음)


def main():
    global JS
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--web", required=True)
    ap.add_argument("--judge", required=True)
    ap.add_argument("--form-head", required=True, help="수집양식 머리줄을 가져올 파일(대구전역 사전입력)")
    ap.add_argument("--date", default="2026-11-24")
    a = ap.parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location("judge_signals", a.judge)
    JS = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(JS)
    target = rd(os.path.join(a.dir, "대상목록.csv"))
    web = {r["상가업소번호"]: r for r in rd(a.web)}
    with open(a.form_head, encoding="utf-8-sig", newline="") as f:
        head = next(csv.reader(f))
    form = os.path.join(a.dir, "수집양식_시범.csv")
    with open(form, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=head, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for t in target:
            row = {h: "" for h in head}
            row.update({head[0]: t["수집ID"], "상호": t["상호"], "구군": "달서구", "도로명주소": t["도로명주소"], "상권_업종소분류": t["업종_소분류"]})
            w.writerow(row)
    outs = sorted(glob.glob(os.path.join(a.dir, "out_*.csv")))
    j1 = os.path.join(a.dir, "판정_1차.csv")
    subprocess.run([sys.executable, "-I", a.judge, form, *outs, "--out", j1, "--evidence", os.path.join(a.dir, "근거전체.csv"), "--date", a.date], check=True)

    meta = signals(outs)
    J = rd(j1)
    col = lambda p: next(h for h in J[0] if h.startswith(p))
    MINO, ENT, NOTE = col("최소주문_판정"), col("1인입장_판정"), col("비고")
    res = []
    for r in J:
        sid = r[col("수집ID")]
        wv = web[sid]
        m = meta.get(sid, {})
        found = "예" in m.get("찾음들", set())
        mino, note = r[MINO], r[NOTE]
        scope = r[col("조건_적용범위")]
        menu, info = m.get("대표메뉴", ""), m.get("메뉴정보", "")
        distrust = wv["업종_소분류"] in DISTRUST
        raw = m.get("원문들", [])
        store_rule = any(STORE_RAW.search(t) for t in raw)
        reason, memo, check = "", "", ""
        bo = next((mm for t in raw for mm in [BASE_ORDER.search(t)] if mm), None)
        base_n = ""
        if bo and not mino.startswith("2인분이상"):
            mino, scope, base_n = "2인분이상_확정", "가게 전체", bo.group(1) or bo.group(2)
            memo = "기본 주문 규칙(원문): " + bo.group(0)
        # 결정 (11-24) 곁들임에만 붙은 조건은 최소 주문 근거가 아니다(수집안내 3장) → 조건 없음으로 보고 아래 미상 경로로
        if mino.startswith("2인분이상") and SIDE_NOTE in note:
            memo = "곁들임 메뉴에만 2인분 조건(최소 주문 근거 아님)"
            mino = "미상"
        # 결정 3 (11-24) '가게 전체'인데 가게 규칙(첫 주문·기본 N인분)이 아니고, 조건 없는 한 그릇 단품 가격이 대표 메뉴에 있으면 '일부 메뉴'
        #   단, 1인분 가격 표기 불신 업종은 단품 가격을 믿지 않으므로 바꾸지 않는다
        if (mino.startswith("2인분이상") and scope == "가게 전체" and STORE_NOTE not in note and not store_rule
                and not distrust and single_items(menu, raw)):
            scope = "일부 메뉴"
            memo = "조건 없는 단품이 있어 일부 메뉴로 봄: " + "; ".join(single_items(menu, raw)[:2])
        # 결정 2 (11-24) 혼자 입장: 리뷰·답글 판정이 먼저, 없으면 '혼자' 태그 3건 이상 또는 '혼밥하기 좋아요' 5명 이상 → 가능(추정)
        ent = {"가능": "가능", "불가": "불가"}.get(r[ENT], "모름")
        ent_lv = "확인됨" if ent != "모름" else ""
        if ent == "모름" and (num(m.get("혼자_태그수")) >= 3 or num(m.get("혼밥키워드수")) >= 5):
            ent, ent_lv = "가능", "추정"
        if not m:
            yn, lv, reason = "모름", "없음", "수집 결과 없음"
        elif not found:
            yn, lv, reason = "모름", "없음", "지도에서 못 찾음"
        elif mino.startswith("2인분이상") and scope == "일부 메뉴":
            # 결정 1 (11-24) 일부 메뉴만 2인분 → 1인분 가능 + 메모
            yn, lv = "1인분 가능", "추정"
            memo = (memo + " / " if memo else "") + "일부 메뉴 2인분"
            reason = "일부 메뉴에만 2인분 조건"
            if distrust:   # 사용자 결정 (11-24): 불신 업종은 1인분 추정으로 두되 팀이 따로 확인
                check = "예"
        elif mino.startswith("2인분이상"):
            yn, lv = "2인분 이상", "확인됨" if mino.endswith("확정") else "추정"
        elif mino == "1인분가능_확정":
            yn, lv = "1인분 가능", "확인됨"
        else:
            # 2인분 조건 신호는 잘린 비고가 아니라 원문 전체에서 1차 도구와 같은 조건식(COND2)으로 찾는다 (Codex 2라운드: 중화당반점)
            #   양·크기·세트 표기('2인세트', '소(2~3인)')는 수집안내 3장·1차 도구와 같이 최소 주문 조건으로 보지 않는다
            cond_raw = any(JS.COND2.search(t) and not JS.side_only(t) for t in raw)
            ok = info == "매장메뉴" and single_items(menu, raw) and not cond_raw and not distrust and not store_rule
            if ok:
                yn, lv, reason = "1인분 가능", "추정", "한 그릇 단위 가격, 2인분 조건 없음"
            elif wv["업종_갈래"] == "한 그릇 업종":
                yn, lv, reason = "1인분 가능", "업종 기준", f"메뉴정보={info or '?'}"
            else:
                yn, lv, reason = "모름", "없음", f"메뉴정보={info or '?'}" + ("; 1인분 가격 불신 업종" if wv["업종_소분류"] in DISTRUST else "")
        res.append({
            "상가업소번호": sid, "상호": wv["상호"], "업종_소분류": wv["업종_소분류"], "업종_갈래": wv["업종_갈래"],
            "지도_못찾음": "" if found else "예", "메뉴정보": m.get("메뉴정보", ""), "대표메뉴": m.get("대표메뉴", ""),
            "1차_최소주문": mino, "1차_인분": base_n or r.get("최소주문_인분", ""), "1차_범위": r[col("조건_적용범위")],
            "1인분_여부": yn, "근거_수준": lv, "1인분_메모": memo, "따로_확인": check, "조건_범위": scope if mino.startswith("2인분이상") else "",
            "혼자_입장": ent, "혼자_근거_수준": ent_lv, "판정_이유": reason,
            "혼자_태그수": m.get("혼자_태그수", ""), "동행태그_리뷰수": m.get("동행태그_리뷰수", ""),
            "혼밥키워드수": m.get("혼밥키워드수", ""), "키워드참여수": m.get("키워드참여수", ""),
            # 사용자 결정 (11-24): 비율은 혼자 입장 판정에 쓰지 않고 칸으로만(혼밥 손님이 많은 곳인지 보는 용도)
            "혼밥_키워드_비율": (f"{100 * num(m.get('혼밥키워드수')) / num(m.get('키워드참여수')):.1f}"
                            if num(m.get("키워드참여수")) > 0 and m.get("혼밥키워드수", "").strip() else ""),
            "확인한_리뷰수": m.get("확인한_리뷰수", ""), "1차_비고": note,
        })
    out = os.path.join(a.dir, "웹판정_시범.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys()), quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(res)
    print(f"{len(res)}곳 -> {out}")
    print("지도 못 찾음:", sum(1 for r in res if r["지도_못찾음"]))
    print("메뉴정보:", dict(Counter(r["메뉴정보"] for r in res)))
    for g in ("2인분 의심", "한 그릇 업종", "그 밖"):
        x = [r for r in res if r["업종_갈래"] == g]
        print(f"[{g} {len(x)}]", dict(Counter((r["1인분_여부"], r["근거_수준"]) for r in x)))
    print("혼자_입장:", dict(Counter(r["혼자_입장"] for r in res)))


if __name__ == "__main__":
    main()
