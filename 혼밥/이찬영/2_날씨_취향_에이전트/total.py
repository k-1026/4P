"""가중치 계산: 가게별 점수에 퍼센트를 곱해 더한다 (10%면 0.1)."""

FACTORS = ("날씨", "취향", "가격")


def rank(stores, weights):
    """stores: [{"name": 이름, "scores": {"날씨": 0~10, "취향": 0~10, "가격": 0~10}}]
    weights: {"날씨": %, "취향": %, "가격": %}. 합계 점수가 높은 순으로 돌려준다."""
    if any(not 0 <= weights[name] <= 100 for name in FACTORS) \
            or abs(sum(weights[name] for name in FACTORS) - 100) > 0.001:
        raise ValueError("퍼센트는 각각 0~100이고, 합이 100이어야 해요.")
    if any(not 0 <= store["scores"][name] <= 10 for store in stores for name in FACTORS):
        raise ValueError("점수는 0~10 사이여야 해요.")

    results = []
    for store in stores:
        value = sum(store["scores"][name] * weights[name] / 100 for name in FACTORS)
        results.append({**store, "total": round(value, 2)})
    results.sort(key=lambda item: -item["total"])
    for item in results:  # 점수가 같으면 같은 순위
        item["place"] = 1 + sum(other["total"] > item["total"] for other in results)
    return results
