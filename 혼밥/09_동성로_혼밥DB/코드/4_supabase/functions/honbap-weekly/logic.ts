// 매주 갱신 계산 부분: 파이썬 갱신/인허가_비교.py·좌표.py·후기_다시보기.py와 같은 규칙(같은 결과가 나오게 시험함).
// Edge Function(index.ts)과 시험(logic.test.ts)이 함께 쓴다. 지울 수 있는 타입만 써서 Node로도 바로 돈다.

// ---------- 날짜·주소·이름 ----------
export function day(x: string | null | undefined): string {
  const d = (x ?? "").replace(/\D/g, "").slice(0, 8);
  return d.length === 8 ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6)}` : "";
}

export function addrKey(a: string | null | undefined): string | null {
  const s = (a ?? "").split(/[,(]/)[0];
  const m = s.match(/중구\s+(\S+(?:로|길))\s*(\d+(?:-\d+)?)/);
  return m ? `${m[1]}|${m[2]}` : null;
}

export function nameKey(n: string | null | undefined): string {
  return (n ?? "").replace(/[\s()（）\[\]·.,'"-]|주식회사|\(주\)/g, "").toLowerCase();
}

const BRANCH = new RegExp(
  "(?:(?:대구)?(?:동성로|중앙로|반월당|대구역|삼덕|종로|대봉|중구|동인|서문시장|경대병원|더현대|현대백화점|대백|롯데|동아|대구)(?:\\d+호)?점" +
    "|본점|직영점|\\d+호점)$",
);

export function baseName(raw: string | null | undefined): string {
  let parts = (raw ?? "").replace(/\(.*?\)|（.*?）|\[.*?\]/g, " ").split(/\s+/).filter(Boolean);
  const last = parts[parts.length - 1] ?? "";
  if (parts.length > 1 && /^[가-힣A-Za-z0-9]{1,8}점$/.test(last) && !last.endsWith("반점")) parts = parts.slice(0, -1);
  const k = nameKey(parts.join(" "));
  return k.replace(BRANCH, "") || k;
}

// 파이썬 difflib.SequenceMatcher(None, a, b).ratio()와 같은 값(짧은 글자에서는 autojunk가 꺼져 있어 같음)
export function ratio(a: string, b: string): number {
  const A = [...a], B = [...b];
  if (A.length + B.length === 0) return 1;
  const b2j = new Map<string, number[]>();
  B.forEach((ch, j) => { const l = b2j.get(ch); if (l) l.push(j); else b2j.set(ch, [j]); });
  const longest = (alo: number, ahi: number, blo: number, bhi: number): [number, number, number] => {
    let besti = alo, bestj = blo, bestsize = 0;
    let j2len = new Map<number, number>();
    for (let i = alo; i < ahi; i++) {
      const next = new Map<number, number>();
      for (const j of b2j.get(A[i]) ?? []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) ?? 0) + 1;
        next.set(j, k);
        if (k > bestsize) { besti = i - k + 1; bestj = j - k + 1; bestsize = k; }
      }
      j2len = next;
    }
    while (besti > alo && bestj > blo && A[besti - 1] === B[bestj - 1]) { besti--; bestj--; bestsize++; }
    while (besti + bestsize < ahi && bestj + bestsize < bhi && A[besti + bestsize] === B[bestj + bestsize]) bestsize++;
    return [besti, bestj, bestsize];
  };
  let matches = 0;
  const q: [number, number, number, number][] = [[0, A.length, 0, B.length]];
  while (q.length) {
    const [alo, ahi, blo, bhi] = q.pop()!;
    const [i, j, k] = longest(alo, ahi, blo, bhi);
    if (k) {
      matches += k;
      if (alo < i && blo < j) q.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) q.push([i + k, ahi, j + k, bhi]);
    }
  }
  return (2 * matches) / (A.length + B.length);
}

export function sameName(ra: string, rb: string): boolean {
  const a = nameKey(ra), b = nameKey(rb);
  if (!a || !b) return false;
  if (a === b) return true;
  const ba = baseName(ra), bb = baseName(rb);
  if (ba === bb) return true;
  const [short, long] = [...ba].length <= [...bb].length ? [ba, bb] : [bb, ba];
  if ([...short].length >= 3 && long.startsWith(short)) return true;
  return Math.min([...ba].length, [...bb].length) >= 4 && ratio(ba, bb) >= 0.9;
}

// ---------- 좌표: EPSG:5174(Bessel 중부원점 TM) → WGS84 ----------
const A_ = 6377397.155, RF = 299.1528128;
const LAT0 = 38.0, LON0 = 127.0028902777778, K0 = 1.0, FE = 200000.0, FN = 500000.0;
const TOWGS = [-115.80, 474.99, 674.11, 1.16, -2.31, -1.63, 6.43];
const WA = 6378137.0, WRF = 298.257223563;
const rad = (d: number) => (d * Math.PI) / 180, deg = (r: number) => (r * 180) / Math.PI;

function tmInverse(x: number, y: number): [number, number] {
  const f = 1 / RF, e2 = 2 * f - f * f, ep2 = e2 / (1 - e2), lat0 = rad(LAT0);
  const arc = (phi: number) => A_ * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
    - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * Math.sin(2 * phi)
    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * Math.sin(4 * phi)
    - (35 * e2 ** 3 / 3072) * Math.sin(6 * phi));
  const m = arc(lat0) + (y - FN) / K0;
  const mu = m / (A_ * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256));
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * Math.sin(4 * mu)
    + (151 * e1 ** 3 / 96) * Math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * Math.sin(8 * mu);
  const s = Math.sin(phi1), c = Math.cos(phi1), t = Math.tan(phi1);
  const n1 = A_ / Math.sqrt(1 - e2 * s * s), r1 = (A_ * (1 - e2)) / (1 - e2 * s * s) ** 1.5;
  const c1 = ep2 * c * c, t1 = t * t, d = (x - FE) / (n1 * K0);
  const lat = phi1 - ((n1 * t) / r1) * (d ** 2 / 2 - ((5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4) / 24
    + ((61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6) / 720);
  const lon = rad(LON0) + (d - ((1 + 2 * t1 + c1) * d ** 3) / 6 + ((5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5) / 120) / c;
  return [deg(lat), deg(lon)];
}

function toXyz(lat: number, lon: number, a: number, rf: number): [number, number, number] {
  const f = 1 / rf, e2 = 2 * f - f * f, p = rad(lat), l = rad(lon);
  const n = a / Math.sqrt(1 - e2 * Math.sin(p) ** 2);
  return [n * Math.cos(p) * Math.cos(l), n * Math.cos(p) * Math.sin(l), n * (1 - e2) * Math.sin(p)];
}

function toLatLon(x: number, y: number, z: number, a: number, rf: number): [number, number] {
  const f = 1 / rf, e2 = 2 * f - f * f, lon = Math.atan2(y, x), p = Math.hypot(x, y);
  let lat = Math.atan2(z, p * (1 - e2));
  for (let i = 0; i < 8; i++) {
    const n = a / Math.sqrt(1 - e2 * Math.sin(lat) ** 2);
    lat = Math.atan2(z + e2 * n * Math.sin(lat), p);
  }
  return [deg(lat), deg(lon)];
}

export function toWgs84(xs: unknown, ys: unknown): [number, number] | null {
  const x = Number(xs), y = Number(ys);
  if (xs === null || xs === undefined || xs === "" || ys === null || ys === undefined || ys === "") return null;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !(x > 100000 && x < 600000 && y > 100000 && y < 800000)) return null;
  const [lat, lon] = tmInverse(x, y);
  const [X, Y, Z] = toXyz(lat, lon, A_, RF);
  const [dx, dy, dz, rxs, rys, rzs, s] = TOWGS;
  const [rx, ry, rz] = [rxs, rys, rzs].map((v) => rad(v / 3600));
  const k = 1 + s * 1e-6;
  const X2 = dx + k * (X - rz * Y + ry * Z), Y2 = dy + k * (rz * X + Y - rx * Z), Z2 = dz + k * (-ry * X + rx * Y + Z);
  return toLatLon(X2, Y2, Z2, WA, WRF);
}

export function meters(a: [number, number], b: [number, number]): number {
  const la = rad(a[0]), lb = rad(b[0]), dl = rad(b[1] - a[1]);
  const h = Math.sin((lb - la) / 2) ** 2 + Math.cos(la) * Math.cos(lb) * Math.sin(dl / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

// ---------- 비교: 새 가게 후보와 폐업한 DB 가게 ----------
export const SKIP_KIND = /호프|통닭|치킨|정종|대포집|소주방|감성주점|라이브|룸살롱|단란|유흥|까페|카페|키즈|피자/;
const OPEN = /영업|정상/, CLOSED = /폐업|취소|말소/;
export const NEAR = 150;

export type Permit = {   // 인허가 API 한 줄(필요한 칸만)
  MNG_NO?: string; BPLC_NM?: string; LCPMT_YMD?: string; SALS_STTS_NM?: string; CLSBIZ_YMD?: string;
  ROAD_NM_ADDR?: string; BZSTAT_SE_NM?: string; CRD_INFO_X?: string | number; CRD_INFO_Y?: string | number;
};
export type Known = { name: string; road_address: string; lat: number | null; lng: number | null; dong: string };
export type Shop = { restaurant_id: string; name: string; road_address: string };
export type NewShop = {
  mng_no: string; name: string; permit_day: string; kind: string; road_address: string;
  lat: number | null; lng: number | null; dong: string; nearest_m: number | null; same_addr_others: string; memo: string;
};
export type Closed = { restaurant_id: string; db_name: string; permit_name: string; closed_on: string; road_address: string; mng_no: string };

export function compare(rows: Permit[], known: Known[], db: Shop[], since: string) {
  const roads = new Set<string>();
  const byAddr = new Map<string, Known[]>();
  for (const r of known) {
    const k = addrKey(r.road_address);
    if (k) roads.add(k.split("|")[0]);
    const kk = String(k);
    byAddr.set(kk, [...(byAddr.get(kk) ?? []), r]);
  }
  const pts = known.filter((r) => r.lat !== null && r.lng !== null).map((r) => [r.lat as number, r.lng as number, r.dong] as const);
  const dbAddr = new Map<string, Shop[]>();
  for (const s of db) {
    const kk = String(addrKey(s.road_address));
    dbAddr.set(kk, [...(dbAddr.get(kk) ?? []), s]);
  }
  const seen = { read: 0, road: 0, permit: 0, skipKind: 0, exists: 0, outside: 0 };
  const fresh: NewShop[] = [], closed: Closed[] = [];
  for (const r of rows) {
    seen.read++;
    const addr = r.ROAD_NM_ADDR ?? "";
    if (!addr.includes("대구") || !addr.includes("중구")) continue;
    const k = addrKey(addr);
    if (!k || !roads.has(k.split("|")[0])) continue;
    seen.road++;
    const state = r.SALS_STTS_NM ?? "", kind = r.BZSTAT_SE_NM ?? "", name = r.BPLC_NM ?? "";
    if (CLOSED.test(state)) {
      for (const s of dbAddr.get(k) ?? []) {
        if (sameName(s.name, name)) {
          closed.push({ restaurant_id: s.restaurant_id, db_name: s.name, permit_name: name, closed_on: day(r.CLSBIZ_YMD),
            road_address: addr, mng_no: r.MNG_NO ?? "" });
        }
      }
      continue;
    }
    if (!OPEN.test(state) || day(r.LCPMT_YMD) < since) continue;
    seen.permit++;
    if (SKIP_KIND.test(kind)) { seen.skipKind++; continue; }
    const old = [...(byAddr.get(k) ?? []).map((x) => x.name), ...(dbAddr.get(k) ?? []).map((x) => x.name)].filter((x) => sameName(x, name));
    if (old.length) { seen.exists++; continue; }
    const p = toWgs84(r.CRD_INFO_X, r.CRD_INFO_Y);
    let far: number | null = null, dong = "";
    if (p && pts.length) {
      let best = Infinity;
      for (const q of pts) {
        const m = meters(p, [q[0], q[1]]);
        if (m < best || (m === best && q[2] < dong)) { best = m; dong = q[2]; }
      }
      far = best;
      if (far > NEAR) { seen.outside++; continue; }
    }
    const others = (byAddr.get(k) ?? []).map((x) => x.name);
    const memo = others.length ? ["같은 주소의 다른 가게가 바뀌었을 수 있음"] : [];
    if (!p) memo.push("좌표 없음(DB에 넣으려면 좌표가 필요)");
    fresh.push({ mng_no: r.MNG_NO ?? "", name, permit_day: day(r.LCPMT_YMD), kind, road_address: addr,
      lat: p ? p[0] : null, lng: p ? p[1] : null, dong, nearest_m: far, same_addr_others: others.join("; "), memo: memo.join("; ") });
  }
  return { fresh, closed, seen };
}

// ---------- 후기 다시 보기: 볼 때가 된 가게 (후기_다시보기.py due()와 같은 규칙) ----------
export const NEW_STEPS = [14, 28, 56], MONTH = 30, MAX_RECHECK = 30;
export type Target = { target_key: string; kind: "새가게" | "기존"; name: string; road_address: string; map_url: string; first_seen: string };
export type Recheck = { target_key: string; seen_on: string; found: string; memo: string };

const addDays = (d: string, n: number) => {
  const t = new Date(d + "T00:00:00Z");
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
};

export function dueRechecks(targets: Target[], log: Recheck[], added: Set<string>, today: string, max = MAX_RECHECK) {
  const seen = new Map<string, Recheck[]>();
  for (const r of [...log].sort((a, b) => a.seen_on.localeCompare(b.seen_on))) seen.set(r.target_key, [...(seen.get(r.target_key) ?? []), r]);
  const stop = new Set([...seen].filter(([, rs]) => rs[rs.length - 1].found !== "예" || /폐업|휴업/.test(rs[rs.length - 1].memo)).map(([k]) => k));
  const out: { order: number; due: string; t: Target }[] = [];
  const keys = new Set<string>();
  for (const t of targets) {
    if (keys.has(t.target_key) || stop.has(t.target_key) || !day(t.first_seen)) continue;
    const rs = seen.get(t.target_key) ?? [];
    let due: string;
    if (t.kind === "새가게") {
      if (added.has(t.target_key)) continue;
      due = rs.length < NEW_STEPS.length ? addDays(t.first_seen, NEW_STEPS[rs.length]) : addDays(rs[rs.length - 1].seen_on, MONTH);
    } else {
      const last = [t.first_seen, ...rs.map((x) => x.seen_on)].sort().pop()!;
      due = addDays(last, MONTH);
    }
    if (due <= today) { out.push({ order: t.kind === "새가게" ? 0 : 1, due, t }); keys.add(t.target_key); }
  }
  out.sort((a, b) => a.order - b.order || a.due.localeCompare(b.due) || a.t.target_key.localeCompare(b.t.target_key));
  return { total: out.length, picked: out.slice(0, max).map((x) => ({ ...x.t, due_on: x.due })) };
}
