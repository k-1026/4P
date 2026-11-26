"""터미널에서 돌려 보기.

    python main.py "달서구 국밥 만원"
    python main.py "성서 고기 1만2천원 이하 걸어서 10분" --origin 128.4958,35.8547
"""
import argparse
import sys

from agents import orchestrator, honbap, verify


def show(board):
    print("\n========== 답 ==========")
    if board.ask:
        print(board.ask)
        return
    if board.mode == "search":
        print(f"조건: {orchestrator._cond_text(board.conditions)}")
    if not board.final:
        print("조건에 맞는 혼밥 식당을 못 찾았어요.")
    for c in board.final[:5]:
        s, ctx = c["store"], c["context"]
        extra = [f"찾은 곳: {c['found_by']}" + ("" if c["in_team"] else " (팀 데이터에 없음)")]
        if c.get("link"): extra.append(f"팀 가게와 이음: {c['link']}")
        if c["map"]: extra.append(c["map"]["url"])
        if s.get("minP"): extra.append(f"{s['minP']:,}원부터")
        if ctx.get("walk_min") is not None: extra.append(f"걸어서 {ctx['walk_min']}분")
        if ctx.get("open_now") is True: extra.append("영업 중")
        print(f"\n· {s['name']} ({s.get('gu', '')}) — 혼밥 지수 {c['score']} · {honbap.LABEL.get(s.get('status'), '')}")
        if extra: print("  " + " · ".join(extra))
        for e in c["evidence"]: print("  - " + e)
        for f in c["flags"]: print("  ! " + f)
        for r in c["rejected"]: print("  ! 주의: " + dict((k, d) for k, d, _ in verify.CHECKS).get(r, r))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("text")
    p.add_argument("--origin", help="출발지 '경도,위도' (없으면 달서구청)")
    a = p.parse_args()
    origin = tuple(map(float, a.origin.split(","))) if a.origin else None
    show(orchestrator.run(a.text, origin))
