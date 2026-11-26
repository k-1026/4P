// 거리 담당 (distance agent)
// 카카오 장소 검색 결과를 조율자가 읽는 JSON 리포트로 바꾼다.
// 계산만 하고 추천 판단은 하지 않는다. 브라우저(window.DistanceAgent)와 Node(require) 둘 다 쓸 수 있다.
(function (root) {
  const DEFAULTS = {
    radius_m: 1000,             // 검색 반경
    max_walk_min: null,         // 숫자를 주면 그보다 오래 걸리는 곳을 제외 (null: 반경 안이면 모두 포함)
    walk_speed_m_per_min: 70,   // 성인 평균 보행 속도
    detour_factor: 1.3,         // 직선거리 대비 실제 길 우회 비율
    low_accuracy_m: 300         // 내 위치 오차가 이보다 크면 확실도 낮춤
  };
  const KAKAO_MAX_RESULTS = 45; // 카카오 카테고리 검색 최대 결과 수

  function shortCategory(categoryName) {
    if (!categoryName) return null;
    const parts = categoryName.split('>').map(s => s.trim()).filter(Boolean);
    return parts.length > 1 ? parts.slice(1).join(' > ') : parts[0];
  }

  function estimate(distanceM, opts) {
    const routeM = Math.round(distanceM * opts.detour_factor);
    return { route_m: routeM, walk_min: Math.max(1, Math.ceil(routeM / opts.walk_speed_m_per_min)) };
  }

  // 거리 점수표 (보통 모드). 위에서부터 처음 맞는 구간의 점수를 준다.
  const SCORE_TABLES = {
    normal: [
      { max_min: 5, score: 10 },        // 약 5분 이내
      { max_min: 10, score: 5 },        // 6~10분
      { max_min: 15, score: 2 },        // 11~15분
      { max_min: Infinity, score: 0 }   // 16분 이상
    ]
  };

  function distanceScore(walkMin, table = 'normal') {
    if (walkMin == null) return null;
    return SCORE_TABLES[table].find(row => walkMin <= row.max_min).score;
  }

  // 거리 점수 (고정: 1분 = 1점): 후보들 중 가장 가까운 곳이 10점, 그보다 1분 더 걸릴 때마다 1점씩 깎는다.
  // 가장 가까운 곳보다 10분 이상 더 걸리면 0점. 범위를 나누지 않으므로 멀리 떨어진 가게 하나가
  // 다른 가게들의 점수를 바꾸지 않는다. 같은 도보 시간이면 같은 점수.
  // "시간이 없어요"(criteria.urgent)일 때는 1분마다 2점 (5분 이상 차이면 0점).
  // 점수는 가장 가까운 곳을 기준으로 하므로, 도보 시간이 바뀌면 다시 계산한다.
  const POINTS_PER_MIN = { normal: 1, urgent: 2 };

  function applyRelativeScores(report) {
    const timed = report.candidates.filter(c => c.walk_min != null);
    const minMin = timed.length ? Math.min(...timed.map(c => c.walk_min)) : null;
    const maxMin = timed.length ? Math.max(...timed.map(c => c.walk_min)) : null;
    const mode = report.criteria && report.criteria.urgent ? 'urgent' : 'normal';
    const ppm = POINTS_PER_MIN[mode];
    const step = timed.length ? 1 / ppm : null;
    const stepText = `1분마다 ${ppm}점`;

    for (const c of report.candidates) {
      c.score_table = 'relative_to_nearest';
      if (c.walk_min == null) {
        c.distance_score = null;
        c.score_reason = null;
        c.score_note = '도보 시간을 알 수 없어 점수 없음';
        continue;
      }
      const extra = c.walk_min - minMin;
      c.distance_score = Math.max(0, Math.round(10 - extra / step));
      c.score_reason = extra === 0
        ? '후보 중 가장 가까워서 10점'
        : `가장 가까운 곳보다 ${extra}분 더 걸려서 ${c.distance_score}점 (${stepText})`;
      c.score_note = c.source === 'straight_line_estimate' ? '추정값 기준' : null;
    }
    report.scoring = { method: 'fixed_per_minute', mode, points_per_min: ppm, nearest_min: minMin, farthest_min: maxMin };
    return report;
  }

  // 도보 시간은 항상 "약 N분"으로 말한다 (경로로 재도 실제와 차이가 날 수 있음)
  function walkLabel(min) {
    return min == null ? '알 수 없음' : `약 ${min}분`;
  }

  // places: 카카오 categorySearch 결과 배열 (distance, x, y, place_name ...)
  // origin: { lat, lng, accuracy_m (없으면 null), source: 'gps' | 'test' | 'address' }
  function buildReport(places, origin, options) {
    if (!origin || typeof origin.lat !== 'number' || typeof origin.lng !== 'number') {
      return { agent: 'distance', ok: false, error: 'NO_ORIGIN', message: '사용자 위치가 없어 거리를 계산하지 않았어요.' };
    }
    const opts = Object.assign({}, DEFAULTS, options || {});
    const lowOrigin = origin.accuracy_m != null && origin.accuracy_m > opts.low_accuracy_m;

    const candidates = (places || []).map(p => {
      const straight = p.distance === '' || p.distance == null ? NaN : Number(p.distance);
      const hasDistance = Number.isFinite(straight);
      const est = hasDistance ? estimate(straight, opts) : { route_m: null, walk_min: null };

      let confidence = hasDistance ? 'medium' : 'low';
      const notes = ['직선거리 기반 도보 추정'];
      if (!hasDistance) notes.push('카카오 응답에 거리가 없음');
      if (lowOrigin) {
        confidence = 'low';
        notes.push(`내 위치 오차 약 ${Math.round(origin.accuracy_m)}m`);
      }

      const tooFar = opts.max_walk_min != null && est.walk_min != null && est.walk_min > opts.max_walk_min;
      return ({
        id: String(p.id),
        name: p.place_name,
        category: shortCategory(p.category_name),
        lat: Number(p.y),
        lng: Number(p.x),
        straight_m: hasDistance ? straight : null,
        distance_m: est.route_m,
        walk_min: est.walk_min,
        walk_label: walkLabel(est.walk_min),
        source: 'straight_line_estimate',
        confidence,
        excluded: tooFar,
        exclude_reason: tooFar ? `도보 약 ${est.walk_min}분으로 기준 ${opts.max_walk_min}분 초과` : null,
        note: notes.join(', '),
        place_url: p.place_url || null
      });
    });

    candidates.sort((a, b) => (a.walk_min ?? Infinity) - (b.walk_min ?? Infinity));
    const kept = candidates.filter(c => !c.excluded).length;

    const truncated = opts.truncated != null ? opts.truncated : candidates.length >= KAKAO_MAX_RESULTS;
    const warnings = [];
    if (lowOrigin) warnings.push(`내 위치 오차가 약 ${Math.round(origin.accuracy_m)}m라 거리 값이 부정확할 수 있어요.`);
    if (truncated) warnings.push('검색 결과가 너무 많은 구역이 있어 일부 식당이 빠졌을 수 있어요.');
    if (candidates.length === 0) warnings.push(`반경 ${opts.radius_m}m 안에서 식당을 찾지 못했어요.`);

    return applyRelativeScores({
      agent: 'distance',
      version: 1,
      ok: true,
      generated_at: new Date().toISOString(),
      origin: { lat: origin.lat, lng: origin.lng, accuracy_m: origin.accuracy_m ?? null, source: origin.source || 'unknown' },
      criteria: {
        radius_m: opts.radius_m,
        max_walk_min: opts.max_walk_min,
        walk_speed_m_per_min: opts.walk_speed_m_per_min,
        detour_factor: opts.detour_factor,
        urgent: !!opts.urgent          // "시간이 없어요" → 거리 점수 1분마다 2점
      },
      summary: { found: candidates.length, kept, excluded: candidates.length - kept, truncated },
      warnings,
      candidates
    });
  }

  // 고른 후보만 실제 도보 경로로 다시 잰다. 걷는 길 서버는 최대한 쓰되, 오래 걸리면 포기하고 추정값으로 끝낸다.
  // fetchRoute(origin, {lat,lng}, timeoutMs) -> Promise<{ distance_m }>  (실패하면 throw)
  // ids를 주면 그 후보들, 없으면 제외되지 않은 가까운 순 topN곳.
  //   1) 먼저 1곳만 물어본다(probeTimeoutMs). 실패하면 서버가 멈춘 것으로 보고 나머지는 묻지 않는다.
  //   2) 성공하면 나머지를 concurrency곳씩 묻는다. 한 곳당 timeoutMs까지만 기다린다.
  //   3) 전체 시간이 budgetMs를 넘으면 남은 곳은 묻지 않는다.
  // 어떤 경우든 리포트(JSON)는 항상 돌려준다.
  const ROUTE_LIMITS = { probeTimeoutMs: 3000, timeoutMs: 3000, budgetMs: 8000, concurrency: 4 };

  async function refineWithRoutes(report, { fetchRoute, ids, topN = 5, routeName = 'osm_foot_route', limits = {} } = {}) {
    if (!report || !report.ok) return report;
    const L = Object.assign({}, ROUTE_LIMITS, limits);
    const opts = Object.assign({}, DEFAULTS, report.criteria);
    const targets = ids
      ? report.candidates.filter(c => ids.map(String).includes(c.id))
      : report.candidates.filter(c => !c.excluded).slice(0, topN);
    const started = Date.now();
    const deadline = started + L.budgetMs;
    let refined = 0, failed = 0, skipped = 0, stopped = null;

    const one = async (c, timeoutMs) => {
      try {
        const { distance_m } = await withTimeout(fetchRoute(report.origin, { lat: c.lat, lng: c.lng }, timeoutMs), timeoutMs);
        if (!Number.isFinite(distance_m)) throw new Error('BAD_ROUTE');
        c.distance_m = Math.round(distance_m);
        c.walk_min = Math.max(1, Math.ceil(distance_m / opts.walk_speed_m_per_min));
        c.walk_label = walkLabel(c.walk_min);
        c.source = routeName;
        c.confidence = report.origin.accuracy_m != null && report.origin.accuracy_m > opts.low_accuracy_m ? 'low' : 'high';
        c.note = c.confidence === 'high' ? '실제 걷는 길 기준 경로 (약)' : `걷는 길 기준이지만 내 위치 오차 약 ${Math.round(report.origin.accuracy_m)}m`;
        if (opts.max_walk_min != null) {
          c.excluded = c.walk_min > opts.max_walk_min;
          c.exclude_reason = c.excluded ? `도보 약 ${c.walk_min}분으로 기준 ${opts.max_walk_min}분 초과` : null;
        }
        refined++;
        return true;
      } catch (e) {
        c.note += ', 경로 확인 실패로 직선거리 추정값 유지';
        failed++;
        return false;
      }
    };
    const skip = list => { for (const c of list) { c.note += ', 시간 제한으로 경로 확인을 건너뛰고 직선거리 추정값 유지'; skipped++; } };

    if (targets.length) {
      // 1) 먼저 1곳만
      const ok = await one(targets[0], Math.min(L.probeTimeoutMs, L.budgetMs));
      const rest = targets.slice(1);
      if (!ok) {
        stopped = 'probe_failed';
        skip(rest);
      } else {
        // 2) 나머지를 concurrency곳씩, 3) 시간 예산 안에서만
        for (let i = 0; i < rest.length; i += L.concurrency) {
          const left = deadline - Date.now();
          if (left <= 0) { stopped = 'time_budget'; skip(rest.slice(i)); break; }
          await Promise.all(rest.slice(i, i + L.concurrency).map(c => one(c, Math.min(L.timeoutMs, left))));
        }
      }
    }

    applyRelativeScores(report);
    report.candidates.sort((a, b) => (a.walk_min ?? Infinity) - (b.walk_min ?? Infinity));
    report.summary.kept = report.candidates.filter(c => !c.excluded).length;
    report.summary.excluded = report.candidates.length - report.summary.kept;
    report.route_check = { method: routeName, requested: targets.length, refined, failed, skipped, stopped, took_ms: Date.now() - started, limits: L, ids: targets.map(c => c.id) };
    if (stopped === 'probe_failed') report.warnings.push(`걷는 길 서버가 응답하지 않아 ${targets.length}곳 모두 직선거리 추정값을 썼어요.`);
    else {
      if (failed) report.warnings.push(`후보 ${failed}곳은 걷는 길 확인에 실패해 직선거리 추정값을 썼어요.`);
      if (skipped) report.warnings.push(`시간이 오래 걸려 ${skipped}곳은 걷는 길 확인을 건너뛰고 직선거리 추정값을 썼어요.`);
    }
    return report;
  }

  // fetchRoute가 시간 제한을 안 지켜도 timeoutMs 뒤에는 실패로 끝낸다
  function withTimeout(promise, timeoutMs) {
    let timer;
    return Promise.race([
      promise,
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('TIMEOUT')), timeoutMs); })
    ]).finally(() => clearTimeout(timer));
  }

  // OpenStreetMap 도보 경로 (키 없음, 시험용 공개 서버라 후보 몇 곳에만 쓸 것)
  async function osmFootRoute(origin, dest, timeoutMs = 3000) {
    const url = `https://routing.openstreetmap.de/routed-foot/route/v1/foot/${origin.lng},${origin.lat};${dest.lng},${dest.lat}?overview=false`;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);     // 서버가 답을 안 주면 포기 → 추정값 유지
    let data;
    try {
      const res = await fetch(url, { signal: ctrl.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
    } finally {
      clearTimeout(timer);
    }
    if (data.code !== 'Ok' || !data.routes || !data.routes[0]) throw new Error(data.code || 'NO_ROUTE');
    return { distance_m: data.routes[0].distance };
  }

  // ⑤ 상의 단계: 1차 순위를 보고 거리 쪽 반론을 한 번만 낸다. 점수는 바꾸지 않는다(의견일 뿐).
  // 조건(모두 만족): 1순위가 약 7분 초과 / 1순위보다 4분 이상 가까운 통과 후보 / 그 후보와 점수 차 1점 이하
  // 기온이 5도 이하이면 날씨 이유를 붙인다.
  // 받침에 맞는 조사 (은/는, 이/가). 한글이 아니면 받침 없음으로 본다.
  function josa(word, withBatchim, withoutBatchim) {
    const code = word.charCodeAt(word.length - 1);
    const hangul = code >= 0xAC00 && code <= 0xD7A3;
    return word + (hangul && (code - 0xAC00) % 28 !== 0 ? withBatchim : withoutBatchim);
  }

  const OBJECTION_RULES = { far_min: 7, closer_by_min: 4, max_score_gap: 1.0, cold_c: 5 };

  function objection(report, { first_ranking, weather } = {}, rules = OBJECTION_RULES) {
    if (!report || !report.ok || !Array.isArray(first_ranking) || first_ranking.length < 2) return null;
    const byId = new Map(report.candidates.map(c => [c.id, c]));
    const ranked = first_ranking
      .map(r => ({ ...r, id: String(r.id), c: byId.get(String(r.id)) }))
      .filter(r => r.c && r.c.walk_min != null && !r.c.excluded);
    if (ranked.length < 2) return null;

    const top = ranked[0];
    if (top.c.walk_min <= rules.far_min) return null;

    const alt = ranked.slice(1)
      .filter(r => top.c.walk_min - r.c.walk_min >= rules.closer_by_min && top.score - r.score <= rules.max_score_gap)
      .sort((a, b) => b.score - a.score || a.c.walk_min - b.c.walk_min)[0];
    if (!alt) return null;

    const cold = weather && typeof weather.temp_c === 'number' && weather.temp_c <= rules.cold_c;
    const reasons = ['far_top_pick', ...(cold ? ['cold_weather'] : [])];
    const name = r => r.c.name || r.id;
    const message = cold
      ? `${weather.temp_c}도인데 ${josa(name(top), '은', '는')} ${top.c.walk_label}이에요. ${alt.c.walk_label}인 ${josa(name(alt), '이', '가')} 낫지 않나요?`
      : `${josa(name(top), '은', '는')} ${top.c.walk_label}이에요. ${alt.c.walk_label}인 ${josa(name(alt), '이', '가')} 더 가까운데 어떨까요?`;

    return {
      agent: 'distance',
      target: top.id,
      prefer: alt.id,
      target_name: name(top),     // 다른 담당(예: weather.rebut)에 넘길 가게 이름
      prefer_name: name(alt),
      reasons,
      facts: {
        target_walk: top.c.walk_label, prefer_walk: alt.c.walk_label,
        closer_by_min: top.c.walk_min - alt.c.walk_min,
        score_gap: Math.round((top.score - alt.score) * 100) / 100,
        temp_c: weather && typeof weather.temp_c === 'number' ? weather.temp_c : null,
        confidence: [top.c.confidence, alt.c.confidence]
      },
      changes_score: false,
      message
    };
  }

  // 다른 담당이 미는 가게(proposed)와 지금 1순위 가게(current)를 도보 시간으로 비교해 답한다.
  // 날씨 담당의 weather.rebut(report, 말한_에이전트, 상대가_미는_가게, ..., 지금_1순위_가게, ...)와 같은 모양.
  //   - 차이가 2분 미만(급할 때 1분 미만): 판단 안 함 ("거리 차이가 작아요")
  //   - 상대 가게가 더 멀면: 반대 / 더 가까우면: 동의
  //   - 두 가게 중 하나라도 거리 담당 후보에 없거나 도보 시간을 모르면: 판단 안 함
  // 가게는 id 또는 이름으로 찾는다. 점수는 바꾸지 않는다.
  const REBUT_RULES = { small_gap_min: 2, small_gap_min_urgent: 1, cold_c: 5 };

  function rebut(report, sender, proposed, current, { weather, urgent } = {}, rules = REBUT_RULES) {
    const find = key => report && report.ok
      ? report.candidates.find(c => c.id === String(key) || c.name === key) : null;
    const p = find(proposed), c = find(current);
    const label = (x, key) => (x && x.name) || String(key);
    const base = { agent: '거리', to: sender, proposed: label(p, proposed), current: label(c, current), changes_score: false };

    if (!p || !c || p.walk_min == null || c.walk_min == null) {
      const missing = [!p || p.walk_min == null ? label(p, proposed) : null, !c || c.walk_min == null ? label(c, current) : null].filter(Boolean);
      return { ...base, stance: '판단 안 함', facts: null,
        message: `${sender} 의견에 대해: ${missing.join(', ')}의 도보 시간을 몰라서 거리로는 비교할 수 없어요.` };
    }

    const isUrgent = urgent != null ? !!urgent : !!(report.criteria && report.criteria.urgent);
    const small = isUrgent ? rules.small_gap_min_urgent : rules.small_gap_min;
    const diff = p.walk_min - c.walk_min;                       // +면 상대 가게가 더 멂
    const cold = weather && typeof weather.temp_c === 'number' && weather.temp_c <= rules.cold_c;
    const estimated = [p, c].some(x => x.source === 'straight_line_estimate');
    const facts = { proposed_walk: p.walk_label, current_walk: c.walk_label, diff_min: diff,
      temp_c: weather && typeof weather.temp_c === 'number' ? weather.temp_c : null,
      confidence: [p.confidence, c.confidence], urgent: isUrgent };

    let stance, text;
    if (Math.abs(diff) < small) {
      stance = '판단 안 함';
      text = `${p.name}(${p.walk_label})와 ${c.name}(${c.walk_label})는 거리 차이가 작아요.`;
    } else if (diff > 0) {
      stance = '반대';
      text = `${josa(p.name, '은', '는')} ${p.walk_label}이라 ${c.name}보다 ${diff}분 더 걸려요.`
        + (cold ? ` ${weather.temp_c}도라 오래 걷기엔 추워요.` : '')
        + (isUrgent ? ' 시간이 없으시니 가까운 쪽이 나아요.' : '');
    } else {
      stance = '동의';
      text = `${josa(p.name, '이', '가')} ${c.name}보다 ${-diff}분 더 가까워요 (${p.walk_label}).`;
    }
    if (estimated) text += ' (직선거리 추정값 기준)';
    return { ...base, stance, facts, message: `${sender} 의견에 대해: ${text}` };
  }

  const api = { REBUT_RULES, rebut, ROUTE_LIMITS, applyRelativeScores, objection, josa, OBJECTION_RULES, buildReport, refineWithRoutes, osmFootRoute, walkLabel, distanceScore, SCORE_TABLES, DEFAULTS, KAKAO_MAX_RESULTS };
  root.DistanceAgent = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
