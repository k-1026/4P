// 혼밥 매주 갱신 (Supabase Edge Function, 컴퓨터 없이 돎). pg_cron이 매주 부른다(003_매주예약.sql).
// 1) 공공데이터 인허가 API에서 지난번 이후 바뀐 대구 중구 자료를 받고
// 2) 동성로 목록·DB와 비교해(logic.ts, 파이썬과 같은 규칙) 폐업한 DB 가게는 바로 빼고
// 3) 새 가게는 '확인 대기'(check_queue)에 쌓고, 볼 때가 된 '후기 다시 보기'도 쌓는다.
//    확인 대기는 이 컴퓨터를 켜면 Aside로 네이버를 보고 처리한다(따로 만듦).
// 비밀값(인허가 인증키, 예약용 열쇠)은 Supabase Vault에서 읽는다. 코드·로그에 찍지 않는다.
// ?dry=1 이면 아무것도 바꾸지 않고 결과 수만 돌려준다(시험용).
import postgres from "npm:postgres@3.4.5";
import { compare, dueRechecks, type Known, type Permit, type Recheck, type Shop, type Target } from "./logic.ts";

const API = "https://apis.data.go.kr/1741000/general_restaurants/info";
const REGION = "대구광역시 중구";
const PER = 100;

const today = () => new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);   // 한국 날짜
const minusDays = (d: string, n: number) => {
  const t = new Date(d + "T00:00:00Z");
  t.setUTCDate(t.getUTCDate() - n);
  return t.toISOString().slice(0, 10);
};

async function fetchPermits(key: string, since: string): Promise<Permit[]> {
  const rows: Permit[] = [];
  for (let page = 1; page <= 200; page++) {
    const q = new URLSearchParams({
      serviceKey: key, pageNo: String(page), numOfRows: String(PER), returnType: "json",
      "cond[ROAD_NM_ADDR::LIKE]": REGION, "cond[DAT_UPDT_PNT::GTE]": since.replaceAll("-", "") + "000000",
    });
    let doc: any = null;
    for (let tryNo = 0; tryNo < 3 && !doc; tryNo++) {
      try {
        const r = await fetch(`${API}?${q}`, { signal: AbortSignal.timeout(30000) });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        doc = await r.json();
      } catch (e) {
        if (tryNo === 2) throw new Error(`인허가 받기 실패(${page}쪽): ${(e as Error).message}`);
        await new Promise((ok) => setTimeout(ok, 3000));
      }
    }
    const res = doc.response ?? doc;
    const code = String(res.header?.resultCode ?? "00");
    if (!["00", "0", "INFO-000"].includes(code)) throw new Error(`인허가 API 오류: ${code} ${res.header?.resultMsg ?? ""}`);
    let it = res.body?.items ?? [];
    it = Array.isArray(it) ? it : (it.item ?? []);
    if (!Array.isArray(it)) it = [it];
    rows.push(...it);
    const total = Number(res.body?.totalCount ?? 0);
    if (!it.length || rows.length >= total) break;
    await new Promise((ok) => setTimeout(ok, 500));
  }
  return rows.filter((r) => (r.ROAD_NM_ADDR ?? "").includes("대구") && (r.ROAD_NM_ADDR ?? "").includes("중구"));
}

Deno.serve(async (req) => {
  const sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { max: 1, prepare: false });
  const dry = new URL(req.url).searchParams.get("dry") === "1";
  let runId: number | null = null;
  try {
    const [tok] = await sql`select decrypted_secret as v from vault.decrypted_secrets where name = 'honbap_cron_token'`;
    if (!tok?.v || req.headers.get("x-honbap-token") !== tok.v) return new Response("forbidden", { status: 403 });
    const [key] = await sql`select decrypted_secret as v from vault.decrypted_secrets where name = 'honbap_data_key'`;
    if (!key?.v) throw new Error("Vault에 honbap_data_key(인허가 인증키)가 없음");

    const day = today();
    const [last] = await sql`select value from honbap.settings where name = 'last_compare'`;
    const since = last?.value ? minusDays(last.value, 3) : minusDays(day, 7);   // 인허가 자료는 2일 전 기준이라 3일 겹쳐 봄
    if (!dry) [{ run_id: runId }] = await sql`insert into honbap.weekly_runs (since, status) values (${since}, '도는중') returning run_id`;

    const rows = await fetchPermits(key.v, since);
    const known = (await sql`select name, road_address, lat, lng, coalesce(dong, '') as dong from honbap.known_shops`) as unknown as Known[];
    const shops = (await sql`select restaurant_id, name, road_address from honbap.restaurants`) as unknown as Shop[];
    const { fresh, closed, seen } = compare(rows, known, shops, since);

    // 후기 다시 보기: 볼 때가 된 가게(새 가게 2·4·8주, 그 뒤와 기존 대기는 매달, 최대 30곳)
    const targets = (await sql`select target_key, kind, name, coalesce(road_address,'') as road_address, coalesce(map_url,'') as map_url,
                                      to_char(first_seen, 'YYYY-MM-DD') as first_seen from honbap.recheck_targets`) as unknown as Target[];
    const log = (await sql`select target_key, to_char(seen_on, 'YYYY-MM-DD') as seen_on, found, coalesce(memo,'') as memo
                             from honbap.recheck_log`) as unknown as Recheck[];
    const added = new Set(shops.map((s) => s.restaurant_id));
    const due = dueRechecks(targets, log, added, day);

    const out = { since, read: seen.read, road: seen.road, new_permits: seen.permit, fresh: fresh.length, closed: closed.length,
      recheck_due: due.total, recheck_queued: due.picked.length };
    if (dry) return Response.json({ dry: true, ...out, fresh_names: fresh.map((f) => f.name), closed_names: closed.map((c) => c.db_name) });

    await sql.begin(async (tx) => {
      for (const c of closed) {   // 폐업: 기록을 남기고 가게를 뺀다(근거·주요메뉴·1인석 등은 함께 지워짐)
        await tx`insert into honbap.closed_log (restaurant_id, name, permit_name, closed_on, mng_no, road_address)
                 values (${c.restaurant_id}, ${c.db_name}, ${c.permit_name}, ${c.closed_on || null}, ${c.mng_no}, ${c.road_address})`;
        await tx`delete from honbap.restaurants where restaurant_id = ${c.restaurant_id}`;
      }
      for (const f of fresh) {   // 새 가게: 같은 관리번호가 이미 대기·처리중·완료면 다시 쌓지 않음
        await tx`insert into honbap.check_queue (kind, target_key, name, road_address, due_on, info)
                 select '새가게', ${f.mng_no}, ${f.name}, ${f.road_address}, ${day}, ${tx.json(f as any)}
                 where not exists (select 1 from honbap.check_queue q where q.kind = '새가게' and q.target_key = ${f.mng_no} and q.status <> '멈춤')`;
      }
      for (const t of due.picked) {
        await tx`insert into honbap.check_queue (kind, target_key, name, road_address, map_url, due_on)
                 select '후기다시보기', ${t.target_key}, ${t.name}, ${t.road_address}, ${t.map_url}, ${t.due_on}
                 where not exists (select 1 from honbap.check_queue q where q.kind = '후기다시보기' and q.target_key = ${t.target_key}
                                     and q.status in ('대기', '처리중'))`;
      }
      await tx`insert into honbap.settings (name, value) values ('last_compare', ${day})
               on conflict (name) do update set value = excluded.value`;
      await tx`update honbap.weekly_runs set status = '끝', finished_at = now(), read_rows = ${seen.read}, new_count = ${fresh.length},
               closed_count = ${closed.length}, recheck_count = ${due.picked.length} where run_id = ${runId}`;
    });
    return Response.json({ ok: true, ...out });
  } catch (e) {
    const msg = (e as Error).message.slice(0, 500);
    if (runId !== null) await sql`update honbap.weekly_runs set status = '멈춤', finished_at = now(), message = ${msg} where run_id = ${runId}`.catch(() => {});
    return Response.json({ ok: false, message: msg }, { status: 500 });
  } finally {
    await sql.end({ timeout: 5 });
  }
});
