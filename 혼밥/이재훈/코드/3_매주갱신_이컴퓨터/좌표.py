"""인허가 자료 좌표(EPSG:5174, 보정계수 없는 Bessel 중부원점 TM) → WGS84 위도·경도. 외부 도구 없이 계산한다.

proj4: +proj=tmerc +lat_0=38 +lon_0=127.0028902777778 +k=1 +x_0=200000 +y_0=500000 +ellps=bessel
       +towgs84=-115.80,474.99,674.11,1.16,-2.31,-1.63,6.43
맞는지는 DB에 있는 가게(상가정보의 WGS84 좌표)와 견줘 검사한다(좌표_검사).
"""
import math

A, RF = 6377397.155, 299.1528128          # Bessel 1841
LAT0, LON0, K0, FE, FN = 38.0, 127.0028902777778, 1.0, 200000.0, 500000.0
TOWGS = (-115.80, 474.99, 674.11, 1.16, -2.31, -1.63, 6.43)   # dx dy dz(m) rx ry rz(초) s(ppm), 위치 벡터 방식
WA, WRF = 6378137.0, 298.257223563        # WGS84


def _tm_inverse(x, y):
    """TM 평면(동쪽 x, 북쪽 y) → Bessel 위도·경도(도)."""
    f = 1 / RF
    e2 = 2 * f - f * f
    ep2 = e2 / (1 - e2)
    lat0 = math.radians(LAT0)

    def arc(phi):   # 적도에서 위도 phi까지 자오선 길이
        return A * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
                    - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
                    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
                    - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))

    m = arc(lat0) + (y - FN) / K0
    mu = m / (A * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    s, c, t = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = A / math.sqrt(1 - e2 * s * s)
    r1 = A * (1 - e2) / (1 - e2 * s * s) ** 1.5
    c1, t1 = ep2 * c * c, t * t
    d = (x - FE) / (n1 * K0)
    lat = phi1 - (n1 * t / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24
                                  + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = math.radians(LON0) + (d - (1 + 2 * t1 + c1) * d ** 3 / 6
                                + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5 / 120) / c
    return math.degrees(lat), math.degrees(lon)


def _to_xyz(lat, lon, a, rf):
    f = 1 / rf
    e2 = 2 * f - f * f
    p, l = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(p) ** 2)
    return (n * math.cos(p) * math.cos(l), n * math.cos(p) * math.sin(l), n * (1 - e2) * math.sin(p))


def _to_latlon(x, y, z, a, rf):
    f = 1 / rf
    e2 = 2 * f - f * f
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(8):
        n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        lat = math.atan2(z + e2 * n * math.sin(lat), p)
    return math.degrees(lat), math.degrees(lon)


def to_wgs84(x, y):
    """EPSG:5174 (x=동쪽, y=북쪽, 미터) → (위도, 경도). 값이 비거나 이상하면 None."""
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        return None
    if not (100000 < x < 600000 and 100000 < y < 800000):
        return None
    lat, lon = _tm_inverse(x, y)
    X, Y, Z = _to_xyz(lat, lon, A, RF)
    dx, dy, dz, rx, ry, rz, s = TOWGS
    rx, ry, rz = (math.radians(v / 3600) for v in (rx, ry, rz))
    k = 1 + s * 1e-6
    X2 = dx + k * (X - rz * Y + ry * Z)
    Y2 = dy + k * (rz * X + Y - rx * Z)
    Z2 = dz + k * (-ry * X + rx * Y + Z)
    return _to_latlon(X2, Y2, Z2, WA, WRF)


def meters(a, b):
    """두 (위도, 경도) 사이 거리(m)."""
    la, lb = map(math.radians, (a[0], b[0]))
    dl = math.radians(b[1] - a[1])
    h = math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))
