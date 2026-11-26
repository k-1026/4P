"""가상 상황 시뮬레이션. 가게·후기·다른 에이전트의 말은 모두 지어낸 것이다.

날씨 에이전트의 말과 점수만 weather.py가 실제로 만든다. 날씨 API는 부르지 않는다.
"""
import contextlib
import io
import os
import tempfile
from datetime import datetime

import weather

WEIGHTS = {"혼밥": 35, "거리": 20, "예산": 20, "취향": 15, "날씨": 10}

# 이름: (음식 종류, 거리 점수, 혼밥 점수, 예산 점수, 취향 점수, 탈락 이유)
STORES = {
    "A 국밥": ("따뜻한 국물", 5, 10, 5, 10, None),
    "B 라멘": ("따뜻한 국물", 10, 10, 5, 2, None),
    "C 찌개": ("따뜻한 국물", None, None, None, None, "2인분부터"),
    "D 돈까스": ("따뜻한 요리", 10, 5, 10, 5, None),
    "E 덮밥": ("따뜻한 요리", None, None, None, None, "1만 원 초과"),
}


def values(temp):
    return {"T1H": temp, "REH": 50.0, "WSD": 0.0}  # 바람이 없어 체감온도 = 기온


def weather_report(now_temp, yesterday_temp):
    """진짜 에이전트를 가짜 날씨로 실행한다. 임시 폴더를 써서 실제 결과 파일은 건드리지 않는다."""
    with tempfile.TemporaryDirectory() as folder:
        with open(os.path.join(folder, "api_key.txt"), "w", encoding="utf-8") as file:
            file.write("fake")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report = weather.main(datetime(2026, 11, 26, 12, 20), lambda key, when: values(now_temp),
                                  folder, lambda key, when: values(yesterday_temp))
    return report, output.getvalue().strip()


def main():
    report, said = weather_report(4.0, 10.0)
    print("[1] 날씨 에이전트\n" + said)
    print("\n[1] 취향기록(가짜): 국밥을 좋아하고, 어제 라면을 드셨어요.")

    print("\n[2] 조율자(가짜): 후보", ", ".join(STORES))

    print("\n[3] 탈락(가짜 거리·혼밥·예산)")
    for name, store in STORES.items():
        if store[5]:
            print(f"  {name}: {store[5]} -> 탈락")

    print("\n[4] 점수 (날씨 점수만 날씨 에이전트가 계산)")
    totals = {}
    for name, (food, distance, solo, budget, taste, out) in STORES.items():
        if out:
            continue
        scores = {"혼밥": solo, "거리": distance, "예산": budget, "취향": taste,
                  "날씨": weather.score(report, food)["score"]}
        totals[name] = round(sum(scores[key] * WEIGHTS[key] / 100 for key in WEIGHTS), 2)
        detail = ", ".join(f"{key} {scores[key]}" for key in WEIGHTS)
        print(f"  {name}: {detail} -> 합계 {totals[name]}")
    order = sorted(totals, key=totals.get, reverse=True)

    print("\n[5] 상의")
    print("거리(가짜): A는 8분이에요. 3분인 B가 낫지 않나요?")
    answer = weather.rebut(report, "거리", "B 라멘", STORES["B 라멘"][0], "A 국밥", STORES["A 국밥"][0])
    print(f"날씨 [{answer['stance']}]: {answer['message']}")

    print("\n[6] 최종 순위(가짜 조율자):", " > ".join(f"{name} {totals[name]}" for name in order))

    print("\n[추가 확인] 다른 상황에서의 날씨 에이전트")
    answer = weather.rebut(report, "예산", "D 돈까스", "따뜻한 요리", "A 국밥", "따뜻한 국물")
    print(f"추운 날, 돈까스를 밀 때 [{answer['stance']}]: {answer['message']}")
    hot, _ = weather_report(30.0, 27.0)
    answer = weather.rebut(hot, "취향기록", "A 국밥", "따뜻한 국물", "F 냉면", "차가운 요리")
    print(f"30도, 국밥을 밀 때 [{answer['stance']}]: {answer['message']}")
    mild, _ = weather_report(18.0, 18.0)
    answer = weather.rebut(mild, "거리", "B 라멘", "따뜻한 국물", "A 국밥", "따뜻한 국물")
    print(f"18도 [{answer['stance']}]: {answer['message']}")


if __name__ == "__main__":
    main()
