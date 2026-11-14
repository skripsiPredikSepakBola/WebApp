(() => {
  'use strict';

  const g = typeof window !== 'undefined' ? window : globalThis;
  const SHARD_COUNT = 16;

  const SUB_POS_TO_ROLE = {
    'Goalkeeper': 'GK',
    'Centre-Back': 'CB',
    'Left-Back': 'LB',
    'Right-Back': 'RB',
    'Defensive Midfield': 'CDM',
    'Central Midfield': 'CM',
    'Attacking Midfield': 'CAM',
    'Left Midfield': 'LM',
    'Right Midfield': 'RM',
    'Left Winger': 'LW',
    'Right Winger': 'RW',
    'Second Striker': 'CF',
    'Centre-Forward': 'ST',
  };
  const POS_FALLBACK = { GK: 'GK', DEF: 'CB', MID: 'CM', ATT: 'ST' };
  const ROLE_TO_GROUP = {
    GK: 'GK',
    CB: 'DEF', LB: 'DEF', RB: 'DEF',
    CDM: 'MID', CM: 'MID', CAM: 'MID', LM: 'MID', RM: 'MID',
    LW: 'ATT', RW: 'ATT', CF: 'ATT', ST: 'ATT',
  };
  const VALID_FORMATIONS = ['4-3-3', '4-2-3-1', '4-4-2', '3-5-2', '3-4-3', '5-3-2', '5-4-1', '4-1-4-1'];
  const FORMATION_ROLES = {
    '4-3-3':   ['GK', 'LB', 'CB', 'CB', 'RB', 'CM', 'CDM', 'CM', 'LW', 'ST', 'RW'],
    '4-2-3-1': ['GK', 'LB', 'CB', 'CB', 'RB', 'CDM', 'CDM', 'LW', 'CAM', 'RW', 'ST'],
    '4-4-2':   ['GK', 'LB', 'CB', 'CB', 'RB', 'LM', 'CM', 'CM', 'RM', 'ST', 'CF'],
    '3-5-2':   ['GK', 'CB', 'CB', 'CB', 'LM', 'CDM', 'CAM', 'CM', 'RM', 'ST', 'CF'],
    '3-4-3':   ['GK', 'CB', 'CB', 'CB', 'LM', 'CM', 'CM', 'RM', 'LW', 'ST', 'RW'],
    '5-3-2':   ['GK', 'LB', 'CB', 'CB', 'CB', 'RB', 'CM', 'CDM', 'CM', 'ST', 'CF'],
    '5-4-1':   ['GK', 'LB', 'CB', 'CB', 'CB', 'RB', 'LM', 'CM', 'CM', 'RM', 'ST'],
    '4-1-4-1': ['GK', 'LB', 'CB', 'CB', 'RB', 'CDM', 'LM', 'CM', 'CM', 'RM', 'ST'],
  };
  const OOP_PENALTY_MATRIX = {
    GK:  { GK: 0,  DEF: 40, MID: 45, ATT: 45 },
    DEF: { GK: 45, DEF: 0,  MID: 4,  ATT: 18 },
    MID: { GK: 45, DEF: 6,  MID: 0,  ATT: 4 },
    ATT: { GK: 45, DEF: 18, MID: 5,  ATT: 0 },
  };
  const GRANULAR_OOP_PENALTY = {
    'ST|CF': 1, 'CF|ST': 1,
    'LW|RW': 2, 'RW|LW': 2,
    'LW|LM': 2, 'LM|LW': 2, 'LW|RM': 2, 'RM|LW': 2,
    'RW|LM': 2, 'LM|RW': 2, 'RW|RM': 2, 'RM|RW': 2,
    'CAM|CM': 2, 'CM|CAM': 2,
    'CM|CDM': 2, 'CDM|CM': 2,
    'CM|LM': 2, 'LM|CM': 2, 'CM|RM': 2, 'RM|CM': 2,
    'LM|RM': 2, 'RM|LM': 2,
    'CAM|LW': 3, 'LW|CAM': 3, 'CAM|RW': 3, 'RW|CAM': 3,
    'CAM|CF': 3, 'CF|CAM': 3, 'CAM|ST': 4, 'ST|CAM': 4,
    'CAM|LM': 3, 'LM|CAM': 3, 'CAM|RM': 3, 'RM|CAM': 3,
    'LB|RB': 3, 'RB|LB': 3,
    'LB|LM': 3, 'LM|LB': 3, 'RB|RM': 3, 'RM|RB': 3,
    'LB|RM': 3, 'RM|LB': 3, 'RB|LM': 3, 'LM|RB': 3,
    'LW|ST': 4, 'RW|ST': 4, 'LW|CF': 4, 'RW|CF': 4,
    'LB|CB': 4, 'RB|CB': 4, 'CDM|CB': 4,
    'ST|LW': 5, 'ST|RW': 5, 'CF|LW': 5, 'CF|RW': 5,
    'CB|LB': 5, 'CB|RB': 5, 'CB|CDM': 5,
    'CAM|CDM': 5, 'CDM|CAM': 5,
    'CDM|LM': 5, 'LM|CDM': 5, 'CDM|RM': 5, 'RM|CDM': 5,
  };
  const GRANULAR_SCORER_WEIGHTS = {
    ST: 1.05, CF: 0.95, LW: 0.82, RW: 0.82,
    CAM: 0.58, LM: 0.45, RM: 0.45, CM: 0.35, CDM: 0.18,
    LB: 0.10, RB: 0.10, CB: 0.07, GK: 0.001,
    ATT: 1.0, MID: 0.40, DEF: 0.08,
  };
  const CTRY_ALIASES = {
    turkey: 'turkiye',
    'south korea': 'korea south',
    'ivory coast': 'cote d ivoire',
    usa: 'united states',
    'united states of america': 'united states',
    czechia: 'czech republic',
  };
  const EXPLORE_REGIONS = ['All', 'Top 5 European', 'Southeast Asia (ASEAN)', 'European Domestic & Cups', 'Americas & Global', 'International'];

  const nativeFetch = typeof g.fetch === 'function' ? g.fetch.bind(g) : null;
  const scriptSrc = typeof document !== 'undefined' && document.currentScript ? document.currentScript.src : '';
  const assetRoot = scriptSrc
    ? scriptSrc.replace(/static\/js\/gh-pages-engine\.js(?:\?.*)?$/, '')
    : (g.location ? g.location.href.replace(/[^/]*$/, '') : 'http://localhost/');
  const cache = new Map();
  let fullIndexPromise = null;

  function normalizeText(text) {
    if (!text) return '';
    return String(text)
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-zA-Z0-9\s]/g, ' ')
      .toLowerCase()
      .trim()
      .replace(/\s+/g, ' ');
  }

  function shardIdx(key) {
    const n = Number(key);
    if (Number.isInteger(n)) return Math.abs(n) % SHARD_COUNT;
    let s = 0;
    for (const ch of String(key)) s += ch.charCodeAt(0);
    return s % SHARD_COUNT;
  }

  async function loadData(relPath) {
    if (cache.has(relPath)) return cache.get(relPath);
    const promise = (async () => {
      if (typeof g.__STATIC_DATA_LOADER__ === 'function') {
        return g.__STATIC_DATA_LOADER__(relPath);
      }
      const url = new URL('data/' + relPath, assetRoot).href;
      const resp = await nativeFetch(url);
      if (!resp.ok) throw new Error(`Failed loading data/${relPath}: HTTP ${resp.status}`);
      return resp.json();
    })();
    cache.set(relPath, promise);
    try {
      const val = await promise;
      cache.set(relPath, val);
      return val;
    } catch (e) {
      cache.delete(relPath);
      throw e;
    }
  }

  async function getPlayersIndex() {
    if (fullIndexPromise) return fullIndexPromise;
    fullIndexPromise = (async () => {
      const list = await loadData('players_full.json');
      const byId = new Map();
      const byName = new Map();
      const blobs = [];
      for (const p of list) {
        if (p.id != null) byId.set(Number(p.id), p);
        for (const k of [p.name, p.full_name, p.tm_name]) {
          const n = normalizeText(k);
          if (n && !byName.has(n)) byName.set(n, p);
        }
        blobs.push([p, normalizeText(`${p.name || ''} ${p.full_name || ''} ${p.tm_name || ''}`)]);
      }
      return { list, byId, byName, blobs };
    })();
    return fullIndexPromise;
  }

  async function getBootIndex() {
    if (fullIndexPromise && !(fullIndexPromise instanceof Promise)) return fullIndexPromise;
    const list = await loadData('boot_players.json');
    const byId = new Map();
    const byName = new Map();
    const blobs = [];
    for (const p of list) {
      if (p.id != null) byId.set(Number(p.id), p);
      for (const k of [p.name, p.full_name, p.tm_name]) {
        const n = normalizeText(k);
        if (n && !byName.has(n)) byName.set(n, p);
      }
      blobs.push([p, normalizeText(`${p.name || ''} ${p.full_name || ''} ${p.tm_name || ''}`)]);
    }
    return { list, byId, byName, blobs };
  }

  function normalizeDate(reportDate) {
    if (!reportDate) return [null, null, null];
    const m = String(reportDate).trim().match(/^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?/);
    if (!m) return [null, null, null];
    const ym = `${m[1]}-${m[2].padStart(2, '0')}`;
    if (m[3]) {
      const d = `${ym}-${m[3].padStart(2, '0')}`;
      return [d, d, ym];
    }
    return [`${ym}-01`, `${ym}-31`, ym];
  }

  function applySnapshotRows(p, reportDate, snapsForPlayer, clubNormToId) {
    const out = { ...p };
    const [normDate, asofDate] = normalizeDate(reportDate);
    if (!normDate || normDate >= '2026-11-01' || !Array.isArray(snapsForPlayer) || !snapsForPlayer.length) {
      if (!out.report_date) out.report_date = '2026-11-01';
      if (out.form_delta == null) out.form_delta = 0.0;
      return out;
    }
    let best = null;
    for (const row of snapsForPlayer) {
      if (row[0] <= asofDate) best = row;
      else break;
    }
    if (!best) {
      out.report_date = out.report_date || '2026-11-01';
      out.form_delta = out.form_delta ?? 0.0;
      return out;
    }
    const [sd, cl, rt, fd, vl, ag, g9, tg] = best;
    if (rt != null) out.rating = rt;
    if (vl != null) out.val = vl;
    if (ag != null) out.age = ag;
    if (cl) {
      out.club = cl;
      const cid = clubNormToId?.[normalizeText(cl)];
      if (cid != null) out.club_id = cid;
    }
    if (g9 != null) out.goals_per_90 = g9;
    if (tg != null) out.total_goals = tg;
    out.report_date = sd;
    out.form_delta = fd ?? 0.0;
    return out;
  }

  async function resolvePlayer(item, idxObj, reportDate = null, clubNormToId = null) {
    if (item == null) return null;
    let slotPos = null;
    let pFound = null;
    let itemStr = '';

    if (typeof item === 'object') {
      slotPos = item.slot_pos ?? null;
      if (item.id != null && idxObj.byId.has(Number(item.id))) {
        pFound = idxObj.byId.get(Number(item.id));
      } else {
        itemStr = item.name || '';
      }
    } else if (typeof item === 'number' && idxObj.byId.has(item)) {
      pFound = idxObj.byId.get(item);
    } else {
      itemStr = String(item);
    }

    if (!pFound) {
      const clean = normalizeText(itemStr);
      if (clean) {
        pFound = idxObj.byName.get(clean) || null;
        if (!pFound) {
          for (const [p, blob] of idxObj.blobs) {
            if (blob.includes(clean)) {
              pFound = p;
              break;
            }
          }
        }
      }
    }
    if (!pFound) return null;

    let res = { ...pFound, club_id: pFound.club_id ?? null, slot_pos: slotPos };
    if (reportDate) {
      const [normDate] = normalizeDate(reportDate);
      if (normDate && normDate < '2026-11-01' && res.id != null) {
        try {
          const shard = await loadData(`player_details_shard_${shardIdx(res.id)}.json`);
          const snaps = shard.snapshots?.[String(res.id)] || [];
          res = applySnapshotRows(res, reportDate, snaps, clubNormToId);
        } catch (_) {}
      } else {
        res = applySnapshotRows(res, reportDate, null, clubNormToId);
      }
    }
    return res;
  }

  function getNativeRole(p) {
    const group = p.pos || ROLE_TO_GROUP[p.role] || 'MID';
    return String(p.role || SUB_POS_TO_ROLE[p.sub_pos || ''] || POS_FALLBACK[group] || 'CM').toUpperCase();
  }

  function calculatePlayerEffectiveRating(p, slotPos) {
    const nativeGroup = p.pos || ROLE_TO_GROUP[p.role] || 'MID';
    const baseRating = Number(p.rating ?? 75);
    if (!slotPos || slotPos === 'SUB') return [baseRating, 0];
    const sp = String(slotPos).trim().toUpperCase();
    let penalty = 0;
    if (sp === 'GK' || sp === 'DEF' || sp === 'MID' || sp === 'ATT') {
      penalty = OOP_PENALTY_MATRIX[nativeGroup]?.[sp] ?? 0;
    } else {
      const natRole = getNativeRole(p);
      if (natRole === sp) penalty = 0;
      else if (`${natRole}|${sp}` in GRANULAR_OOP_PENALTY) penalty = GRANULAR_OOP_PENALTY[`${natRole}|${sp}`];
      else penalty = OOP_PENALTY_MATRIX[nativeGroup]?.[ROLE_TO_GROUP[sp] || sp] ?? 0;
    }
    return [Math.max(35.0, baseRating - penalty), penalty];
  }

  function cohesionProxy(players) {
    const counts = new Map();
    let anyClub = false;
    for (const p of players) {
      if (p.club) {
        anyClub = true;
        counts.set(p.club, (counts.get(p.club) || 0) + 1);
      }
    }
    if (!anyClub) return 0.0;
    const n = players.length || 1;
    let sum = 0;
    for (const c of counts.values()) sum += (c / n) ** 2;
    return sum;
  }

  function mean(arr, fb = 0) {
    return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : fb;
  }

  async function aggregateTeamAdvanced(startersInput, subsInput, teamName, idxObj, reportDate, clubNormToId) {
    const starters = [];
    for (const s of startersInput || []) {
      const p = await resolvePlayer(s, idxObj, reportDate, clubNormToId);
      if (p) starters.push(p);
    }
    const subs = [];
    for (const s of subsInput || []) {
      const p = await resolvePlayer(s, idxObj, reportDate, clubNormToId);
      if (p) subs.push(p);
    }
    if (!starters.length) throw new Error(`No valid starting players resolved for ${teamName}`);

    let hasOutfieldInGk = false;
    const effRatings = [];
    const heights = [];
    const primes = [];
    let valSum = 0;
    let ageSum = 0;

    for (const p of starters) {
      const h = Number.isFinite(Number(p.height)) && p.height != null ? Number(p.height) : 182.0;
      const age = Number.isFinite(Number(p.age)) && p.age != null ? Number(p.age) : 26.0;
      const val = Number.isFinite(Number(p.val)) && p.val != null ? Number(p.val) : 0.0;
      p.height = h;
      p.age = age;
      p.val = val;
      p.rating = Number.isFinite(Number(p.rating)) && p.rating != null ? Number(p.rating) : 75.0;
      p.goals_per_90 = Number.isFinite(Number(p.goals_per_90)) && p.goals_per_90 != null ? Number(p.goals_per_90) : 0.0;

      const sp = String(p.slot_pos || p.role || p.pos || 'MID').trim().toUpperCase();
      const sGrp = ROLE_TO_GROUP[sp] || sp;
      const [effR, pen] = calculatePlayerEffectiveRating(p, sp);
      p._eff = effR;
      p._pen = pen;
      p._slot_group = sGrp;

      if ((sp === 'GK' || sGrp === 'GK') && p.pos !== 'GK' && p.role !== 'GK') {
        hasOutfieldInGk = true;
      }

      effRatings.push(effR);
      heights.push(h);
      valSum += val;
      ageSum += age;
      const prime = Math.min(1.0, Math.max(0.6, 1.0 - 0.018 * (Math.abs(age - 27.0) ** 1.25)));
      primes.push(prime);
    }

    const overallMean = mean(effRatings);
    const heightMean = mean(heights);

    function lineMetric(label, field, fb) {
      let arr = starters.filter(p => p._slot_group === label).map(p => field === 'eff' ? p._eff : p[field]);
      if (!arr.length) arr = starters.filter(p => p.pos === label).map(p => field === 'eff' ? p._eff : p[field]);
      return arr.length ? mean(arr) : fb;
    }

    const subRatings = subs.map(s => Number.isFinite(Number(s.rating)) && s.rating != null ? Number(s.rating) : 75.0);
    const subMean = subRatings.length ? mean(subRatings) : overallMean - 5.0;
    const subMax = subRatings.length ? Math.max(...subRatings) : overallMean;

    const stats = {
      starter_count: starters.length,
      starter_overall_mean: overallMean,
      starter_overall_max: Math.max(...effRatings),
      starter_overall_min: Math.min(...effRatings),
      starter_market_val_sum: valSum,
      starter_height_mean: heightMean,
      starter_age_mean: ageSum / starters.length,
      has_outfield_in_gk: hasOutfieldInGk,
      starter_prime_mean: mean(primes),
      overall_mean_GK: lineMetric('GK', 'eff', overallMean),
      overall_mean_DEF: lineMetric('DEF', 'eff', overallMean),
      overall_mean_MID: lineMetric('MID', 'eff', overallMean),
      overall_mean_ATT: lineMetric('ATT', 'eff', overallMean),
      height_mean_DEF: lineMetric('DEF', 'height', heightMean),
      height_mean_ATT: lineMetric('ATT', 'height', heightMean),
      sub_count: subs.length,
      sub_overall_mean: subMean,
      sub_overall_max: subMax,
      depth_gap: overallMean - subMean,
    };
    return [stats, starters, subs];
  }

  function evalHgbtRow(exp, x) {
    const raw = exp.base.slice();
    const k = raw.length;
    for (const iterTrees of exp.trees) {
      for (let c = 0; c < k; c++) {
        const t = iterTrees[c];
        let idx = 0;
        while (!t.lf[idx]) {
          const val = x[t.f[idx]];
          if (val == null || Number.isNaN(val)) {
            idx = t.mg && t.mg[idx] ? t.l[idx] : t.r[idx];
          } else {
            idx = val <= t.th[idx] ? t.l[idx] : t.r[idx];
          }
        }
        raw[c] += t.v[idx];
      }
    }
    return raw;
  }

  function softmax(logits) {
    const mx = Math.max(...logits);
    const ex = logits.map(v => Math.exp(v - mx));
    const sm = ex.reduce((a, b) => a + b, 0) || 1;
    return ex.map(v => v / sm);
  }

  function factorial(n) {
    let r = 1;
    for (let i = 2; i <= n; i++) r *= i;
    return r;
  }

  function computePlayerScorers(players, teamXg) {
    const weights = players.map(p => {
      const pRole = getNativeRole(p);
      const slotP = String(p.slot_pos || pRole || p.pos || 'MID').trim().toUpperCase();
      const posMult = slotP === 'GK' ? 0.001 : (GRANULAR_SCORER_WEIGHTS[slotP] || GRANULAR_SCORER_WEIGHTS[pRole] || GRANULAR_SCORER_WEIGHTS[p.pos || 'MID'] || 0.4);
      const g90 = p.goals_per_90 == null || Number.isNaN(Number(p.goals_per_90)) ? 0.2 : Number(p.goals_per_90);
      const [effR] = calculatePlayerEffectiveRating(p, slotP);
      return posMult * (0.3 * (effR / 80.0) + 0.7 * Math.max(0.05, g90));
    });
    const totalW = weights.reduce((a, b) => a + b, 0) || 1.0;
    return players.map((p, i) => {
      const share = weights[i] / totalW;
      const indivXg = teamXg * share;
      const anytime = 1.0 - Math.exp(-indivXg);
      const pRole = getNativeRole(p);
      const slotP = p.slot_pos || pRole || p.pos || 'MID';
      const [effR, pen] = calculatePlayerEffectiveRating(p, slotP);
      const g90Val = p.goals_per_90 == null || Number.isNaN(Number(p.goals_per_90)) ? 0.0 : Number(p.goals_per_90);
      return {
        id: p.id,
        name: p.name,
        pos: p.pos || 'MID',
        role: pRole,
        pos_role: pRole,
        slot_pos: slotP,
        rating: p.rating ?? 75,
        effective_rating: Math.round(effR * 10) / 10,
        oop_penalty: pen,
        height: p.height || 182,
        age: p.age || 26,
        club: p.club || '',
        club_id: p.club_id ?? null,
        is_former: Boolean(p.is_former),
        last_season: p.last_season ?? null,
        former_club: p.former_club || '',
        image_url: p.image_url || '',
        career_goals: p.total_goals || 0,
        goals_per_90: g90Val,
        anytime_prob: Math.round(anytime * 1000) / 10,
        expected_goals: Math.round(indivXg * 100) / 100,
      };
    }).sort((a, b) => b.anytime_prob - a.anytime_prob);
  }

  function starterRows(players) {
    return players.map(p => {
      const [eff, pen] = calculatePlayerEffectiveRating(p, p.slot_pos);
      const pRole = getNativeRole(p);
      return {
        id: p.id ?? null, name: p.name ?? null, club: p.club ?? null, club_id: p.club_id ?? null,
        pos: p.pos ?? null, sub_pos: p.sub_pos ?? null, slot_pos: p.slot_pos ?? null,
        rating: p.rating ?? null, age: p.age ?? null, height: p.height ?? null, val: p.val ?? null,
        goals_per_90: p.goals_per_90 ?? null, total_goals: p.total_goals ?? null,
        report_date: p.report_date ?? null, last_season: p.last_season ?? null,
        image_url: p.image_url || '', role: 'Starter', pos_role: pRole,
        is_former: Boolean(p.is_former), former_club: p.former_club || '',
        effective_rating: eff, oop_penalty: pen,
      };
    });
  }

  function subRows(players) {
    return players.map(p => {
      const pRole = getNativeRole(p);
      return {
        id: p.id ?? null, name: p.name ?? null, club: p.club ?? null, club_id: p.club_id ?? null,
        pos: p.pos ?? null, sub_pos: p.sub_pos ?? null, slot_pos: 'SUB',
        rating: p.rating ?? null, age: p.age ?? null, height: p.height ?? null, val: p.val ?? null,
        goals_per_90: p.goals_per_90 ?? null, total_goals: p.total_goals ?? null,
        report_date: p.report_date ?? null, last_season: p.last_season ?? null,
        image_url: p.image_url || '', role: 'Sub', pos_role: pRole,
        is_former: Boolean(p.is_former), former_club: p.former_club || '',
        effective_rating: p.rating ?? null, oop_penalty: 0,
      };
    });
  }

  function normalizeFormation(f) {
    if (!f) return '4-3-3';
    const s = String(f).trim();
    if (VALID_FORMATIONS.includes(s)) return s;
    const nums = s.match(/\d+/g) || [];
    const cand = nums.join('-');
    if (VALID_FORMATIONS.includes(cand)) return cand;
    const remap = {
      '4-3-2-1': '4-2-3-1', '4-1-2-1-2': '4-4-2', '4-3-1-2': '4-4-2',
      '4-2-2-2': '4-4-2', '4-4-1-1': '4-4-2', '4-5-1': '4-1-4-1',
      '3-4-2-1': '3-4-3', '3-4-1-2': '3-5-2', '3-1-4-2': '3-5-2',
      '5-2-3': '3-4-3', '5-2-2-1': '5-4-1', '5-3-1-1': '5-3-2',
    };
    return remap[cand] || '4-3-3';
  }

  function alignToFormation(resolved, formation) {
    const roles = FORMATION_ROLES[normalizeFormation(formation)] || FORMATION_ROLES['4-3-3'];
    const pool = resolved.filter(Boolean).map(p => ({ ...p }));
    if (!pool.length) return Array(11).fill(null);
    const slots = Array(11).fill(null);
    const used = new Set();

    roles.forEach((slotRole, idx) => {
      for (let j = 0; j < pool.length; j++) {
        if (!used.has(j) && getNativeRole(pool[j]) === slotRole) {
          slots[idx] = { ...pool[j], slot_pos: slotRole };
          used.add(j);
          break;
        }
      }
    });
    roles.forEach((slotRole, idx) => {
      if (slots[idx]) return;
      const tGrp = ROLE_TO_GROUP[slotRole] || slotRole;
      for (let j = 0; j < pool.length; j++) {
        const pGrp = pool[j].pos || ROLE_TO_GROUP[pool[j].role] || 'MID';
        if (!used.has(j) && pGrp === tGrp) {
          slots[idx] = { ...pool[j], slot_pos: slotRole };
          used.add(j);
          break;
        }
      }
    });
    const rem = pool.filter((_, j) => !used.has(j));
    roles.forEach((slotRole, idx) => {
      if (!slots[idx] && rem.length) slots[idx] = { ...rem.shift(), slot_pos: slotRole };
    });
    return slots;
  }

  function getTeamCrest(teamName, presetMeta, clubsLight, countries) {
    if (!teamName) return '';
    const nrm = normalizeText(teamName);
    for (const k of [teamName, `${teamName} (National Team)`, nrm, normalizeText(`${teamName} (National Team)`)]) {
      if (presetMeta?.[k]?.crest_url) return presetMeta[k].crest_url;
    }
    const cid = clubsLight?.club_norm_to_id?.[nrm];
    if (cid) return `https://tmssl.akamaized.net/images/wappen/head/${cid}.png`;
    const cobj = findCountryObj(teamName, countries);
    return cobj?.team_image_url || '';
  }

  function findCountryObj(name, countries) {
    if (!name || !Array.isArray(countries)) return null;
    let clean = normalizeText(String(name).replace(/\s*\(national team\)\s*$/i, ''));
    clean = CTRY_ALIASES[clean] || clean;
    for (const c of countries) {
      if (normalizeText(c.name) === clean || normalizeText(c.nt_name) === clean) return c;
    }
    for (const c of countries) {
      if (clean && normalizeText(c.name).includes(clean)) return c;
    }
    return null;
  }

  // ---- Pure-JS stored ZIP (.xlsx) builder ----
  const CRC_TABLE = (() => {
    const tbl = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      tbl[n] = c >>> 0;
    }
    return tbl;
  })();

  function crc32(bytes) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  function xmlEsc(v) {
    return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function sheetXml(rows) {
    const rXml = rows.map((row, rIdx) => {
      const cells = row.map((val, cIdx) => {
        const col = String.fromCharCode(65 + (cIdx % 26));
        const ref = `${cIdx >= 26 ? String.fromCharCode(64 + Math.floor(cIdx / 26)) : ''}${col}${rIdx + 1}`;
        if (typeof val === 'number' && Number.isFinite(val)) {
          return `<c r="${ref}"><v>${val}</v></c>`;
        }
        return `<c r="${ref}" t="inlineStr"><is><t>${xmlEsc(val)}</t></is></c>`;
      }).join('');
      return `<row r="${rIdx + 1}">${cells}</row>`;
    }).join('');
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${rXml}</sheetData></worksheet>`;
  }

  function buildZip(entries) {
    const enc = new TextEncoder();
    const parts = [];
    const central = [];
    let offset = 0;

    for (const [name, content] of entries) {
      const nb = enc.encode(name);
      const db = enc.encode(content);
      const crc = crc32(db);

      const lh = new ArrayBuffer(30);
      const dv = new DataView(lh);
      dv.setUint32(0, 0x04034B50, true);
      dv.setUint16(4, 20, true);
      dv.setUint16(6, 0x0800, true);
      dv.setUint16(8, 0, true);
      dv.setUint16(10, 0, true);
      dv.setUint16(12, 0x5421, true);
      dv.setUint32(14, crc, true);
      dv.setUint32(18, db.length, true);
      dv.setUint32(22, db.length, true);
      dv.setUint16(26, nb.length, true);
      dv.setUint16(28, 0, true);

      const ch = new ArrayBuffer(46);
      const cdv = new DataView(ch);
      cdv.setUint32(0, 0x02014B50, true);
      cdv.setUint16(4, 20, true);
      cdv.setUint16(6, 20, true);
      cdv.setUint16(8, 0x0800, true);
      cdv.setUint16(10, 0, true);
      cdv.setUint16(12, 0, true);
      cdv.setUint16(14, 0x5421, true);
      cdv.setUint32(16, crc, true);
      cdv.setUint32(20, db.length, true);
      cdv.setUint32(24, db.length, true);
      cdv.setUint16(28, nb.length, true);
      cdv.setUint16(30, 0, true);
      cdv.setUint16(32, 0, true);
      cdv.setUint16(34, 0, true);
      cdv.setUint16(36, 0, true);
      cdv.setUint32(38, 0, true);
      cdv.setUint32(42, offset, true);

      parts.push(new Uint8Array(lh), nb, db);
      central.push(new Uint8Array(ch), nb);
      offset += 30 + nb.length + db.length;
    }

    const cSize = central.reduce((a, b) => a + b.length, 0);
    const eocd = new ArrayBuffer(22);
    const edv = new DataView(eocd);
    edv.setUint32(0, 0x06054B50, true);
    edv.setUint16(8, entries.length, true);
    edv.setUint16(10, entries.length, true);
    edv.setUint32(12, cSize, true);
    edv.setUint32(16, offset, true);

    const out = new Uint8Array(offset + cSize + 22);
    let pos = 0;
    for (const p of [...parts, ...central, new Uint8Array(eocd)]) {
      out.set(p, pos);
      pos += p.length;
    }
    return out;
  }

  function buildXlsxBytes(d) {
    const h = String(d.home_name || 'Home').replaceAll(' (National Team)', '');
    const a = String(d.away_name || 'Away').replaceAll(' (National Team)', '');
    const pr = d.probabilities || {};
    const sp = d.score_prediction || {};
    const sm = d.summary || {};

    const sumRows = [
      [`${h} vs ${a}`],
      [sm.headline || '', '', '', `Confidence: ${sm.confidence || '-'}`],
      [],
      ['Outcome', 'Win Probability (%)', 'Projected xG'],
      [`${h} Win`, pr.home ?? 0, sp.projected_home_xg ?? 0],
      ['Draw', pr.draw ?? 0, ''],
      [`${a} Win`, pr.away ?? 0, sp.projected_away_xg ?? 0],
      [],
      ['Most Likely Score', sp.most_likely_score || '-', 'Over 2.5 Goals (%)', sp.over_2_5_prob ?? 0],
      [],
      ['Category', h, a, 'Edge'],
      ...(d.tactical_metrics || []).map(m => [m.label, m.home, m.away, Math.round((m.home - m.away) * 10) / 10]),
    ];

    const rawRows = [
      ['Team', 'Role', 'Slot', 'Player', 'Pos', 'Nat Role', 'Base Rating', 'Effective Rating', 'OOP Penalty', 'Goals/90'],
      ...(d.lineups?.home || []).map(p => [h, p.role, p.slot_pos, p.name, p.pos, p.pos_role, p.rating, p.effective_rating, p.oop_penalty, p.goals_per_90 ?? 0]),
      ...(d.lineups?.away || []).map(p => [a, p.role, p.slot_pos, p.name, p.pos, p.pos_role, p.rating, p.effective_rating, p.oop_penalty, p.goals_per_90 ?? 0]),
    ];

    return buildZip([
      ['[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'],
      ['_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'],
      ['xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Summary" sheetId="1" r:id="rId1"/><sheet name="Raw Data" sheetId="2" r:id="rId2"/></sheets></workbook>'],
      ['xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>'],
      ['xl/worksheets/sheet1.xml', sheetXml(sumRows)],
      ['xl/worksheets/sheet2.xml', sheetXml(rawRows)],
    ]);
  }

  async function enrichPlayerSummary(p, shardData = null) {
    if (!p) return p;
    const out = { ...p };
    if (shardData && out.id != null) {
      const det = shardData.details?.[String(out.id)];
      if (det) {
        if (!out.image_url && det[5]) out.image_url = det[5];
        if (out.highest_val == null && det[6] != null) out.highest_val = det[6];
      }
    }
    if (!out.role) out.role = SUB_POS_TO_ROLE[out.sub_pos || ''] || POS_FALLBACK[out.pos || 'MID'] || 'CM';
    out.pos_role = out.pos_role || out.role;
    out.is_former = Boolean(out.is_former);
    out.former_club = out.former_club || '';
    return out;
  }

  async function handlePredict(body) {
    const [models, idxObj, presetMeta, clubsLight, countries] = await Promise.all([
      loadData('models.json'),
      getPlayersIndex(),
      loadData('preset_meta.json').catch(() => ({})),
      loadData('clubs_light.json').catch(() => ({})),
      loadData('countries.json').catch(() => []),
    ]);

    const teamAName = body.home_name || 'Squad 1';
    const teamBName = body.away_name || 'Squad 2';
    const reportDate = body.report_date || null;
    const [normDate] = normalizeDate(reportDate);
    const effReportDate = normDate || '2026-11-01';
    const clubNormToId = clubsLight?.club_norm_to_id || {};

    const formPtsA = Number(body.home_form_pts ?? 1.8);
    const formPtsB = Number(body.away_form_pts ?? 1.8);
    const formGdA = Number(body.home_form_gd ?? 0.5);
    const formGdB = Number(body.away_form_gd ?? 0.5);

    const [statsA, stA, sbA] = await aggregateTeamAdvanced(body.home_starters || [], body.home_subs || [], teamAName, idxObj, reportDate, clubNormToId);
    const [statsB, stB, sbB] = await aggregateTeamAdvanced(body.away_starters || [], body.away_subs || [], teamBName, idxObj, reportDate, clubNormToId);

    const fAb = {
      diff_overall_mean: statsA.starter_overall_mean - statsB.starter_overall_mean,
      diff_overall_max: statsA.starter_overall_max - statsB.starter_overall_max,
      diff_overall_min: statsA.starter_overall_min - statsB.starter_overall_min,
      diff_attack_vs_defense: statsA.overall_mean_ATT - statsB.overall_mean_DEF,
      diff_defense_vs_attack: statsA.overall_mean_DEF - statsB.overall_mean_ATT,
      diff_midfield: statsA.overall_mean_MID - statsB.overall_mean_MID,
      diff_sub_mean: statsA.sub_overall_mean - statsB.sub_overall_mean,
      diff_depth_gap: statsA.depth_gap - statsB.depth_gap,
      diff_market_val_log: Math.log1p(statsA.starter_market_val_sum) - Math.log1p(statsB.starter_market_val_sum),
      diff_form_pts_5: formPtsA - formPtsB,
      diff_form_gd_5: formGdA - formGdB,
      diff_aerial_att_vs_def: statsA.height_mean_ATT - statsB.height_mean_DEF,
      diff_aerial_def_vs_att: statsA.height_mean_DEF - statsB.height_mean_ATT,
      diff_prime_score: statsA.starter_prime_mean - statsB.starter_prime_mean,
      diff_cohesion: cohesionProxy(stA) - cohesionProxy(stB),
      league_tier_factor: Number(body.league_tier_factor ?? 0.95),
    };
    const fBa = {
      diff_overall_mean: -fAb.diff_overall_mean,
      diff_overall_max: -fAb.diff_overall_max,
      diff_overall_min: -fAb.diff_overall_min,
      diff_attack_vs_defense: -fAb.diff_defense_vs_attack,
      diff_defense_vs_attack: -fAb.diff_attack_vs_defense,
      diff_midfield: -fAb.diff_midfield,
      diff_sub_mean: -fAb.diff_sub_mean,
      diff_depth_gap: -fAb.diff_depth_gap,
      diff_market_val_log: -fAb.diff_market_val_log,
      diff_form_pts_5: -fAb.diff_form_pts_5,
      diff_form_gd_5: -fAb.diff_form_gd_5,
      diff_aerial_att_vs_def: -fAb.diff_aerial_def_vs_att,
      diff_aerial_def_vs_att: -fAb.diff_aerial_att_vs_def,
      diff_prime_score: -fAb.diff_prime_score,
      diff_cohesion: -fAb.diff_cohesion,
      league_tier_factor: fAb.league_tier_factor,
    };

    const vecAb = models.feature_cols.map(c => fAb[c]);
    const vecBa = models.feature_cols.map(c => fBa[c]);

    const probAb = softmax(evalHgbtRow(models.model_3class, vecAb));
    const probBa = softmax(evalHgbtRow(models.model_3class, vecBa));

    let pAWin = (probAb[2] + probBa[0]) / 2.0;
    let pBWin = (probAb[0] + probBa[2]) / 2.0;
    let pDraw = (probAb[1] + probBa[1]) / 2.0;

    const xgBaseA = Math.max(0.4, evalHgbtRow(models.model_xg, vecAb)[0]);
    const xgBaseB = Math.max(0.4, evalHgbtRow(models.model_xg, vecBa)[0]);

    const top3G90 = st => st.length ? st.map(p => Number(p.goals_per_90 || 0)).sort((a, b) => b - a).slice(0, 3).reduce((a, b) => a + b, 0) : 0.8;
    const attG90A = top3G90(stA);
    const attG90B = top3G90(stB);

    const attMultA = ((statsA.overall_mean_ATT / 78.0) ** 1.25) * (1.0 + (attG90A - 0.7) / 3.2);
    const attMultB = ((statsB.overall_mean_ATT / 78.0) ** 1.25) * (1.0 + (attG90B - 0.7) / 3.2);
    const defSuppA = (statsA.overall_mean_DEF / 78.0) ** 0.5;
    const defSuppB = (statsB.overall_mean_DEF / 78.0) ** 0.5;
    const formBoostA = 0.88 + 0.12 * (formPtsA / 2.0);
    const formBoostB = 0.88 + 0.12 * (formPtsB / 2.0);

    let xgA = Math.max(0.3, xgBaseA * (attMultA / defSuppB) * formBoostA);
    let xgB = Math.max(0.3, xgBaseB * (attMultB / defSuppA) * formBoostB);

    if (statsA.has_outfield_in_gk) {
      xgB = xgB * 2.2 + 1.2;
      pBWin = Math.min(0.92, pBWin * 1.8 + 0.35);
      pAWin = Math.max(0.04, pAWin * 0.25);
      pDraw = Math.max(0.04, 1.0 - pAWin - pBWin);
    }
    if (statsB.has_outfield_in_gk) {
      xgA = xgA * 2.2 + 1.2;
      pAWin = Math.min(0.92, pAWin * 1.8 + 0.35);
      pBWin = Math.max(0.04, pBWin * 0.25);
      pDraw = Math.max(0.04, 1.0 - pAWin - pBWin);
    }

    const scoreMatrix = [];
    const scoreGrid = Array.from({ length: 6 }, () => Array(6).fill(0.0));
    for (let ga = 0; ga < 6; ga++) {
      const pGa = (Math.pow(xgA, ga) * Math.exp(-xgA)) / factorial(ga);
      for (let gb = 0; gb < 6; gb++) {
        const pGb = (Math.pow(xgB, gb) * Math.exp(-xgB)) / factorial(gb);
        const probPct = Math.round(pGa * pGb * 1000) / 10;
        scoreMatrix.push({ score: `${ga} - ${gb}`, team_a_goals: ga, team_b_goals: gb, prob: probPct });
        scoreGrid[ga][gb] = probPct;
      }
    }
    scoreMatrix.sort((a, b) => b.prob - a.prob);
    const topScore = scoreMatrix[0];

    const scorersA = computePlayerScorers(stA, xgA);
    const scorersB = computePlayerScorers(stB, xgB);
    const over25 = Math.round(scoreMatrix.filter(s => s.team_a_goals + s.team_b_goals > 2).reduce((a, b) => a + b.prob, 0) * 10) / 10;

    const tactical = [
      ['Starting XI quality (effective)', statsA.starter_overall_mean, statsB.starter_overall_mean],
      ['Goalkeeper', statsA.overall_mean_GK, statsB.overall_mean_GK],
      ['Attack line', statsA.overall_mean_ATT, statsB.overall_mean_ATT],
      ['Midfield', statsA.overall_mean_MID, statsB.overall_mean_MID],
      ['Defence line', statsA.overall_mean_DEF, statsB.overall_mean_DEF],
      ['Aerial: attack height vs opp. defence (cm)', statsA.height_mean_ATT, statsB.height_mean_DEF],
      ['Age-prime factor', statsA.starter_prime_mean * 100, statsB.starter_prime_mean * 100],
      ['Bench depth', statsA.sub_overall_mean, statsB.sub_overall_mean],
    ].map(([label, x, y]) => ({ label, home: Math.round(x * 10) / 10, away: Math.round(y * 10) / 10 }));

    let ko = null;
    if (body.knockout) {
      const penA = Math.min(0.58, Math.max(0.42, 0.5 + 0.004 * (statsA.overall_mean_GK - statsB.overall_mean_GK)));
      const advA = pAWin + pDraw * penA;
      ko = {
        shootout_prob: Math.round(pDraw * 1000) / 10,
        shootout_home: Math.round(penA * 1000) / 10,
        advance_home: Math.round(advA * 1000) / 10,
        advance_away: Math.round((1 - advA) * 1000) / 10,
      };
    }

    const pa = Math.round(pAWin * 1000) / 10;
    const pdr = Math.round(pDraw * 1000) / 10;
    const pb = Math.round(pBWin * 1000) / 10;
    const margin = Math.abs(pAWin - pBWin);
    const confidence = margin >= 0.25 ? 'High' : (margin >= 0.10 ? 'Medium' : 'Low');

    let verdictArgmax, headlineArgmax;
    if (pdr >= pa && pdr >= pb) {
      verdictArgmax = 'draw'; headlineArgmax = `Even contest: draw most likely (${pdr}%)`;
    } else if (pa > pb) {
      verdictArgmax = 'home'; headlineArgmax = `${teamAName} favoured to win (${pa}%)`;
    } else {
      verdictArgmax = 'away'; headlineArgmax = `${teamBName} favoured to win (${pb}%)`;
    }

    let verdictTuned, headlineTuned;
    if (pdr >= 27.0) {
      verdictTuned = 'draw'; headlineTuned = `Balanced model: draw identified (${pdr}% >= 27% threshold)`;
    } else if (pa > pb) {
      verdictTuned = 'home'; headlineTuned = `${teamAName} favoured to win (${pa}%)`;
    } else {
      verdictTuned = 'away'; headlineTuned = `${teamBName} favoured to win (${pb}%)`;
    }

    const activeMode = body.threshold_mode || 'tuned';
    const activeVerdict = activeMode === 'tuned' ? verdictTuned : verdictArgmax;
    const headline = ko
      ? `${ko.advance_home >= 50 ? teamAName : teamBName} favoured to advance (${Math.max(ko.advance_home, ko.advance_away)}%)`
      : (activeMode === 'tuned' ? headlineTuned : headlineArgmax);

    const big = tactical.reduce((best, cur) => {
      const sBest = Math.abs(best.home - best.away) / Math.max(best.home, best.away, 1);
      const sCur = Math.abs(cur.home - cur.away) / Math.max(cur.home, cur.away, 1);
      return sCur > sBest ? cur : best;
    });
    const points = [
      `Win probability: ${teamAName} ${pa}% | Draw ${pdr}% | ${teamBName} ${pb}%.`,
      `Most likely score ${topScore.score} (xG ${xgA.toFixed(2)} - ${xgB.toFixed(2)}); over 2.5 goals ${over25}%.`,
      `Biggest edge: ${big.label} favours ${big.home > big.away ? teamAName : teamBName} (${big.home} vs ${big.away}).`,
      `Top scoring threats: ${scorersA[0]?.name || '-'} (${teamAName}, ${scorersA[0]?.anytime_prob ?? 0}%), ${scorersB[0]?.name || '-'} (${teamBName}, ${scorersB[0]?.anytime_prob ?? 0}%).`,
    ];
    if (ko) points.push(`If level after 90 min (${ko.shootout_prob}%), shootout is near coin-flip: ${teamAName} ${ko.shootout_home}%. Advance: ${teamAName} ${ko.advance_home}%, ${teamBName} ${ko.advance_away}%.`);
    const stRowsA = starterRows(stA);
    const stRowsB = starterRows(stB);
    const oop = [...stRowsA, ...stRowsB].filter(p => p.oop_penalty);
    if (oop.length) points.push(`Caution: ${oop.length} starter(s) out of position (rating reduced).`);
    if (statsA.has_outfield_in_gk || statsB.has_outfield_in_gk) points.push('Caution: an outfield player is in goal; result is dominated by this.');

    return {
      status: 'success',
      home_name: teamAName,
      away_name: teamBName,
      home_crest: getTeamCrest(teamAName, presetMeta, clubsLight, countries),
      away_crest: getTeamCrest(teamBName, presetMeta, clubsLight, countries),
      winner_key: activeVerdict,
      verdict_argmax: verdictArgmax,
      verdict_tuned: verdictTuned,
      headline_argmax: headlineArgmax,
      headline_tuned: headlineTuned,
      threshold_tau: 0.27,
      summary: { headline, confidence, points },
      probabilities: { home: pa, draw: pdr, away: pb },
      knockout: ko,
      score_prediction: {
        projected_home_xg: Math.round(xgA * 100) / 100,
        projected_away_xg: Math.round(xgB * 100) / 100,
        most_likely_score: topScore.score,
        top_scores: scoreMatrix.slice(0, 6),
        score_grid: scoreGrid,
        over_2_5_prob: over25,
      },
      goalscorers: { home: scorersA.slice(0, 6), away: scorersB.slice(0, 6) },
      tactical_metrics: tactical,
      lineups: { home: [...stRowsA, ...subRows(sbA)], away: [...stRowsB, ...subRows(sbB)] },
      home_stats: statsA,
      away_stats: statsB,
      inputs: {
        home_form_pts: formPtsA,
        away_form_pts: formPtsB,
        knockout: Boolean(body.knockout),
        threshold_mode: activeMode,
        report_date: effReportDate,
      },
    };
  }

  async function resolveSnapshotSide(teamName, dateStr, autoLineup, formArg, passedSt, passedSb, presets, histPresets, idxObj, clubNormToId) {
    const currPreset = presets[teamName] || presets[`${teamName} (National Team)`] || null;
    const baseForm = normalizeFormation(formArg || currPreset?.formation || '4-3-3');
    const [normDate, , ym] = normalizeDate(dateStr);

    if (!autoLineup) {
      const rawSt = passedSt?.length ? passedSt : (currPreset?.starters || []);
      const rawSb = passedSb ?? currPreset?.subs ?? [];
      const slots = await Promise.all(rawSt.slice(0, 11).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)));
      while (slots.length < 11) slots.push(null);
      const subs = (await Promise.all(rawSb.map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)))).filter(Boolean);
      return [baseForm, slots, subs];
    }

    if (!ym || normDate >= '2026-11-01') {
      if (currPreset) {
        const useForm = normalizeFormation(currPreset.formation || baseForm);
        const st = await Promise.all((currPreset.starters || []).slice(0, 11).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)));
        const subs = (await Promise.all((currPreset.subs || []).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)))).filter(Boolean);
        return [useForm, alignToFormation(st, useForm), subs];
      }
      if (passedSt?.length) {
        const slots = await Promise.all(passedSt.slice(0, 11).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)));
        while (slots.length < 11) slots.push(null);
        const subs = (await Promise.all((passedSb || []).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)))).filter(Boolean);
        return [baseForm, slots, subs];
      }
    }

    let th = histPresets?.[teamName] || histPresets?.[`${teamName} (National Team)`] || null;
    if (!th && histPresets) {
      const tNorm = normalizeText(teamName);
      for (const k of Object.keys(histPresets)) {
        if (normalizeText(k) === tNorm) { th = histPresets[k]; break; }
      }
    }
    if (th && ym) {
      const keys = Object.keys(th).filter(k => k <= ym).sort();
      const hist = keys.length ? th[keys[keys.length - 1]] : null;
      if (hist?.starters?.length) {
        const useForm = normalizeFormation(hist.formation || baseForm);
        const st = await Promise.all(hist.starters.slice(0, 11).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)));
        const aligned = alignToFormation(st, useForm);
        const subs = (await Promise.all((hist.subs || []).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)))).filter(Boolean);
        if (aligned.filter(Boolean).length >= 7) return [useForm, aligned, subs];
      }
    }

    const rawSt = passedSt?.length ? passedSt : (currPreset?.starters || []);
    const rawSb = passedSb?.length ? passedSb : (currPreset?.subs || []);
    const useForm = normalizeFormation(currPreset?.formation || baseForm);
    const slots = await Promise.all(rawSt.slice(0, 11).map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)));
    while (slots.length < 11) slots.push(null);
    const subs = (await Promise.all(rawSb.map(x => resolvePlayer(x, idxObj, dateStr, clubNormToId)))).filter(Boolean);
    return [useForm, slots, subs];
  }

  async function handleApiRequest(urlStr, init = {}) {
    const parsed = new URL(urlStr, g.location ? g.location.href : 'http://localhost/');
    const rawPath = parsed.pathname;
    const apiIdx = rawPath.indexOf('/api/');
    const path = apiIdx >= 0 ? rawPath.slice(apiIdx) : rawPath;
    const qs = parsed.searchParams;
    const method = String(init.method || 'GET').toUpperCase();
    let body = {};
    if (init.body && typeof init.body === 'string') {
      try { body = JSON.parse(init.body); } catch (_) { body = {}; }
    }

    if (path === '/api/health') {
      const idxObj = await getBootIndex();
      return { body: { status: 'ok', players: idxObj.list.length } };
    }
    if (path === '/api/players') {
      return { body: await loadData(qs.get('mode') === 'boot' ? 'boot_players.json' : 'players_full.json') };
    }
    if (path === '/api/presets') return { body: await loadData('presets.json') };
    if (path === '/api/categories') return { body: await loadData('categories.json') };
    if (path === '/api/preset-meta') return { body: await loadData('preset_meta.json') };
    if (path === '/api/thesis-metrics') return { body: await loadData('thesis_metrics.json') };
    if (path === '/api/sync/status') return { body: await loadData('sync_status.json') };
    if (path === '/api/matches/recent') return { body: await loadData('recent_matches.json') };
    if (path === '/api/sync' && method === 'POST') {
      const st = await loadData('sync_status.json').catch(() => ({}));
      return { body: { status: 'success', synced: st.last_result || { mode: 'github_actions', message: 'Matches & players sync automatically every 6h via GitHub Actions.' } } };
    }

    if (path === '/api/snapshot') {
      const reqData = method === 'POST' ? body : Object.fromEntries(qs.entries());
      const dateStr = reqData.date || reqData.report_date || '2026-11';
      const [normDate] = normalizeDate(dateStr);
      const effDate = normDate || '2026-11-01';
      const rawAuto = reqData.auto_lineup ?? true;
      const autoLineup = typeof rawAuto === 'string' ? !['0', 'false', 'no'].includes(rawAuto.toLowerCase()) : Boolean(rawAuto);

      const [presets, histPresets, idxObj, clubsLight] = await Promise.all([
        loadData('presets.json'),
        effDate < '2026-11-01' ? loadData('historical_presets.json').catch(() => ({})) : Promise.resolve({}),
        getPlayersIndex(),
        loadData('clubs_light.json').catch(() => ({})),
      ]);
      const cn2id = clubsLight?.club_norm_to_id || {};
      const [hf, hs, hsb] = await resolveSnapshotSide(reqData.home_name || '', dateStr, autoLineup, reqData.home_formation, reqData.home_starters, reqData.home_subs, presets, histPresets, idxObj, cn2id);
      const [af, as_, asb] = await resolveSnapshotSide(reqData.away_name || '', dateStr, autoLineup, reqData.away_formation, reqData.away_starters, reqData.away_subs, presets, histPresets, idxObj, cn2id);
      return { body: { status: 'success', report_date: effDate, home_formation: hf, away_formation: af, home_slots: hs, home_subs: hsb, away_slots: as_, away_subs: asb } };
    }

    if (path === '/api/predict' && method === 'POST') {
      try {
        return { body: await handlePredict(body) };
      } catch (e) {
        return { status: 400, body: { status: 'error', message: String(e?.message || e) } };
      }
    }

    if (path === '/api/export' && method === 'POST') {
      const bytes = buildXlsxBytes(body);
      return { rawBytes: bytes, contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' };
    }

    if (path === '/api/explore/overview') return { body: await loadData('overview.json') };

    if (path === '/api/explore/leagues') {
      const ld = await loadData('leagues.json');
      return { body: { status: 'success', regions: ld.regions || EXPLORE_REGIONS, leagues: ld.leagues || [] } };
    }

    if (path === '/api/explore/league') {
      const rawCid = (qs.get('comp_id') || 'GB1').trim();
      const ld = await loadData('leagues.json');
      const foundLg = (ld.leagues || []).find(l => l.comp_id.toUpperCase() === rawCid.toUpperCase());
      if (!foundLg) return { status: 404, body: { status: 'error', message: 'League not found' } };
      const lgFile = await loadData(`leagues/${foundLg.comp_id}.json`);
      const avail = lgFile.available_seasons || [2026];
      const reqSeason = qs.get('season');
      const seasonStr = reqSeason && lgFile.seasons?.[String(reqSeason)] ? String(reqSeason) : String(avail[0]);
      const sd = lgFile.seasons?.[seasonStr] || {};
      return {
        body: {
          status: 'success',
          league: lgFile.league,
          season: Number(seasonStr),
          available_seasons: avail,
          summary: sd.summary || {},
          standings: sd.standings || [],
          top_scorers: sd.top_scorers || [],
          top_assisters: sd.top_assisters || [],
          top_rated: sd.top_rated || [],
          recent_matches: sd.recent_matches || [],
        },
      };
    }

    if (path === '/api/explore/players') {
      const idxObj = await getPlayersIndex();
      const qNorm = normalizeText(qs.get('q') || '');
      const pos = (qs.get('pos') || qs.get('role') || '').trim().toUpperCase();
      const statusFilter = (qs.get('status') || 'active').trim().toLowerCase();
      const clubQ = normalizeText(qs.get('club') || '');
      let natQ = normalizeText(qs.get('nat') || '');
      natQ = CTRY_ALIASES[natQ] || natQ;
      const sortBy = (qs.get('sort') || 'rating').trim().toLowerCase();
      const minRat = qs.get('min_rating') ? Number(qs.get('min_rating')) : null;
      const limit = Math.max(1, Math.min(parseInt(qs.get('limit') || '40', 10) || 40, 200));

      const matches = [];
      for (const p of idxObj.list) {
        const isF = Boolean(p.is_former);
        if (statusFilter === 'active' && isF) continue;
        if (['former', 'legends', 'retired'].includes(statusFilter) && !isF) continue;
        if (pos && pos !== 'ALL') {
          if (String(p.pos || '').toUpperCase() !== pos && String(p.role || '').toUpperCase() !== pos) continue;
        }
        if (minRat != null && Number.isFinite(minRat) && Number(p.rating || 0) < minRat) continue;
        if (clubQ && !normalizeText(`${p.club || ''} ${p.former_club || ''}`).includes(clubQ)) continue;
        if (natQ && !normalizeText(p.nat).includes(natQ)) continue;
        if (qNorm && !normalizeText(`${p.name || ''} ${p.full_name || ''} ${p.tm_name || ''} ${p.club || ''} ${p.former_club || ''} ${p.nat || ''}`).includes(qNorm)) continue;
        matches.push(p);
      }

      matches.sort((a, b) => {
        if (sortBy === 'val') return (Number(b.val || 0) - Number(a.val || 0)) || (Number(b.rating || 0) - Number(a.rating || 0));
        if (sortBy === 'goals') return ((b.total_goals || 0) - (a.total_goals || 0)) || (Number(b.rating || 0) - Number(a.rating || 0));
        if (sortBy === 'assists') return ((b.total_assists || 0) - (a.total_assists || 0)) || (Number(b.rating || 0) - Number(a.rating || 0));
        return (Number(b.rating || 0) - Number(a.rating || 0)) || (Number(b.val || 0) - Number(a.val || 0));
      });

      const sliced = matches.slice(0, limit);
      const shardIds = [...new Set(sliced.filter(p => p.id != null).map(p => shardIdx(p.id)))];
      const shards = {};
      await Promise.all(shardIds.map(async s => { shards[s] = await loadData(`player_details_shard_${s}.json`); }));
      const playersOut = await Promise.all(sliced.map(p => enrichPlayerSummary(p, p.id != null ? shards[shardIdx(p.id)] : null)));
      return { body: { status: 'success', status_filter: statusFilter, total: matches.length, players: playersOut } };
    }

    const playerMatch = path.match(/^\/api\/explore\/player\/(\d+)$/);
    if (playerMatch) {
      const pid = Number(playerMatch[1]);
      const [idxObj, shard, ld] = await Promise.all([
        getPlayersIndex(),
        loadData(`player_details_shard_${shardIdx(pid)}.json`),
        loadData('leagues.json'),
      ]);
      const base = idxObj.byId.get(pid);
      if (!base) return { status: 404, body: { status: 'error', message: 'Player not found' } };
      const player = { ...base };
      const det = shard.details?.[String(pid)];
      const lm = ld.leagues_meta || {};
      if (det) {
        const cid = det.length > 9 ? det[9] : '';
        Object.assign(player, {
          foot: det[0], dob: det[1], city_of_birth: det[2], country_of_birth: det[3],
          contract: det[4], image_url: det[5], highest_val: det[6], caps: det[7], int_goals: det[8],
          comp_id: cid, comp_name: lm[cid]?.name || cid,
        });
      }
      const seasons = (shard.seasons?.[String(pid)] || []).map(s => ({
        season: s[0], comp_id: s[1], comp_name: lm[s[1]]?.name || s[1], club: s[2],
        apps: s[3], minutes: s[4], goals: s[5], assists: s[6], yellow_cards: s[7], red_cards: s[8],
      }));
      const snapshots = (shard.snapshots?.[String(pid)] || []).map(([rd, cl, rt, fd, vl, ag, g9, tg]) => ({
        report_date: rd, club: cl, rating: rt, form_delta: fd ?? 0.0, val: vl, age: ag, goals_per_90: g9, total_goals: tg,
      }));
      return { body: { status: 'success', player, seasons, snapshots } };
    }

    if (path === '/api/explore/clubs') {
      const clData = await loadData('clubs_light.json');
      const qNorm = normalizeText(qs.get('q') || '');
      const compId = (qs.get('comp_id') || '').trim().toUpperCase();
      const ctryQ = normalizeText(qs.get('country') || '');
      const sortBy = (qs.get('sort') || 'val').trim().toLowerCase();
      const limit = Math.max(1, Math.min(parseInt(qs.get('limit') || '40', 10) || 40, 200));

      const skipNames = new Set(['---', 'Unknown', 'Disqualification', 'Without Club', 'Retired', 'Career break']);
      const matches = (clData.clubs || []).filter(c => {
        if (skipNames.has(c.name)) return false;
        if (compId && compId !== 'ALL' && String(c.comp_id || '').toUpperCase() !== compId) return false;
        if (ctryQ && !normalizeText(c.country_name).includes(ctryQ)) return false;
        if (qNorm && !normalizeText(`${c.name || ''} ${c.comp_name || ''} ${c.country_name || ''} ${c.coach_name || ''}`).includes(qNorm)) return false;
        return true;
      });

      matches.sort((a, b) => {
        if (sortBy === 'rating' || sortBy === 'avg_rating') return (Number(b.avg_rating || 0) - Number(a.avg_rating || 0)) || (Number(b.total_val || 0) - Number(a.total_val || 0));
        if (sortBy === 'squad' || sortBy === 'squad_size') return ((b.squad_size || 0) - (a.squad_size || 0)) || (Number(b.total_val || 0) - Number(a.total_val || 0));
        if (sortBy === 'name') return String(a.name || '').toLowerCase().localeCompare(String(b.name || '').toLowerCase());
        return (Number(b.total_val || 0) - Number(a.total_val || 0)) || (Number(b.avg_rating || 0) - Number(a.avg_rating || 0));
      });
      return { body: { status: 'success', total: matches.length, clubs: matches.slice(0, limit) } };
    }

    if (path === '/api/explore/club') {
      const [clData, idxObj, presets] = await Promise.all([loadData('clubs_light.json'), getPlayersIndex(), loadData('presets.json')]);
      const byCid = new Map((clData.clubs || []).map(c => [String(c.club_id), c]));
      const cidArg = (qs.get('id') || '').trim();
      const nameArg = (qs.get('name') || '').trim();
      let cidStr = null;
      if (cidArg && byCid.has(cidArg)) {
        cidStr = cidArg;
      } else if (nameArg) {
        const nNorm = normalizeText(nameArg);
        const mapped = clData.club_norm_to_id?.[nNorm];
        if (mapped != null && byCid.has(String(mapped))) cidStr = String(mapped);
        else {
          const cands = (clData.clubs || []).filter(c => nNorm && normalizeText(c.name).includes(nNorm));
          cands.sort((a, b) => ((normalizeText(a.name).startsWith(nNorm) ? 0 : 1) - (normalizeText(b.name).startsWith(nNorm) ? 0 : 1)) || (Number(b.total_val || 0) - Number(a.total_val || 0)));
          if (cands.length) cidStr = String(cands[0].club_id);
        }
      }
      if (!cidStr || !byCid.has(cidStr)) return { status: 404, body: { status: 'error', message: 'Club not found' } };

      const club = { ...byCid.get(cidStr) };
      const extrasShard = await loadData(`clubs_extras_shard_${shardIdx(cidStr)}.json`);
      const extras = extrasShard[cidStr] || {};
      const cNameNorm = normalizeText(club.name);

      let rosterRaw = (extras.player_ids || []).map(pid => idxObj.byId.get(Number(pid))).filter(p => p && !p.is_former);
      if (!rosterRaw.length) rosterRaw = idxObj.list.filter(p => !p.is_former && normalizeText(p.club) === cNameNorm);

      let formerRaw = (extras.former_player_ids || []).map(pid => idxObj.byId.get(Number(pid))).filter(p => p && p.is_former);
      if (!formerRaw.length) formerRaw = idxObj.list.filter(p => p.is_former && (normalizeText(p.former_club) === cNameNorm || normalizeText(p.club) === cNameNorm)).slice(0, 30);

      const allPeople = [...rosterRaw, ...formerRaw];
      const shardIds = [...new Set(allPeople.filter(p => p.id != null).map(p => shardIdx(p.id)))];
      const pShards = {};
      await Promise.all(shardIds.map(async s => { pShards[s] = await loadData(`player_details_shard_${s}.json`); }));

      const roster = await Promise.all(rosterRaw.map(p => enrichPlayerSummary(p, p.id != null ? pShards[shardIdx(p.id)] : null)));
      const formerPlayers = await Promise.all(formerRaw.map(p => enrichPlayerSummary(p, p.id != null ? pShards[shardIdx(p.id)] : null)));

      return {
        body: {
          status: 'success',
          club,
          season_records: extras.season_records || [],
          recent_matches: extras.recent_matches || [],
          roster,
          former_players: formerPlayers,
          preset: club.preset_name ? (presets[club.preset_name] || null) : null,
        },
      };
    }

    if (path === '/api/explore/countries') {
      const countries = await loadData('countries.json');
      const qNorm = normalizeText(qs.get('q') || '');
      const conf = (qs.get('confederation') || '').trim().toUpperCase();
      const sortBy = (qs.get('sort') || 'fifa').trim().toLowerCase();
      const limit = Math.max(1, Math.min(parseInt(qs.get('limit') || '124', 10) || 124, 200));

      const matches = countries.filter(c => {
        if (conf && conf !== 'ALL' && String(c.confederation || '').toUpperCase() !== conf) return false;
        if (qNorm && !normalizeText(`${c.name || ''} ${c.code || ''} ${c.nt_name || ''}`).includes(qNorm)) return false;
        return true;
      }).map(({ top_player_ids, top_clubs, domestic_leagues, ...rest }) => rest);

      matches.sort((a, b) => {
        if (sortBy === 'rating' || sortBy === 'top11_avg_rating') return (Number(b.top11_avg_rating || 0) - Number(a.top11_avg_rating || 0)) || ((a.fifa_ranking || 999) - (b.fifa_ranking || 999));
        if (sortBy === 'val' || sortBy === 'top25_val') return (Number(b.top25_val || 0) - Number(a.top25_val || 0)) || (Number(b.top11_avg_rating || 0) - Number(a.top11_avg_rating || 0));
        if (sortBy === 'players' || sortBy === 'total_players') return ((b.total_players || 0) - (a.total_players || 0)) || (Number(b.top11_avg_rating || 0) - Number(a.top11_avg_rating || 0));
        if (sortBy === 'name') return String(a.name || '').toLowerCase().localeCompare(String(b.name || '').toLowerCase());
        return ((a.fifa_ranking ?? 999) - (b.fifa_ranking ?? 999)) || (Number(b.top11_avg_rating || 0) - Number(a.top11_avg_rating || 0));
      });
      return { body: { status: 'success', total: matches.length, countries: matches.slice(0, limit) } };
    }

    if (path === '/api/explore/country') {
      const [countries, idxObj, presets] = await Promise.all([loadData('countries.json'), getPlayersIndex(), loadData('presets.json')]);
      const cobj = findCountryObj(qs.get('name') || '', countries);
      if (!cobj) return { status: 404, body: { status: 'error', message: 'Country not found' } };
      const { top_player_ids, top_clubs, domestic_leagues, ...country } = cobj;
      const tpRaw = (top_player_ids || []).map(pid => idxObj.byId.get(Number(pid))).filter(Boolean);
      const shardIds = [...new Set(tpRaw.filter(p => p.id != null).map(p => shardIdx(p.id)))];
      const pShards = {};
      await Promise.all(shardIds.map(async s => { pShards[s] = await loadData(`player_details_shard_${s}.json`); }));
      const topPlayers = await Promise.all(tpRaw.map(p => enrichPlayerSummary(p, p.id != null ? pShards[shardIdx(p.id)] : null)));
      return {
        body: {
          status: 'success',
          country,
          domestic_leagues: domestic_leagues || [],
          top_clubs: top_clubs || [],
          top_players: topPlayers,
          preset: cobj.nt_preset_name ? (presets[cobj.nt_preset_name] || null) : null,
        },
      };
    }

    return { status: 404, body: { status: 'error', message: `Unsupported route: ${path}` } };
  }

  function toResponse(res) {
    if (res.rawBytes) {
      return new Response(res.rawBytes, { status: 200, headers: { 'Content-Type': res.contentType } });
    }
    return new Response(JSON.stringify(res.body), {
      status: res.status || 200,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  if (typeof window !== 'undefined' && nativeFetch) {
    const forceStatic = Boolean(window.__STATIC_MODE__) || /\.github\.io$/i.test(window.location?.hostname || '') || window.location?.protocol === 'file:';
    let fallbackActivated = forceStatic;

    window.fetch = async (input, init) => {
      const urlStr = typeof input === 'string' ? input : (input?.url || '');
      const u = new URL(urlStr, window.location.href);
      if (!u.pathname.includes('/api/')) return nativeFetch(input, init);

      if (fallbackActivated) return toResponse(await handleApiRequest(u.href, init));

      try {
        const resp = await nativeFetch(input, init);
        if (resp.status !== 404 && resp.status !== 405) return resp;
        fallbackActivated = true;
      } catch (_) {
        fallbackActivated = true;
      }
      return toResponse(await handleApiRequest(u.href, init));
    };
  }

  g.PitchPulseGHPagesEngine = { evalHgbtRow, handleApiRequest, buildXlsxBytes };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = g.PitchPulseGHPagesEngine;
  }
})();
