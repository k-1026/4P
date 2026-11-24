"""수집한 신호(메뉴 표기·사장님 답글·방문자 리뷰)로 수집양식의 판정 칸을 채운다.

판정 규칙은 `2인분식당_데이터체크_및_수집안내.md` 3장을 그대로 옮겼다. 규칙에 없는 부분은 아래 '적용 기준'에 적었다.

쓰는 법:
  python -I judge_signals.py 수집양식.csv 신호원문.csv [신호원문2.csv ...] --out 결과양식.csv --evidence 근거전체.csv [--date 2026-11-21]

신호원문 CSV 머리줄 (Aside 수집 결과 형식):
  수집ID, 찾음(예/아니오), 플랫폼_상호, 대표메뉴, 근거_종류(메뉴표기/사장답글/방문자리뷰/없음), 근거_출처(네이버/카카오),
  근거_원문, 근거_작성일, 근거_URL, 혼자_태그수, 누구와_태그_전체수, 메모

최소주문_판정 (3장 규칙):
  2인분이상_확정  메뉴 표기 또는 사장님 답글에 2인분 이상 '조건'이 있음 (예: "2인분부터", "2인 이상 주문", "최소 2인")
  1인분가능_확정  1인분 메뉴 표기, 또는 "1인분 가능" 사장님 답글
  2인분이상_추정  서로 다른 방문자 리뷰 2건 이상이 같은 조건을 말함
  미상            위에 해당하지 않음 (1인분 가능으로 보지 않음)

적용 기준 (규칙 표에 없어서 정한 것, 2026-11-21):
  - 메뉴에 2인 조건과 1인분 메뉴가 같이 있으면 2인분이상_확정 + 조건_적용범위=일부 메뉴 (산갈래닭갈비 예시와 같은 방식).
  - '2인분(400g)', '2~3인', '(소)', '2인용', '2인 세트'처럼 양·크기만 적은 표기는 조건으로 보지 않고 비고에 '검토필요'로 남긴다.
  - '1인분 추가'처럼 추가 주문 단위만 1인분인 표기는 1인분가능_확정으로 보지 않고 '검토필요'로 남긴다.
  - 1인입장_판정: 사장님 답글이 있으면 그것으로, 없으면 서로 다른 리뷰 2건 이상이 같은 쪽을 말할 때만 불가/가능. 양쪽이 섞이면 미상 + 비고.
  - 공공DB(착한가격업소·대구푸드) 메뉴 원문도 메뉴 표기로 본다(출처를 그대로 남김).
  - (시험 5곳을 보고 추가) '1인분가능_확정'은 '1인 세트', '혼밥 메뉴', '나홀로', '1인분 주문 가능'처럼 혼자 주문을 직접 말하는 표기만 쓴다.
    '안창살(1인분)', '만두(1인분)'처럼 값·양 단위로만 쓴 '1인분'은 검토필요로 남긴다(고기집은 1인분 값을 적고도 2인분부터 받는 곳이 있음).
  - 배민·요기요 등 배달앱 메뉴는 매장 근거가 아니므로 판정에서 빼고 검토필요로 남긴다.
  - 문장 없이 고른 리뷰 키워드("혼밥하기 좋아요")는 리뷰 근거로 세지 않고, 키워드 수만 비고에 적는다.
"""
import argparse, csv, re
from collections import defaultdict

NUMW = r"([2-5]|두|세|네|다섯)"
# 최소 주문 조건. 숫자는 최소주문_인분 칸에 옮긴다 (2026-11-21: 첫 주문 N인분, (N인이상), N분이상 오타, 기본 N인 등 추가)
COND2 = re.compile(
    r"첫\s*주문\S{0,3}\s*" + NUMW + r"\s*인\s*분?"
    r"|" + NUMW + r"\s*인\s*분?\s*(이상|부터)(?!\s*(주문\s*)?(시|이면|하면)?\s*(서비스|무료|할인|증정|제공))"
    r"|최소\s*" + NUMW + r"\s*인"
    r"|" + NUMW + r"\s*분\s*이상\s*주문"
    r"|기본\s*" + NUMW + r"\s*인"
    r"|1\s*인\s*(분)?\s*(주문|판매)\s*(불가|안\s*됨|안됩니다|안\s*돼)")
COND2_RAW = COND2
# (2026-11-23 대구 전역 판정에서 추가) 조건처럼 보이지만 매장 최소 주문이 아닌 경우를 뺀다
_AFTER_NOT = re.compile(r"^.{0,25}?(서비스|무료|할인|증정|먹기\s*적당|추천|권장|먹은|먹었|먹고|먹어|시켰|시킴|냄비에|포장|배달)")
_BEFORE_NOT = re.compile(r"(포장|배달|추가)[^/|·\n]{0,10}$")
SIDE_ITEM = re.compile(r"볶음밥|보끔밥|사리|공기\s*밥|공깃밥|라면|음료|주먹밥")


class _CondFilter:
    """COND2와 같게 쓰되, 포장·배달·추가 주문·혜택·권유·먹은 양 이야기는 조건에서 뺀다."""
    def _ok(self, t, m):
        if _AFTER_NOT.search(t[m.end(): m.end() + 30]):
            return False
        if _BEFORE_NOT.search(t[max(0, m.start() - 14): m.start()]):
            return False
        return True

    def finditer(self, t):
        return (m for m in COND2_RAW.finditer(t or "") if self._ok(t, m))

    def search(self, t):
        return next(self.finditer(t), None)


COND2 = _CondFilter()


def side_only(text):
    """조건이 붙은 메뉴가 모두 볶음밥·사리 같은 곁들임이면 True"""
    segs = []
    for m in COND2.finditer(text):
        s = max(text.rfind("/", 0, m.start()), text.rfind("|", 0, m.start()), text.rfind("\n", 0, m.start()))
        segs.append(text[s + 1: m.end() + 5])
    return bool(segs) and all(SIDE_ITEM.search(x) for x in segs)


NUM_OF = {"두": 2, "세": 3, "네": 4, "다섯": 5}
# 혼자면 더 받는 표기: '(2인이상) 1인분 9000 / 8,000원' → 1인분 주문은 되지만 값이 다름
SOLO_PREMIUM = re.compile(r"2\s*인\s*이상\)?\s*\(?\s*1\s*인\s*분\s*[\d,]{3,}|혼자\s*(는|면|일\s*때)\s*[\d,]{3,}\s*원")
UNIT2 = re.compile(r"2\s*인\s*분|2\s*~\s*3\s*인|3\s*~\s*4\s*인|\(\s*소\s*\)|2\s*인\s*용|2\s*인\s*세트|2\s*인\s*기준")
# 혼자 주문을 직접 말하는 표기만 1인분가능 근거로 본다 (2026-11-21 시험 5곳을 보고 정함)
ONE_MENU = re.compile(r"1\s*인\s*(세트|메뉴|정식|코스|상)|혼밥|나홀로|혼자\s*(세트|메뉴)|1\s*인\s*분\s*(도\s*)?(주문|가능|판매)")
# '안창살(1인분)', '만두(1인분)'처럼 값이나 양의 단위로만 쓴 1인분 → 검토필요
ONE_UNIT = re.compile(r"1\s*인\s*분|\(\s*1\s*인\s*\)")
DELIVERY = re.compile(r"배달|배민|요기요|쿠팡")
ONE_ADD = re.compile(r"1\s*인\s*분?\s*추가|추가\s*1\s*인")
# '1인분 주문 가능'(최소주문)과 '혼자 와도 된다'(1인입장)를 나눈다 (2026-11-21: 1인분은 있어도 혼자는 안 받는 곳이 있음)
ONE_OK_REPLY = re.compile(r"1\s*인\s*분?\s*(도|은|주문)?\s*(가능|됩니다|되세요|돼요)")
ENTRY_OK_REPLY = re.compile(r"혼자\s*(오셔도|오셔서도|드셔도|와도|오시는)|혼밥\s*(가능|환영|하셔도|손님)|1\s*인\s*(손님|고객)\s*(도\s*)?(환영|가능)")
# 매장 메뉴에 혼밥·나홀로·혼자 세트가 있으면 혼자 입장 가능 근거로 본다('1인분'·'1인 세트'만으로는 보지 않음)
ENTRY_OK_MENU = re.compile(r"혼밥|나홀로|혼자\s*(세트|메뉴)")
ENTRY_NO = re.compile(
    r"혼자\s*(는|서는|선|오면|오시면)?\s*(안\s*(받|돼|된|됨|되)|못\s*(가|갑|들어|받|와|옵))|혼자\s*밥도\s*못"
    r"|1\s*인\s*(손님|입장|방문|은|이용|식사는?|식사)?\s*(안\s*받|불가|사절|안\s*돼|안됨|안돼|못\s*(가|갑))"
    r"|혼밥\s*(은|는)?\s*(불가|안\s*(돼|됨|되|받)|거절|사절)|입장\s*불가|2\s*인\s*이상\s*(입장|이용|방문)"
    r"|1\s*명\s*(은|이면|이라)?.{0,15}(안\s*된|안돼|안\s*돼|불가|안\s*받)"
    r"|(혼밥|혼자|1\s*인)\s*(손님|오시는\s*분|온\s*분)\s*(은|는)?.{0,15}(이후에|이후|부터)\s*(오|와|가능)")
ENTRY_OK = re.compile(r"혼자(서)?\s*(가도|와도|먹기|먹어도|방문|가기|오기)\s*(좋|괜찮|편|가능|부담\s*없)|혼자\s*(와도|가도|왔는데도|갔는데도|왔는데|갔는데)\s*(반갑|친절|눈치\s*안|잘\s*해|편하게|괜찮)|혼밥\s*(가능|하기\S{0,3}\s*(좋|편|괜찮|딱)|환영|하러|했)|1\s*인\s*(가능|손님\s*환영|도\s*가능)|혼자\s*(먹었|왔|갔|방문했)")
TIME = re.compile(r"점심|피크|저녁|주말|바쁜\s*시간|\d{1,2}\s*시\s*(이후|이전|전|부터|까지)")
# 가게 규칙으로 쓰인 조건(메뉴 하나가 아니라 가게 전체에 적용)
STORE_RULE = re.compile(r"^[\s※·\-\*<\[(（]*(기본|첫|주\s*메뉴|추가|모든\s*메뉴|전\s*메뉴|고기는|고기\s*주문)|기본\s*주문|첫\s*주문|모든\s*메뉴")

MENU_KINDS = ("메뉴표기", "공공DB")


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("form"); p.add_argument("signals", nargs="+")
    p.add_argument("--out", required=True); p.add_argument("--evidence", required=True)
    p.add_argument("--date", default="2026-11-21")
    a = p.parse_args()

    F = list(csv.DictReader(open(a.form, encoding="utf-8-sig")))
    hdr = list(F[0].keys())
    for c in ("최소주문_인분", "혼밥_유형", "검토필요"):
        if c not in hdr:
            hdr.append(c)
        for f in F:
            f.setdefault(c, "")
    H = lambda prefix: next(h for h in hdr if h.startswith(prefix))
    ID, MINO, ENT, TIMEC, SCOPE = H("수집ID"), H("최소주문_판정"), H("1인입장_판정"), H("시간대제한"), H("조건_적용범위")
    MENU = H("대표메뉴"); ALONE, ALLTAG = H("혼자_태그"), H("동행태그"); DATE, WHO, NOTE = H("확인일"), H("확인자"), H("비고")

    ev = defaultdict(list); meta = {}
    for path in a.signals:
        txt = open(path, encoding="utf-8", errors="replace").read()
        s = txt.find('"수집ID"'); s = txt.find("수집ID,") if s < 0 else s
        if s < 0:
            print("머리줄 없음:", path); continue
        body = txt[s:].split("```")[0]
        for r in csv.DictReader(body.splitlines()):
            sid = (r.get("수집ID") or "").strip()
            if not sid:
                continue
            k = {kk.split("(")[0]: v for kk, v in r.items() if kk}
            # 메뉴판 사진은 사진 주소의 날짜(예: .../20200129_49/...)를 등록일로 쓴다
            if not k.get("근거_작성일") and "메뉴판사진" in (k.get("근거_출처") or ""):
                d = re.search(r"/(20\d{2})(\d{2})(\d{2})_", k.get("근거_URL") or "")
                if d:
                    k["근거_작성일"] = f"{d.group(1)}-{d.group(2)}-{d.group(3)}(사진 등록일)"
            meta.setdefault(sid, k)
            if k.get("근거_종류") and k["근거_종류"] != "없음":
                ev[sid].append(k)
    # 공공DB 근거(사전입력된 근거1/근거2)도 메뉴 표기로 넣는다
    for f in F:
        for n in (1, 2):
            kind, src, txt = f.get(H(f"근거{n}_종류"), ""), f.get(H(f"근거{n}_출처"), ""), f.get(H(f"근거{n}_원문"), "")
            if kind == "공공DB" and txt:
                ev[f[ID]].append({"근거_종류": "공공DB", "근거_출처": src, "근거_원문": txt, "근거_작성일": "", "근거_URL": ""})

    all_ev = []
    done = 0
    for f in F:
        sid = f[ID]
        if sid not in meta:
            continue
        done += 1
        m = meta[sid]
        notes = []
        E_all = ev.get(sid, [])
        # 배달앱 메뉴는 매장 근거가 아니므로 판정에서 뺀다
        is_deliv = lambda e: e["근거_종류"] in MENU_KINDS and (DELIVERY.search(e.get("근거_출처", "")) or DELIVERY.search(e.get("메모", "")))
        # 문장 없이 고른 키워드 리뷰는 근거 문장으로 보지 않는다
        is_kw = lambda e: e["근거_종류"] == "방문자리뷰" and "키워드" in (e.get("메모", "") or "")
        deliv = [e for e in E_all if is_deliv(e)]
        E = [e for e in E_all if not is_deliv(e) and not is_kw(e)]
        if deliv:
            hits = [norm(e["근거_원문"])[:50] for e in deliv if COND2.search(e["근거_원문"]) or ONE_UNIT.search(e["근거_원문"]) or ONE_MENU.search(e["근거_원문"])]
            if hits:
                notes.append(f"검토필요: 배달 메뉴에만 인분 표기 {len(hits)}건 → " + " | ".join(hits[:2]))
        menu_cond = [e for e in E if e["근거_종류"] in MENU_KINDS + ("사장답글",) and COND2.search(e["근거_원문"])]
        menu_one = [e for e in E if e["근거_종류"] in MENU_KINDS and ONE_MENU.search(e["근거_원문"]) and not ONE_ADD.search(e["근거_원문"])]
        reply_one = [e for e in E if e["근거_종류"] == "사장답글" and ONE_OK_REPLY.search(e["근거_원문"])]
        rev_cond = {norm(e["근거_원문"]): e for e in E if e["근거_종류"] == "방문자리뷰" and COND2.search(e["근거_원문"])}
        unit_only = [e for e in E if e["근거_종류"] in MENU_KINDS and UNIT2.search(e["근거_원문"]) and not COND2.search(e["근거_원문"])]
        add_only = [e for e in E if e["근거_종류"] in MENU_KINDS and ONE_ADD.search(e["근거_원문"])]
        one_unit = [e for e in E if e["근거_종류"] in MENU_KINDS and ONE_UNIT.search(e["근거_원문"]) and not ONE_MENU.search(e["근거_원문"])
                    and not ONE_ADD.search(e["근거_원문"]) and not SOLO_PREMIUM.search(e["근거_원문"]) and not COND2.search(e["근거_원문"])]
        if one_unit:
            notes.append(f"검토필요: '1인분'이 값·양 단위로만 쓰임 {len(one_unit)}건 → " + " | ".join(norm(e["근거_원문"])[:40] for e in one_unit[:2]))

        used = []
        premium = [e for e in E if e["근거_종류"] in MENU_KINDS + ("사장답글",) and SOLO_PREMIUM.search(e["근거_원문"])]
        if premium:
            # '(2인이상) 1인분 9000'은 1인분도 팔되 값이 다른 것이므로 최소 주문 조건으로 보지 않는다.
            # 같은 메뉴(예: 돼지찌개)의 다른 줄 '(2인이상) 9,000원'도 같은 뜻으로 본다
            pw = set(re.findall(r"[가-힣]{2,}", re.sub(r"인분|인이상|이상", " ", premium[0]["근거_원문"])))
            menu_cond = [e for e in menu_cond if not SOLO_PREMIUM.search(e["근거_원문"])
                         and not (set(re.findall(r"[가-힣]{2,}", re.sub(r"인분|인이상|이상", " ", e["근거_원문"]))) & pw)]
            menu_one = premium[:1] + menu_one
            notes.append("혼자면 1인분 값을 더 받음 → " + norm(premium[0]["근거_원문"])[:60])

        def nmin(es):
            ns = []
            for e in es:
                for mm in COND2.finditer(e["근거_원문"]):
                    d = re.search(r"[2-5]|두|세|네|다섯", mm.group(0))
                    if d:
                        ns.append(NUM_OF.get(d.group(0), int(d.group(0)) if d.group(0).isdigit() else 2))
            return max(ns) if ns else ""
        if menu_cond:
            f[MINO] = "2인분이상_확정"; used = menu_cond[:1]
            f["최소주문_인분"] = nmin(menu_cond)
            head = re.sub(r"^\s*([\(（〈<\[][^\)）〉>\]]*[\)）〉>\]]\s*)+", "", menu_cond[0]["근거_원문"])   # 앞의 (특미)·〈특선〉 같은 꼬리표 떼기
            item = norm(re.split(r"[\(\[（:]|\d", head)[0]).replace(" ", "")
            item = re.sub(r"^(네이버|카카오)\s*:\s*", "", item)
            reps = [re.sub(r"^(네이버|카카오):", "", x.replace(" ", "")) for x in re.split(r"[;/,]", m.get("대표메뉴", "")) if x.strip()]
            reps = [re.sub(r"\(.*", "", x) for x in reps if x]
            if all(side_only(e["근거_원문"]) for e in menu_cond):
                f[SCOPE] = "일부 메뉴"      # 볶음밥·사리 같은 곁들임에만 붙은 조건
                notes.append("적용범위: 곁들임 메뉴(볶음밥·사리 등)에만 조건")
            elif any(STORE_RULE.search(e["근거_원문"]) for e in menu_cond):
                f[SCOPE] = "가게 전체"      # '첫 주문 N인분', '기본 3인분부터' 같은 가게 규칙
                notes.append("적용범위: 첫 주문·기본 주문 규칙이라 가게 전체")
            elif menu_one or reply_one:
                # 1인분 메뉴가 같이 있으면 조건은 일부 메뉴에만 붙은 것
                f[SCOPE] = "일부 메뉴"; used += (menu_one or reply_one)[:1]
            elif item and reps and any(item in r_ or r_ in item for r_ in reps if len(r_) >= 2):
                f[SCOPE] = "가게 전체"
                notes.append(f"적용범위: 조건이 붙은 '{item}'이 대표메뉴")
            elif item and reps and not any(item in r_ or r_ in item for r_ in reps):
                f[SCOPE] = "일부 메뉴"
                notes.append(f"적용범위: 조건이 붙은 '{item}'은 대표메뉴가 아님")
            else:
                notes.append("검토필요: 조건 적용범위(가게 전체/일부 메뉴) 확인")
            if any("메뉴판사진" in e.get("근거_출처", "") for e in menu_cond[:1]):
                notes.append("근거가 메뉴판 사진(등록일은 근거1_작성일)")
        elif menu_one or reply_one:
            f[MINO] = "1인분가능_확정"; used = (menu_one or reply_one)[:2]
        elif len(rev_cond) >= 2:
            f[MINO] = "2인분이상_추정"; used = list(rev_cond.values())[:2]
            f["최소주문_인분"] = nmin(list(rev_cond.values()))
        else:
            f[MINO] = "미상"
            if len(rev_cond) == 1:
                notes.append("리뷰 1건만 2인 조건을 말함(추정 기준 2건 미달)")
        if unit_only:
            notes.append("검토필요: 양·크기 표기만 있음 → " + " | ".join(norm(e["근거_원문"])[:60] for e in unit_only[:2]))
        if add_only:
            notes.append("검토필요: '1인분 추가' 표기 → " + norm(add_only[0]["근거_원문"])[:60])

        # 1인입장
        r_no = [e for e in E if e["근거_종류"] == "사장답글" and ENTRY_NO.search(e["근거_원문"])]
        r_ok = [e for e in E if (e["근거_종류"] == "사장답글" and (ENTRY_OK.search(e["근거_원문"]) or ENTRY_OK_REPLY.search(e["근거_원문"])))
                or (e["근거_종류"] in MENU_KINDS and ENTRY_OK_MENU.search(e["근거_원문"]))]
        v_no = {norm(e["근거_원문"]): e for e in E if e["근거_종류"] == "방문자리뷰" and ENTRY_NO.search(e["근거_원문"])}
        v_ok = {norm(e["근거_원문"]): e for e in E if e["근거_종류"] == "방문자리뷰" and ENTRY_OK.search(e["근거_원문"])}
        v_no_time = [e for e in v_no.values() if TIME.search(e["근거_원문"])]
        if r_no and not r_ok:
            f[ENT] = "불가"; used += r_no[:1]
        elif len(v_no) >= 2 and v_no_time:
            # 시간대를 말하는 거절('점심시간엔 1명 안 됨')은 다른 시간의 '혼밥 좋아요'와 엇갈림으로 보지 않는다
            f[ENT] = "불가"; used += v_no_time[:1] + [e for e in v_no.values() if e not in v_no_time][:1]
            notes.append(f"1인입장=리뷰 {len(v_no)}건, 시간대 제한" + (f"(혼자 가능 리뷰 {len(v_ok)}건은 다른 시간일 수 있음)" if v_ok else ""))
        elif r_ok and not r_no:
            f[ENT] = "가능"; used += r_ok[:1]
        elif len(v_no) >= 2 and not v_ok:
            f[ENT] = "불가"; used += list(v_no.values())[:1]; notes.append("1인입장=리뷰 2건 이상")
        elif len(v_ok) >= 2 and not v_no:
            f[ENT] = "가능"; used += list(v_ok.values())[:1]; notes.append("1인입장=리뷰 2건 이상")
        else:
            f[ENT] = "미상"
            if (v_no and v_ok) or (r_no and r_ok):
                notes.append("1인입장 근거가 엇갈림")
            elif v_no or v_ok:
                notes.append(f"1인입장 리뷰 {len(v_no) + len(v_ok)}건(기준 2건 미달)")
        tm = [e for e in (r_no + list(v_no.values())) if TIME.search(e["근거_원문"])]
        if tm:
            f[TIMEC] = norm(tm[0]["근거_원문"])[:80]

        # 혼밥 유형: 최소주문 × 1인입장
        mo, en, sc, n = f[MINO], f[ENT], f[SCOPE], f["최소주문_인분"]
        nn = f"{n}인분" if n else "N인분"
        if en == "불가" and f[TIMEC]:
            t = "특정 시간대 혼자 불가"
        elif en == "불가":
            t = "혼자 불가" + (" (1인분 메뉴는 있음)" if mo.startswith("1인분") else "")
        elif mo.startswith("2인분이상") and sc == "일부 메뉴":
            t = f"일부 메뉴만 {nn} 이상" + (" (혼자 입장 가능)" if en == "가능" else "")
        elif mo.startswith("2인분이상"):
            t = f"혼자 가능, {nn} 이상 주문" if en == "가능" else f"{nn} 이상 주문 (혼자 입장 미상)"
        elif mo.startswith("1인분"):
            t = ("혼자 1인분 가능" if en == "가능" else "1인분 메뉴 있음 (혼자 입장 미상)") + (" (혼자면 값이 더 비쌈)" if premium else "")
        elif en == "가능":
            t = "혼자 입장 가능 (최소주문 미상)"
        else:
            t = "미상"
        f["혼밥_유형"] = t

        # 근거 칸: 판정에 쓴 근거 먼저, 없으면 가장 앞 근거
        seen, pick = set(), []
        for e in used + E:
            key = (e["근거_종류"], norm(e["근거_원문"]))
            if key not in seen:
                seen.add(key); pick.append(e)
        for n in (1, 2):
            for c in ("종류", "출처", "원문", "URL", "작성일"):
                f[H(f"근거{n}_{c}")] = ""
        for n, e in enumerate(pick[:2], 1):
            f[H(f"근거{n}_종류")] = e["근거_종류"]; f[H(f"근거{n}_출처")] = e.get("근거_출처", "")
            f[H(f"근거{n}_원문")] = norm(e["근거_원문"])[:300]; f[H(f"근거{n}_URL")] = e.get("근거_URL", ""); f[H(f"근거{n}_작성일")] = e.get("근거_작성일", "")
        if m.get("대표메뉴"):
            f[MENU] = m["대표메뉴"]
        f[ALONE] = m.get("혼자_태그수", "")
        f[ALLTAG] = m.get("동행태그_리뷰수", "") or m.get("누구와_태그_전체수", "")
        extra = []
        if m.get("확인한_리뷰수"):
            extra.append(f"확인한 리뷰 {m['확인한_리뷰수']}개")
        if m.get("혼밥키워드수"):
            extra.append(f"'혼밥하기 좋아요' 키워드 {m['혼밥키워드수']}/{m.get('키워드참여수', '')}명")
        if extra:
            notes.append(", ".join(extra))
        f[DATE] = a.date; f[WHO] = "Aside(수집)·Claude(판정)"
        if m.get("찾음", "").startswith("아니"):
            notes.append("지도에서 가게를 찾지 못함")
        if m.get("메모"):
            notes.append("수집메모: " + norm(m["메모"])[:120])
        f[NOTE] = "; ".join([x for x in [f[NOTE]] + notes if x])
        f["검토필요"] = "예" if any(x.startswith("검토필요") or "엇갈림" in x for x in notes) else ""
        for e in E_all:
            all_ev.append({"수집ID": sid, "상호": f["상호"], **{k: e.get(k, "") for k in ("근거_종류", "근거_출처", "근거_원문", "근거_작성일", "근거_URL")},
                           "판정에서_뺌": "배달메뉴" if is_deliv(e) else ("키워드리뷰" if is_kw(e) else ""),
                           "2인조건": "O" if COND2.search(e["근거_원문"]) else "", "1인분표기": "O" if ONE_MENU.search(e["근거_원문"]) else "",
                           "혼자불가": "O" if ENTRY_NO.search(e["근거_원문"]) else "", "혼자가능": "O" if ENTRY_OK.search(e["근거_원문"]) else ""})

    with open(a.out, "w", encoding="utf-8-sig", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=hdr); w.writeheader(); w.writerows(F)
    if all_ev:
        with open(a.evidence, "w", encoding="utf-8-sig", newline="") as fo:
            w = csv.DictWriter(fo, fieldnames=list(all_ev[0].keys())); w.writeheader(); w.writerows(all_ev)
    from collections import Counter
    J = [f for f in F if f[ID] in meta]
    print(f"판정한 가게 {done}곳")
    for grp in ("DS", "DC"):
        g = [f for f in J if f[ID].startswith(grp)]
        if g:
            print(f"  {grp} {len(g)}곳 최소주문", dict(Counter(f[MINO] for f in g)), "1인입장", dict(Counter(f[ENT] for f in g)))
    print(f"근거 줄 {len(all_ev)}")


if __name__ == "__main__":
    main()
