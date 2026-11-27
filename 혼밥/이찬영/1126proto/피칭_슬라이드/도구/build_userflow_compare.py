# -*- coding: utf-8 -*-
"""피칭 8쪽 유저플로우 3쪽짜리 HTML(실제 · 계획 · 비교)을 만든다.

python3 -I 도구/build_userflow_compare.py [출력 경로]
  입력: 08_유저플로우_실제.html  (실제 쪽 그림과 공통 CSS를 여기서 가져옴)
  출력: 08_유저플로우_실제_계획_비교.html (출력 경로를 주면 그곳)

계획 쪽 그림(PLAN)과 비교 표(CMP)는 아래 문자열을 고친다.
근거: 재료/유저플로우/userflow.md (부록 계획 v0), 계획_실제_플로우_차이.md
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "08_유저플로우_실제.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "08_유저플로우_실제_계획_비교.html")

PLAN = '<div class="content">\n  <svg viewBox="0 0 832 288" role="img" aria-label="계획 플로우: 홈·요청, 위치 허용 갈림길, 진행, 에이전트 결과 갈림길, 가게 있음 갈림길, 추천 결과, 가게 상세, 끝, 결과 없음에서 조건 바꾸기">\n    <defs>\n      <marker id="pr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#22406E"/></marker>\n      <marker id="prg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8A93A2"/></marker>\n    </defs>\n    <!-- 1줄 -->\n    <rect class="n end" x="0" y="40" width="86" height="40" rx="20"/>\n    <text class="t" x="43" y="57" style="font-size:12px">시작</text>\n    <text class="s" x="43" y="71">휴대폰 웹</text>\n    <path class="a" d="M86,60 H106" marker-end="url(#pr)"/>\n\n    <rect class="n" x="108" y="26" width="124" height="68" rx="10"/>\n    <circle class="numc" cx="119" cy="37" r="7.5"/><text class="num" x="119" y="40.5" style="font-size:9px">1</text>\n    <text class="t" x="170" y="56">홈·요청</text>\n    <text class="s" x="170" y="72">예산 · \'시간이 없어요\'</text>\n    <text class="s" x="170" y="85">한 문장 요청 → \'찾기\'</text>\n    <path class="a" d="M232,60 H250" marker-end="url(#pr)"/>\n\n    <polygon class="d" points="290,30 330,60 290,90 250,60"/>\n    <text class="t" x="290" y="57" style="font-size:11px">위치</text>\n    <text class="t" x="290" y="71" style="font-size:11px">허용?</text>\n    <path class="a" d="M330,60 H350" marker-end="url(#pr)"/>\n    <text class="lb b" x="340" y="52" text-anchor="middle">예</text>\n    <text class="lb" x="290" y="106" text-anchor="middle">아니오 → 동성로</text>\n    <text class="lb" x="290" y="118" text-anchor="middle">중심 거리로 계속</text>\n\n    <rect class="n main" x="352" y="26" width="124" height="68" rx="10"/>\n    <circle class="numc" cx="363" cy="37" r="7.5"/><text class="num" x="363" y="40.5" style="font-size:9px">2</text>\n    <text class="t w" x="414" y="56">진행</text>\n    <text class="s w" x="414" y="72">에이전트가 일하는 동안</text>\n    <text class="s w" x="414" y="85">기다림 (단계 표시 미정)</text>\n    <path class="a" d="M476,60 H494" marker-end="url(#pr)"/>\n\n    <polygon class="d" points="536,28 578,60 536,92 494,60"/>\n    <text class="t" x="536" y="57" style="font-size:11px">모두</text>\n    <text class="t" x="536" y="71" style="font-size:11px">결과?</text>\n    <path class="a" d="M578,60 H604" marker-end="url(#pr)"/>\n    <text class="lb b" x="591" y="52" text-anchor="middle">예</text>\n    <text class="lb" x="536" y="106" text-anchor="middle">아니오 → 실패한</text>\n    <text class="lb" x="536" y="118" text-anchor="middle">항목 빼고 계산</text>\n\n    <polygon class="d" points="646,28 688,60 646,92 604,60"/>\n    <text class="t" x="646" y="57" style="font-size:11px">가게</text>\n    <text class="t" x="646" y="71" style="font-size:11px">있나?</text>\n    <path class="a" d="M688,60 H716" marker-end="url(#pr)"/>\n    <text class="lb b" x="702" y="52" text-anchor="middle">아니오</text>\n\n    <rect class="n" x="718" y="34" width="114" height="52" rx="10"/>\n    <text class="t" x="775" y="56">결과 없음</text>\n    <text class="s" x="775" y="72">조건 바꾸기 안내</text>\n    <!-- 결과 없음 → 홈 -->\n    <path class="a" d="M775,86 V140 H170 V96" marker-end="url(#pr)"/>\n    <text class="lb" x="760" y="134" text-anchor="end">\'조건 바꾸기\'</text>\n\n    <!-- 2줄 -->\n    <path class="a" d="M646,92 V172" marker-end="url(#pr)"/>\n    <text class="lb b" x="654" y="160">예 · 1~3곳</text>\n    <rect class="n main" x="584" y="174" width="124" height="62" rx="10"/>\n    <circle class="numc" cx="595" cy="185" r="7.5"/><text class="num" x="595" y="188.5" style="font-size:9px">3</text>\n    <text class="t w" x="646" y="200">추천 결과</text>\n    <text class="s w" x="646" y="215">3곳 · 총점 x.x / 10</text>\n    <text class="s w" x="646" y="228">이유 · \'AI 추천\' 라벨</text>\n    <path class="a" d="M584,205 H498" marker-end="url(#pr)"/>\n    <text class="lb" x="541" y="198" text-anchor="middle">카드 누르기</text>\n    <path class="a" d="M498,221 H584" marker-end="url(#pr)"/>\n    <text class="lb" x="541" y="234" text-anchor="middle">다른 가게 보기</text>\n\n    <rect class="n" x="372" y="174" width="124" height="62" rx="10"/>\n    <circle class="numc" cx="383" cy="185" r="7.5"/><text class="num" x="383" y="188.5" style="font-size:9px">4</text>\n    <text class="t" x="434" y="200">가게 상세</text>\n    <text class="s" x="434" y="215">1인 메뉴 · 가격 · 혼밥 후기</text>\n    <text class="s" x="434" y="228">본날 · 1인석(모르면 \'모름\')</text>\n    <path class="a" d="M372,205 H262" marker-end="url(#pr)"/>\n    <text class="lb" x="317" y="198" text-anchor="middle">이 가게로 가기</text>\n\n    <rect class="n end" x="130" y="185" width="130" height="40" rx="20"/>\n    <text class="t" x="195" y="210" style="font-size:12px">끝 · 갈 가게를 정함</text>\n\n    <path class="a dash" d="M434,236 V254" marker-end="url(#prg)"/>\n    <rect class="n dash" x="372" y="256" width="124" height="28" rx="8"/>\n    <text class="s" x="434" y="274" style="font-size:10.5px">다녀왔어요 [나중]</text>\n\n    <text class="leg" x="0" y="262">◇ 갈림길 · 진한 상자 = 에이전트가 일하는 단계</text>\n    <text class="leg" x="0" y="276">점선 = [나중] 스토리 · 웹페이지가 없을 때 spec만 보고 그림</text>\n  </svg>\n  </div>'

CMP = '<div class="content"><table class="cmp"><tr><th style="width:92px">단계</th><th style="width:250px">계획 (spec v0)</th><th>실제 웹앱 (2026-11-26)</th><th style="width:82px"></th></tr><tr><td><b>조건 넣기</b></td><td>한 화면에서 예산·\'시간이 없어요\'·한 문장 요청</td><td>채팅이 차례로 물음: 중요 순위 5개 → 업종 → 예산 → \'추천 시작\'</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>가중치</b></td><td>criteria.json 고정 열 + 혼밥 MBTI 배수</td><td>사용자가 고른 순위대로 33·27·20·13·7%</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>진행</b></td><td>기다리는 화면 (단계 표시 미정)</td><td>상의 ①~⑤가 채팅에 다 나옴 · 후보 20곳 카드 · 1차 점수표</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>상의</b></td><td>1·2위 0.5점 이하일 때만 · 점수는 안 바뀜</td><td>반론 뒤 사용자가 \'점수를 높일까요?\'를 고르면 점수가 바뀜</td><td><span class="bd k">팀 결정 필요</span></td></tr><tr><td><b>총점·검증</b></td><td>x.x / 10 · 검증은 안 보임</td><td>7.80점(소수 둘째 자리) · \'검증 8가지 중 8가지 통과\' 표시</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>가게 상세</b></td><td>추천 카드를 누름</td><td>지도 탭 목록에서 누름 (추천 카드 → 상세는 확인 중)</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>끝 · 다녀온 뒤</b></td><td>이 가게로 가기 · [나중] 다녀왔어요</td><td>길찾기(카카오맵) · 찜 · 혼밥일기(사진 필수)가 이미 있음</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>새 화면</b></td><td>–</td><td>위치 정보 시트 · 지도 탭 · 마이 탭</td><td><span class="bd d">달라짐</span></td></tr><tr><td><b>계획대로</b></td><td>위치 거부 문구 · \'AI 추천\' · \'사람 확인 전\' 라벨 · 1인석 \'모름\' · 1km 20곳</td><td>모두 있음</td><td><span class="bd s">같음</span></td></tr><tr><td><b>확인 못 함</b></td><td>결과 없음 · 에이전트 실패</td><td>아직 지나가 보지 못함</td><td><span class="bd u">확인 필요</span></td></tr></table></div>'

EXTRA_CSS = '\n/* 여러 쪽 묶음 */\n.deck{transform-origin:0 0}\n.stage{margin-bottom:24px;break-after:page;page-break-after:always}\n.stage:last-child{margin-bottom:0}\n.kind{position:absolute;left:38px;top:62px;font-size:11px;font-weight:800;color:#fff;background:var(--accent);border-radius:999px;padding:2px 9px}\n.kind.plan{background:var(--mute)}\ntable.cmp{width:832px;border-collapse:collapse;font-size:10.5px;line-height:1.35}\ntable.cmp th,table.cmp td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:middle}\ntable.cmp th{background:var(--panel);color:var(--navy);font-size:10.5px}\n.bd{display:inline-block;font-size:9.5px;font-weight:800;border-radius:999px;padding:1px 7px;white-space:nowrap}\n.bd.d{background:#E5ECF6;color:var(--navy)}\n.bd.k{background:var(--accent);color:#fff}\n.bd.s{background:#E3F1E6;color:#2E6B3A}\n.bd.u{background:#FDF3CF;color:#7A5C00}\n@media print{.deck{transform:none!important}.stage{margin:0}}\n'

HEAD = ('  <div class="brand">혼밥 · 팀 4P</div>\n'
        '  <div class="rule l"></div><div class="rule r"></div>\n'
        '  <div class="nav"><span>문제</span><span class="sep">›</span><span class="on">해결</span>'
        '<span class="sep">›</span><span>시장</span><span class="sep">›</span><span>BM</span>'
        '<span class="sep">›</span><span>MVP</span></div>\n')

SCRIPT = """<script>
(function(){
  const d=document.getElementById('deck');
  function fit(){ const k=Math.min(1,(innerWidth-16)/960); d.style.transform='scale('+k+')'; d.style.marginLeft=Math.max(0,(innerWidth-960*k)/2)+'px'; }
  addEventListener('resize',fit); fit();
})();
</script>"""


def stage(chip, kind, kclass, title, sub, content, src, pg):
    return ('<section class="stage">\n' + HEAD +
            '  <div class="chip">' + chip + '</div>\n'
            '  <div class="kind ' + kclass + '">' + kind + '</div>\n'
            '  <div class="title">' + title + '</div>\n'
            '  <div class="subtitle">' + sub + '</div>\n'
            '  ' + content + '\n'
            '  <div class="src">' + src + '</div>\n'
            '  <div class="pg">' + pg + '</div>\n'
            '  <div class="bar"></div>\n'
            '</section>')


def main():
    t = open(SRC, encoding="utf-8").read()
    css = t[t.index("<style>") + 7:t.index("</style>")]
    css = css.replace("@media print{ html,body{background:var(--bg)} .stage{transform:none!important;margin:0!important} }",
                      "@media print{ html,body{background:var(--bg)} }")
    s = t.index('<div class="content">')
    actual = t[s:t.index("</div>", t.index("</svg>")) + 6]
    pages = [
        stage("피치 2 · 해결", "실제", "", "유저플로우 — 순위 고르고, 밥톨이 상의 보고, 3곳 중 하나로 간다",
              "실제 웹 ‘혼밥 밥친구’를 휴대폰 화면으로 직접 써 본 순서 (2026-11-26)", actual,
              "출처: 10_에이전트/spec/userflow.md v1 · honbap-bapchingu.vercel.app (2026-11-26 직접 확인)", "8"),
        stage("피치 2 · 해결 · 부록", "계획", "plan", "계획 유저플로우 — 조건 걸고, 기다리고, 3곳을 받는다",
              "웹페이지가 생기기 전 spec v0의 스토리 US1~US5로 그린 순서", PLAN,
              "출처: 10_에이전트/spec/spec.md 4절 스토리 · 7.2 화면 목록 · spec/userflow.md 부록(계획 플로우 v0)", "8-1"),
        stage("피치 2 · 해결 · 부록", "비교", "", "계획과 실제 — 채팅으로 묻고, 상의를 보여 주고, 사용자가 고른다",
              "계획한 장면이 실제 앱에서 어떻게 바뀌었나 (C1~C8)", CMP,
              "출처: 10_에이전트/spec/계획_실제_플로우_차이.md · spec/userflow.md 4절 · '팀 결정 필요' = criteria.json의 '상의는 점수를 바꾸지 않는다'와 어긋남", "8-2"),
    ]
    html = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>혼밥 피칭 8쪽 · 유저플로우 실제·계획·비교 (960×540, 3쪽)</title>\n'
            '<style>' + css + EXTRA_CSS + '</style>\n</head>\n<body>\n<div class="deck" id="deck">\n' +
            "\n".join(pages) + '\n</div>\n' + SCRIPT + '\n</body>\n</html>\n')
    open(OUT, "w", encoding="utf-8").write(html)
    print("만듦:", OUT)


if __name__ == "__main__":
    main()
