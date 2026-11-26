"""혼밥 MBTI 읽기 (앱 혼밥_홈화면_v2.html과 같은 글자).

  1번째 W 날씨파 / A 입맛파   -> 날씨 에이전트: 추우면 따뜻한 음식, 더우면 시원한 음식을 찾는지
  2번째 B 아늑파 / O 당당파      -> 혼밥 에이전트: 아늑파면 1인석 있는 곳을 더 추천
  3번째 N 탐험파 / R 단골파      -> 취향 에이전트: 탐험파면 안 가본 곳, 단골파면 가봤던 곳
  4번째 V 가성비파 / P 플렉스파  -> 가격 에이전트: 가성비파면 싼 곳, 플렉스파면 비싼 곳
"""
FRONT = "WBNV"  # 축마다 앞쪽 글자. 앱 퍼센트는 이 글자를 고른 비율(0~100)

AXES = ({"W": "날씨파", "A": "입맛파"}, {"B": "아늑파", "O": "당당파"},
        {"N": "탐험파", "R": "단골파"}, {"V": "가성비파", "P": "플렉스파"})


def parse(code):
    """'WBNV' -> ['날씨파', '아늑파', '탐험파', '가성비파']. 틀린 값이면 []"""
    code = str(code or "").strip().upper()
    if len(code) != 4 or any(letter not in axis for letter, axis in zip(code, AXES)):
        return []
    return [axis[letter] for letter, axis in zip(code, AXES)]


def has(code, name):
    return name in parse(code)


def label(code):
    names = parse(code)
    return f"{str(code).upper()}({'·'.join(names)})" if names else "MBTI 없음"


def parse_order(order):
    """네 축의 중요 순위 ['V', 'B', 'N', 'W'] (축의 앞쪽 글자, 1위부터). 모양이 틀리면 None"""
    if not isinstance(order, (list, tuple)) or not all(isinstance(x, str) for x in order):
        return None
    letters = [x.upper() for x in order]
    return letters if sorted(letters) == sorted(FRONT) else None


def parse_pct(code, pct):
    """앱이 보낸 퍼센트 [W, B, N, V] (0~100) -> ({"W": 0.75, ...}, 문제). 문제가 없으면 문제는 ""
    퍼센트가 50 이상이면 앞쪽 글자여야 한다 (앱도 50 이상이면 앞쪽 글자로 정한다)."""
    if pct is None:
        return None, "퍼센트 없음"
    if (not isinstance(pct, (list, tuple)) or len(pct) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 100 for v in pct)):
        return None, "퍼센트 모양이 틀림 (0~100 숫자 4개여야 해요)"
    names = parse(code)
    if names:
        for i, (letter, value) in enumerate(zip(str(code).upper(), pct)):
            if (value >= 50) != (letter == FRONT[i]):
                return None, f"{i + 1}번째 글자 {letter}와 퍼센트 {value:g}%가 안 맞음"
    return {letter: value / 100 for letter, value in zip(FRONT, pct)}, ""


def pct_label(pct):
    """{"W": 0.75, ...} -> '날씨파 75% · 아늑파 88% · ...' (센 쪽 이름과 그 퍼센트)"""
    parts = []
    for axis, letter in zip(AXES, FRONT):
        value = pct[letter]
        back = next(k for k in axis if k != letter)
        name, share = (axis[letter], value) if value >= 0.5 else (axis[back], 1 - value)
        parts.append(f"{name} {share * 100:.0f}%")
    return " · ".join(parts)
