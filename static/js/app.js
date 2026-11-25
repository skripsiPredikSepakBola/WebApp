const $ = id => document.getElementById(id);
const escRaw = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const esc = s => escRaw(String(s ?? '').replaceAll(' (National Team)', ''));

const OOP = {
  GK: { GK: 0, DEF: 40, MID: 45, ATT: 45 },
  DEF: { GK: 45, DEF: 0, MID: 4, ATT: 18 },
  MID: { GK: 45, DEF: 6, MID: 0, ATT: 4 },
  ATT: { GK: 45, DEF: 18, MID: 5, ATT: 0 },
};

const ROLE_GROUP = {
  GK: 'GK',
  CB: 'DEF', LB: 'DEF', RB: 'DEF', DEF: 'DEF',
  CDM: 'MID', CM: 'MID', CAM: 'MID', LM: 'MID', RM: 'MID', MID: 'MID',
  LW: 'ATT', RW: 'ATT', CF: 'ATT', ST: 'ATT', ATT: 'ATT',
};

const GRANULAR_OOP = {
  ST: { CF: 1, LW: 5, RW: 5 },
  CF: { ST: 1, LW: 5, RW: 5, CAM: 3 },
  LW: { RW: 2, ST: 4, CF: 4, LM: 2, RM: 2, CAM: 3 },
  RW: { LW: 2, ST: 4, CF: 4, LM: 2, RM: 2, CAM: 3 },
  CAM: { CM: 2, CDM: 5, LM: 3, RM: 3, LW: 3, RW: 3, CF: 3 },
  CM: { CAM: 2, CDM: 2, LM: 2, RM: 2 },
  CDM: { CM: 2, CAM: 5, LM: 5, RM: 5, CB: 4 },
  LM: { RM: 2, CM: 2, CAM: 3, CDM: 5, LW: 2, RW: 2, LB: 3, RB: 3 },
  RM: { LM: 2, CM: 2, CAM: 3, CDM: 5, LW: 2, RW: 2, LB: 3, RB: 3 },
  LB: { RB: 3, CB: 4, LM: 3, RM: 3 },
  RB: { LB: 3, CB: 4, LM: 3, RM: 3 },
  CB: { LB: 5, RB: 5, CDM: 5 },
};

const FORMATION_LAYOUTS = {
  '4-3-3': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'LB', u: 0.162, v: 0.12 },
    { role: 'CB', u: 0.152, v: 0.36 },
    { role: 'CB', u: 0.152, v: 0.64 },
    { role: 'RB', u: 0.162, v: 0.88 },
    { role: 'CM', u: 0.298, v: 0.24 },
    { role: 'CDM', u: 0.256, v: 0.50 },
    { role: 'CM', u: 0.298, v: 0.76 },
    { role: 'LW', u: 0.410, v: 0.14 },
    { role: 'ST', u: 0.435, v: 0.50 },
    { role: 'RW', u: 0.410, v: 0.86 },
  ],
  '4-2-3-1': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'LB', u: 0.162, v: 0.12 },
    { role: 'CB', u: 0.152, v: 0.36 },
    { role: 'CB', u: 0.152, v: 0.64 },
    { role: 'RB', u: 0.162, v: 0.88 },
    { role: 'CDM', u: 0.256, v: 0.33 },
    { role: 'CDM', u: 0.256, v: 0.67 },
    { role: 'LW', u: 0.352, v: 0.13 },
    { role: 'CAM', u: 0.340, v: 0.50 },
    { role: 'RW', u: 0.352, v: 0.87 },
    { role: 'ST', u: 0.442, v: 0.50 },
  ],
  '4-4-2': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'LB', u: 0.162, v: 0.11 },
    { role: 'CB', u: 0.152, v: 0.35 },
    { role: 'CB', u: 0.152, v: 0.65 },
    { role: 'RB', u: 0.162, v: 0.89 },
    { role: 'LM', u: 0.295, v: 0.11 },
    { role: 'CM', u: 0.285, v: 0.35 },
    { role: 'CM', u: 0.285, v: 0.65 },
    { role: 'RM', u: 0.295, v: 0.89 },
    { role: 'ST', u: 0.430, v: 0.35 },
    { role: 'CF', u: 0.415, v: 0.65 },
  ],
  '3-5-2': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'CB', u: 0.158, v: 0.22 },
    { role: 'CB', u: 0.152, v: 0.50 },
    { role: 'CB', u: 0.158, v: 0.78 },
    { role: 'LM', u: 0.285, v: 0.10 },
    { role: 'CDM', u: 0.258, v: 0.32 },
    { role: 'CAM', u: 0.342, v: 0.50 },
    { role: 'CM', u: 0.258, v: 0.68 },
    { role: 'RM', u: 0.285, v: 0.90 },
    { role: 'ST', u: 0.440, v: 0.32 },
    { role: 'CF', u: 0.432, v: 0.68 },
  ],
  '3-4-3': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'CB', u: 0.158, v: 0.22 },
    { role: 'CB', u: 0.152, v: 0.50 },
    { role: 'CB', u: 0.158, v: 0.78 },
    { role: 'LM', u: 0.288, v: 0.11 },
    { role: 'CM', u: 0.278, v: 0.35 },
    { role: 'CM', u: 0.278, v: 0.65 },
    { role: 'RM', u: 0.288, v: 0.89 },
    { role: 'LW', u: 0.412, v: 0.16 },
    { role: 'ST', u: 0.435, v: 0.50 },
    { role: 'RW', u: 0.412, v: 0.84 },
  ],
  '5-3-2': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'LB', u: 0.188, v: 0.10 },
    { role: 'CB', u: 0.156, v: 0.30 },
    { role: 'CB', u: 0.150, v: 0.50 },
    { role: 'CB', u: 0.156, v: 0.70 },
    { role: 'RB', u: 0.188, v: 0.90 },
    { role: 'CM', u: 0.305, v: 0.26 },
    { role: 'CDM', u: 0.262, v: 0.50 },
    { role: 'CM', u: 0.305, v: 0.74 },
    { role: 'ST', u: 0.432, v: 0.35 },
    { role: 'CF', u: 0.418, v: 0.65 },
  ],
  '5-4-1': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'LB', u: 0.188, v: 0.10 },
    { role: 'CB', u: 0.156, v: 0.30 },
    { role: 'CB', u: 0.150, v: 0.50 },
    { role: 'CB', u: 0.156, v: 0.70 },
    { role: 'RB', u: 0.188, v: 0.90 },
    { role: 'LM', u: 0.312, v: 0.11 },
    { role: 'CM', u: 0.296, v: 0.35 },
    { role: 'CM', u: 0.296, v: 0.65 },
    { role: 'RM', u: 0.312, v: 0.89 },
    { role: 'ST', u: 0.435, v: 0.50 },
  ],
  '4-1-4-1': [
    { role: 'GK', u: 0.048, v: 0.50 },
    { role: 'LB', u: 0.162, v: 0.11 },
    { role: 'CB', u: 0.152, v: 0.33 },
    { role: 'CB', u: 0.152, v: 0.67 },
    { role: 'RB', u: 0.162, v: 0.89 },
    { role: 'CDM', u: 0.246, v: 0.50 },
    { role: 'LM', u: 0.340, v: 0.11 },
    { role: 'CM', u: 0.336, v: 0.33 },
    { role: 'CM', u: 0.336, v: 0.67 },
    { role: 'RM', u: 0.340, v: 0.89 },
    { role: 'ST', u: 0.442, v: 0.50 },
  ],
};

const FORMATIONS = Object.keys(FORMATION_LAYOUTS);
const FORMS = [[2.6, 'Excellent (4W 1D)'], [2.0, 'Good (3W 1D 1L)'], [1.4, 'Average (2W 1D 2L)'], [0.6, 'Poor (0-1W)']];
const TEAMS = ['home', 'away'];
const CONF = { High: 'One side is clearly stronger.', Medium: 'One side has an edge, but upsets are common.', Low: 'The sides are close. Read this as a lean, not a call.' };

let players = [], byId = new Map(), byRating = [], nameIdx = new Map(), presets = {}, presetMeta = {}, flat = [], last = null, busy = false, ctx = null;
const mk = () => ({ name: '', formation: '4-3-3', form: 2.0, slots: Array(11).fill(null), subs: [] });
const T = { home: mk(), away: mk() };

let activeView = 'predictor';
let activeExSub = 'players';
let leaguesCache = null;
let activeContinent = 'All';
let activeCountry = 'All';
let activeLeaderKey = 'top_scorers';
let lastLeagueData = null;
let exPlayersCtx = { club: '', nat: '' };
let exClubsCtx = { country: '' };
let currentPlayerDetail = null;
let currentClubDetail = null;
let currentCountryDetail = null;
let activeChartMetric = 'rating';
let dlgFilterMode = 'exact';
let dlgUserPickedFilter = false;
let dlgSourceMode = 'squad';
let dlgSummaryReqId = 0;
let pitchViewMode = matchMedia('(max-width:760px)').matches ? 'home' : 'both';
let pitchViewUserPicked = false;
let pitchSwapMode = false;
let swapArmed = null;
let syncStatusData = null;
let calCache = new Map();
let calActiveMonth = new Date().toISOString().slice(0, 7);
let calSelectedDate = new Date().toISOString().slice(0, 10);
let calScope = 'day';
let calData = null;

const clean = t => (t || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, ' ').trim();
const short = n => { const w = (n || '').split(' '); return w.length > 1 ? w.slice(1).join(' ') : (n || ''); };
const posFallback = pos => ({ GK: 'GK', DEF: 'CB', MID: 'CM', ATT: 'ST' }[pos] || 'CM');
const playerRole = p => (p && (p.role || p.pos_role)) || posFallback(p?.pos);
const roleToGroup = r => ROLE_GROUP[r] || 'MID';

function oopPenalty(p, slotRole) {
  if (!p || !slotRole || slotRole === 'SUB') return 0;
  const nr = playerRole(p);
  if (nr === slotRole) return 0;
  const gFrom = roleToGroup(nr);
  const gTo = roleToGroup(slotRole);
  if (slotRole === 'GK' || nr === 'GK') return OOP[gFrom]?.[gTo] ?? 45;
  if (slotRole === 'DEF' || slotRole === 'MID' || slotRole === 'ATT') {
    return OOP[gFrom]?.[slotRole] ?? 0;
  }
  if (GRANULAR_OOP[nr]?.[slotRole] !== undefined) return GRANULAR_OOP[nr][slotRole];
  return OOP[gFrom]?.[gTo] ?? 0;
}

const eff = (p, slotRole) => {
  if (!p) return 0;
  if (slotRole === 'SUB') return p.rating;
  return Math.max(35, p.rating - oopPenalty(p, slotRole));
};

const fmtVal = v => {
  const n = Number(v);
  if (!n || Number.isNaN(n)) return '-';
  if (n >= 1e6) return `€${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `€${Math.round(n / 1e3)}K`;
  return `€${Math.round(n)}`;
};
const fmtNum = v => (v === null || v === undefined || v === '') ? '-' : Number(v).toLocaleString();

function initialsOf(name) {
  const parts = String(name || '').replace(/\(National Team\)/gi, '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function shieldSvg() {
  return '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" aria-hidden="true"><path d="M12 2.5L20 6V12.5C20 17.5 16.5 20.8 12 22.3C7.5 20.8 4 17.5 4 12.5V6L12 2.5Z" fill="#efe9df" stroke="#7b7266" stroke-width="1.5"/></svg>';
}

function crestUrlFor(teamName, explicitUrl = '') {
  if (explicitUrl) return explicitUrl;
  if (!teamName) return '';
  const base = String(teamName).replace(/ \(National Team\)/, '');
  const meta = presetMeta[teamName]
    || presetMeta[`${base} (National Team)`]
    || presetMeta[clean(teamName)]
    || presetMeta[clean(base)];
  if (meta?.crest_url) return meta.crest_url;
  if (meta?.club_id > 0) return `https://tmssl.akamaized.net/images/wappen/head/${meta.club_id}.png`;
  return '';
}

function clubCrestUrl(c) {
  if (!c) return '';
  if (c.crest_url) return c.crest_url;
  const cid = Number(c.club_id);
  return cid > 0 ? `https://tmssl.akamaized.net/images/wappen/head/${cid}.png` : '';
}

function crestHtml(url, name, cls = 'crest-sm') {
  const safeName = escRaw(String(name || '').replace(' (National Team)', ''));
  if (url) {
    return `<img class="${cls}" src="${escRaw(url)}" alt="${safeName} crest" loading="lazy" referrerpolicy="no-referrer" onerror="this.hidden=true;if(this.nextElementSibling)this.nextElementSibling.hidden=false"><span class="${cls} crest-fb" hidden aria-hidden="true">${shieldSvg()}</span>`;
  }
  return `<span class="${cls} crest-fb" aria-hidden="true">${shieldSvg()}</span>`;
}

function ratingTier(rating) {
  const n = Number(rating);
  if (!n || Number.isNaN(n)) return 'tier-bronze';
  if (n >= 83) return 'tier-gold';
  if (n >= 72) return 'tier-silver';
  return 'tier-bronze';
}

function avatarHtml(url, name, cls = 'av-sm', rating = null) {
  const ini = escRaw(initialsOf(name));
  const tier = rating !== null && rating !== undefined ? ` ${ratingTier(rating)}` : '';
  if (url) {
    return `<img class="${cls}${tier}" src="${escRaw(url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.hidden=true;if(this.nextElementSibling)this.nextElementSibling.hidden=false"><span class="${cls}${tier} av-fb" hidden aria-hidden="true">${ini}</span>`;
  }
  return `<span class="${cls}${tier} av-fb" aria-hidden="true">${ini}</span>`;
}

function indexPlayers(list) {
  players = Array.isArray(list) ? list : [];
  byId = new Map();
  nameIdx = new Map();
  byRating = [...players].sort((a, b) => (b.rating || 0) - (a.rating || 0));
  for (const x of players) {
    byId.set(x.id, x);
    for (const k of [x.name, x.full_name, x.tm_name]) {
      const c = clean(k);
      if (c && !nameIdx.has(c)) nameIdx.set(c, x);
    }
  }
}

function layout(f) {
  const safeF = FORMATION_LAYOUTS[f] ? f : '4-3-3';
  return FORMATION_LAYOUTS[safeF];
}

function wireQuickChips() {
  document.querySelectorAll('.quick .chip').forEach(b => {
    b.onclick = async () => {
      loadPreset('home', b.dataset.a);
      loadPreset('away', b.dataset.b);
      if (($('wi-date')?.value || '2026-11') !== '2026-11') await applySnapshot();
      predict();
    };
  });
}

async function init() {
  const [pBoot, pr, cat, pMeta] = await Promise.all([
    fetch('/api/players?mode=boot').then(r => r.json()),
    fetch('/api/presets').then(r => r.json()),
    fetch('/api/categories').then(r => r.json()),
    fetch('/api/preset-meta').then(r => r.ok ? r.json() : {}).catch(() => ({}))
  ]);
  presets = pr || {};
  presetMeta = pMeta || {};
  indexPlayers(pBoot);
  flat = [];
  for (const [c, names] of Object.entries(cat || {})) {
    const cleanCat = c.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\uFE0F]/gu, '').replace(/^[^\p{L}\p{N}]+/u, '').trim();
    const isLegendCat = /legend|icon/i.test(c);
    names.forEach(n => flat.push({ n, c: cleanCat, isLegend: isLegendCat || /legends$/i.test(n) }));
  }

  if (presets['FC Barcelona Legends'] && presets['Real Madrid Legends'] && $('quick-fixtures')) {
    const btn = document.createElement('button');
    btn.className = 'chip legend-chip';
    btn.type = 'button';
    btn.dataset.a = 'Real Madrid Legends';
    btn.dataset.b = 'FC Barcelona Legends';
    btn.textContent = 'Real Madrid Legends v Barça Legends';
    $('quick-fixtures').appendChild(btn);
  }

  TEAMS.forEach(buildPicker);
  wireQuickChips();

  TEAMS.forEach(t => {
    const pSel = $('ptool-' + t + '-f');
    if (pSel) {
      pSel.innerHTML = FORMATIONS.map(f => `<option>${f}</option>`).join('');
      pSel.onchange = e => {
        rearrangeLineupForFormation(t, e.target.value, { useBench: false });
        render();
        predict();
      };
    }
    const autoBtn = $(t + '-autofit');
    if (autoBtn) {
      autoBtn.onclick = () => {
        rearrangeLineupForFormation(t, T[t].formation, { useBench: true });
        render();
        predict();
      };
    }
  });

  if ($('pitch-view-tabs')) {
    $('pitch-view-tabs').onclick = e => {
      const b = e.target.closest('button[data-pitch-view]');
      if (!b) return;
      pitchViewMode = b.dataset.pitchView;
      pitchViewUserPicked = true;
      render();
    };
  }
  if ($('pitch-swap-mode-btn')) {
    $('pitch-swap-mode-btn').onclick = () => {
      pitchSwapMode = !pitchSwapMode;
      if (!pitchSwapMode) swapArmed = null;
      updateSwapUI();
      renderPitch();
      renderBench();
    };
  }
  if ($('swap-banner-cancel')) $('swap-banner-cancel').onclick = cancelSwapMode;
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && (swapArmed || pitchSwapMode)) cancelSwapMode();
  });

  $('swap-sides-btn').onclick = swapSides;

  $('pitch').onclick = e => {
    const b = e.target.closest('.tok');
    if (!b) return;
    const t = b.dataset.t, i = +b.dataset.i;
    if (handleSwapTap(t, 'slot', i)) return;
    openDlg(t, 'slot', i);
  };
  TEAMS.forEach(t => $('bench-' + t).onclick = e => {
    const ins = e.target.closest('button[data-inspect]');
    if (ins) { openPlayerInspector(+ins.dataset.inspect); return; }
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.rm !== undefined) {
      if (swapArmed && swapArmed.t === t && swapArmed.kind === 'sub' && swapArmed.i === +b.dataset.rm) swapArmed = null;
      T[t].subs.splice(+b.dataset.rm, 1);
      render();
      predict();
      return;
    }
    const idx = b.dataset.i === undefined ? -1 : +b.dataset.i;
    if (idx >= 0 && handleSwapTap(t, 'sub', idx)) return;
    openDlg(t, 'sub', idx);
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('.pk-search')) document.querySelectorAll('.pk-list:not(.g-search-list)').forEach(l => l.hidden = true);
    if (!e.target.closest('.g-search') && $('global-search-results')) $('global-search-results').hidden = true;
  });
  matchMedia('(max-width:760px)').onchange = () => {
    if (!pitchViewUserPicked) {
      pitchViewMode = matchMedia('(max-width:760px)').matches ? 'home' : 'both';
    }
    render();
  };
  $('predict-btn').onclick = predict;
  $('dlg-q').oninput = fillDlg;
  if ($('dlg-source-tabs')) {
    $('dlg-source-tabs').onclick = e => {
      const b = e.target.closest('button[data-source]');
      if (!b) return;
      dlgSourceMode = b.dataset.source;
      document.querySelectorAll('#dlg-source-tabs .seg-btn').forEach(x => x.classList.toggle('active', x === b));
      fillDlg();
    };
  }
  if ($('dlg-quick-swap')) {
    $('dlg-quick-swap').onclick = () => {
      if (!ctx) return;
      const target = { t: ctx.t, kind: ctx.kind, i: ctx.i };
      $('dlg').close();
      swapArmed = target;
      updateSwapUI();
      renderPitch();
      renderBench();
    };
  }
  if ($('dlg')) {
    $('dlg').addEventListener('close', () => { dlgSummaryReqId++; });
  }
  if ($('dlg-role-pills')) {
    $('dlg-role-pills').onclick = e => {
      const b = e.target.closest('button[data-mode]');
      if (!b) return;
      dlgFilterMode = b.dataset.mode;
      dlgUserPickedFilter = true;
      document.querySelectorAll('#dlg-role-pills .filter-pill').forEach(x => x.classList.toggle('active', x === b));
      fillDlg();
    };
  }
  if ($('dlg-legends')) $('dlg-legends').onchange = fillDlg;
  $('dlg-list').onclick = e => { const b = e.target.closest('button'); if (b) assign(byId.get(+b.dataset.id)); };
  $('dlg-clear').onclick = () => assign(null);
  if ($('dlg-inspect')) $('dlg-inspect').onclick = () => {
    if (!ctx) return;
    const p = ctx.kind === 'slot' ? T[ctx.t].slots[ctx.i] : T[ctx.t].subs[ctx.i];
    $('dlg').close();
    if (p?.id) openPlayerInspector(p.id);
  };
  $('knockout').onchange = () => { if (last) predict(); };
  if ($('neutral')) $('neutral').onchange = () => { if (last) predict(); };
  $('exp').onclick = exportXlsx;
  if ($('imp-xlsx') && $('imp-xlsx-file')) {
    $('imp-xlsx').onclick = () => $('imp-xlsx-file').click();
    $('imp-xlsx-file').onchange = importXlsx;
  }
  if ($('sync-btn')) $('sync-btn').onclick = syncMatches;
  wireSyncModal();
  loadThesisAndRecent();
  loadSyncStatus();
  setInterval(loadSyncStatus, 60000);
  enableDragAndDrop();
  wireWhatIf();
  wireHeatMap();
  wireWorkspaceNav();
  wireGlobalSearch();
  wireLeaguesView();
  wireCalendarView();
  wireExplorerView();

  if ($('thesis-tabs')) $('thesis-tabs').onclick = e => {
    const b = e.target.closest('.tab-btn'); if (!b) return;
    document.querySelectorAll('#thesis-tabs .tab-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); activeThesisTab = b.dataset.tab; renderThesisTab();
  };
  if ($('analyst-scorers')) $('analyst-scorers').onclick = e => {
    const b = e.target.closest('button[data-player-name], button[data-player-id]');
    if (!b) return;
    if (b.dataset.playerId) { openPlayerInspector(+b.dataset.playerId); return; }
    const p = find(b.dataset.playerName);
    if (p?.id) openPlayerInspector(p.id);
  };

  loadPreset('home', 'Spain (National Team)');
  loadPreset('away', 'England (National Team)');
  predict();

  // Phase 2: Load full 71,161-player index in background without blocking initial boot
  setTimeout(() => {
    fetch('/api/players')
      .then(r => r.ok ? r.json() : null)
      .then(full => {
        if (Array.isArray(full) && full.length > players.length) {
          indexPlayers(full);
          if ($('dlg')?.open && ctx) fillDlg();
        }
      })
      .catch(() => {});
  }, 300);
}

async function loadSyncStatus() {
  const dot = $('header-sync-dot'), lbl = $('header-sync-label');
  try {
    const r = await fetch('/api/sync/status');
    if (!r.ok) {
      if (dot) dot.className = 'sync-dot';
      if (lbl) lbl.textContent = 'Ready';
      return;
    }
    const d = await r.json();
    syncStatusData = d;
    const isRunning = Boolean(d.running || d.syncing);
    const hasErr = Boolean(d.last_error);
    const enabled = d.enabled !== false;
    const sbOk = d.supabase_configured !== false;
    if (dot) {
      dot.className = 'sync-dot' + (isRunning ? ' busy' : (hasErr ? ' warn' : (!enabled ? ' off' : (!sbOk ? ' warn' : ''))));
    }
    if (lbl) {
      if (isRunning) lbl.textContent = 'Syncing';
      else if (hasErr) lbl.textContent = 'Check';
      else if (!enabled) lbl.textContent = 'Off';
      else if (!sbOk) lbl.textContent = 'Local';
      else lbl.textContent = 'Live';
    }
    if ($('sync-dlg')?.open) renderSyncModalBody();
  } catch (_) {
    if (dot) dot.className = 'sync-dot off';
    if (lbl) lbl.textContent = 'Offline';
  }
}

function renderSyncModalBody() {
  const body = $('sync-dlg-body');
  if (!body) return;
  const s = syncStatusData || {};
  const tm = thesisData;
  const m3 = tm?.model_3class_metrics;
  const m3t = tm?.model_3class_tuned_metrics;
  const mb = tm?.model_binary_metrics;
  const lastSync = s.last_sync || s.last_run || s.last_success || 'Pending initial cycle';
  const intervalHrs = s.interval_sec ? `${Math.round(s.interval_sec / 3600)}h` : '6h';
  const syncedMatches = s.matches_synced ?? s.last_result?.matches_upserted ?? recentData?.finished_matches?.length ?? '-';

  body.innerHTML = `
    <div class="sync-kv-grid num">
      <div class="sync-kv"><span>Auto-Sync Daemon</span><b>${s.running || s.syncing ? 'Running now' : (s.enabled === false ? 'Disabled' : 'Active (' + escRaw(intervalHrs) + ')')}</b></div>
      <div class="sync-kv"><span>Last Sync</span><b>${escRaw(String(lastSync).slice(0, 19).replace('T', ' '))}</b></div>
      <div class="sync-kv"><span>Database Mode</span><b>${s.supabase_configured === false ? 'Local Cache + Bundle' : 'Supabase Live Sync'}</b></div>
      <div class="sync-kv"><span>Recent Matches Tracked</span><b>${escRaw(String(syncedMatches))}</b></div>
    </div>
    ${s.last_error ? `<p class="state-banner error">Last sync warning: ${escRaw(s.last_error)}</p>` : ''}
    ${tm ? `
      <h4 style="margin-top:6px">Model Validation (Unseen Hold-Out ${escRaw(tm.methodology?.test_period || '2023-2026')})</h4>
      <div class="sync-kv-grid num">
        <div class="sync-kv"><span>3-Class Accuracy</span><b>${m3?.accuracy ?? '-'}%</b></div>
        <div class="sync-kv"><span>Tuned &tau;=0.27 Macro-F1</span><b>${m3t?.macro_f1 ?? '-'}</b></div>
        <div class="sync-kv"><span>Log Loss</span><b>${m3?.log_loss ?? '-'}</b></div>
        <div class="sync-kv"><span>Binary ROC-AUC</span><b>${mb?.roc_auc ?? '-'}</b></div>
      </div>` : '<p class="sub">Validation metrics loading...</p>'}`;
}

function wireSyncModal() {
  const pill = $('header-sync-pill'), dlg = $('sync-dlg');
  if (!pill || !dlg) return;
  pill.onclick = () => {
    loadSyncStatus();
    renderSyncModalBody();
    dlg.showModal();
  };
  if ($('sync-dlg-run')) {
    $('sync-dlg-run').onclick = async () => {
      const btn = $('sync-dlg-run');
      btn.disabled = true; btn.textContent = 'Syncing...';
      const ok = await syncMatches();
      await loadSyncStatus();
      renderSyncModalBody();
      if (ok) {
        btn.textContent = 'Synced';
        setTimeout(() => { btn.textContent = 'Sync finished matches'; }, 2000);
      } else {
        btn.textContent = 'Sync finished matches';
      }
      btn.disabled = false;
    };
  }
  if ($('sync-dlg-jump')) {
    $('sync-dlg-jump').onclick = () => {
      dlg.close();
      switchView('predictor');
      const results = $('analyst-results');
      if (results && results.hidden && last) results.hidden = false;
      const target = ($('thesis-sync-card') && !results?.hidden) ? $('thesis-sync-card') : ($('analyst-deck') || $('view-predictor'));
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
  }
}

function switchView(view) {
  activeView = view;
  ['predictor', 'leagues', 'calendar', 'explorer'].forEach(v => {
    const el = $('view-' + v);
    const tab = $('tab-' + v);
    if (el) el.hidden = v !== view;
    if (tab) {
      tab.classList.toggle('active', v === view);
      tab.setAttribute('aria-selected', v === view ? 'true' : 'false');
    }
  });
  const actBar = $('actionbar');
  if (actBar) {
    actBar.hidden = view !== 'predictor';
    document.body?.classList.toggle('no-actionbar', view !== 'predictor');
  } else {
    document.body?.classList.remove('no-actionbar');
  }
  if (view === 'leagues') ensureLeaguesLoaded();
  if (view === 'calendar') ensureCalendarLoaded();
  if (view === 'explorer') ensureExplorerSubLoaded(activeExSub);
}

function wireWorkspaceNav() {
  const nav = document.querySelector('.main-nav');
  if (nav) {
    nav.onclick = e => {
      const b = e.target.closest('.nav-tab');
      if (b?.dataset.view) switchView(b.dataset.view);
    };
    nav.onkeydown = e => {
      const tabs = [...nav.querySelectorAll('.nav-tab')];
      const i = tabs.indexOf(document.activeElement);
      if (i < 0) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); const n = tabs[(i + 1) % tabs.length]; n.focus(); switchView(n.dataset.view); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); const n = tabs[(i - 1 + tabs.length) % tabs.length]; n.focus(); switchView(n.dataset.view); }
    };
  }
  if ($('brand-home')) $('brand-home').onclick = e => { e.preventDefault(); switchView('predictor'); };
}

function wireGlobalSearch() {
  const inp = $('global-search'), list = $('global-search-results');
  const wrap = $('g-search-wrap'), toggle = $('mobile-search-toggle');
  if (!inp || !list) return;
  let gsTimer = null;
  const setSearchOpen = open => {
    if (wrap) wrap.classList.toggle('is-open', open);
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      document.querySelectorAll('.pk-list:not(.g-search-list)').forEach(l => l.hidden = true);
      setTimeout(() => inp.focus(), 10);
    } else {
      list.hidden = true;
    }
  };
  if (toggle) {
    toggle.onclick = () => {
      const next = wrap ? !wrap.classList.contains('is-open') : false;
      setSearchOpen(next);
    };
  }
  const run = async () => {
    const q = inp.value.trim();
    if (q.length < 2) { list.hidden = true; return; }
    try {
      const [plRes, clRes, ctRes] = await Promise.all([
        fetch(`/api/explore/players?q=${encodeURIComponent(q)}&status=all&limit=5`).then(r => r.ok ? r.json() : { players: [] }),
        fetch(`/api/explore/clubs?q=${encodeURIComponent(q)}&limit=4`).then(r => r.ok ? r.json() : { clubs: [] }),
        fetch(`/api/explore/countries?q=${encodeURIComponent(q)}&limit=3`).then(r => r.ok ? r.json() : { countries: [] }),
      ]);
      const ql = q.toLowerCase();
      const lgHits = (leaguesCache?.leagues || []).filter(l => `${l.name} ${l.country_name || ''} ${l.comp_id}`.toLowerCase().includes(ql)).slice(0, 3);
      const items = [
        ...lgHits.map(l => ({ kind: 'League', label: l.name, sub: `${l.region_group || ''} · ${l.comp_id}`, act: () => openLeagueStandings(l.comp_id) })),
        ...(clRes.clubs || []).map(c => ({ kind: 'Club', label: c.name, sub: `${c.comp_name || c.country_name || ''} · Rtg ${c.avg_rating != null ? Number(c.avg_rating).toFixed(1) : '-'}`, act: () => openClubInspector(c.name, c.club_id) })),
        ...(ctRes.countries || []).map(c => ({ kind: 'Country', label: c.name, sub: `${c.confederation || 'FIFA'} · ${c.total_players ?? 0} players`, act: () => openCountryInspector(c.name) })),
        ...(plRes.players || []).map(p => ({ kind: p.is_former ? 'Legend' : 'Player', label: p.name, sub: `${playerRole(p)} · ${p.is_former ? `Former: ${p.former_club || p.club || 'Retired'}` : (p.club || p.nat || '')} · Rtg ${p.rating != null ? Number(p.rating).toFixed(1) : '-'}`, act: () => openPlayerInspector(p.id) })),
      ];
      list._items = items;
      list.innerHTML = items.length
        ? items.map((it, idx) => `<li><button type="button" class="g-search-item" data-idx="${idx}"><span><b>${escRaw(it.label)}</b><br><small>${escRaw(it.sub)}</small></span><span class="g-kind">${escRaw(it.kind)}</span></button></li>`).join('')
        : '<li><small style="padding:8px 10px;display:block">No matching players, clubs, countries, or leagues</small></li>';
      list.hidden = false;
    } catch (e) { console.error(e); }
  };
  inp.addEventListener('input', () => { clearTimeout(gsTimer); gsTimer = setTimeout(run, 180); });
  inp.addEventListener('focus', () => {
    document.querySelectorAll('.pk-list:not(.g-search-list)').forEach(l => l.hidden = true);
    if (inp.value.trim().length >= 2) run();
  });
  inp.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      setSearchOpen(false);
      inp.blur();
    }
  });
  list.onclick = e => {
    const b = e.target.closest('button[data-idx]');
    if (!b) return;
    const item = list._items?.[+b.dataset.idx];
    inp.value = '';
    setSearchOpen(false);
    if (item?.act) item.act();
  };
}

function formatVerdictCopy(d) {
  const h = String(d?.home_name || 'Home').replaceAll(' (National Team)', '').trim();
  const a = String(d?.away_name || 'Away').replaceAll(' (National Team)', '').trim();
  const pr = d?.probabilities || { home: 0, draw: 0, away: 0 };
  const pHome = Number(pr.home || 0);
  const pDraw = Number(pr.draw || 0);
  const pAway = Number(pr.away || 0);
  const conf = d?.summary?.confidence || 'Medium';
  const leader = pHome >= pAway ? h : a;
  const edge = Math.max(pHome, pAway);

  if (d?.knockout) {
    const advHome = Number(d.knockout.advance_home || 0);
    const advAway = Number(d.knockout.advance_away || 0);
    const fav = advHome >= advAway ? h : a;
    const advPct = Math.max(advHome, advAway).toFixed(1);
    return {
      headline: `${fav} favoured to advance`,
      confHtml: `<b>${escRaw(conf)} confidence</b> &middot; ${escRaw(fav)} ${advPct}% to advance &middot; 90 min draw ${pDraw.toFixed(1)}%`
    };
  }

  const rawHead = String(d?.summary?.headline || d?.headline_tuned || '');
  const isDrawVerdict = d?.verdict_tuned === 'draw' || /draw risk flagged|draw most likely/i.test(rawHead);

  if (isDrawVerdict) {
    if (pDraw >= pHome && pDraw >= pAway) {
      return {
        headline: 'Even contest — Draw most likely',
        confHtml: `<b>${escRaw(conf)} confidence</b> &middot; Draw ${pDraw.toFixed(1)}% leads &middot; ${escRaw(leader)} ${edge.toFixed(1)}%`
      };
    }
    return {
      headline: 'Tight contest — Draw risk flagged',
      confHtml: `<b>${escRaw(conf)} confidence</b> &middot; Draw ${pDraw.toFixed(1)}% meets 27.0% draw-flag threshold &middot; ${escRaw(leader)} ${edge.toFixed(1)}% edge`
    };
  }

  const favIsAway = d?.verdict_tuned === 'away' || (d?.verdict_tuned !== 'home' && pAway > pHome);
  const fav = favIsAway ? a : h;
  const winPct = (favIsAway ? pAway : pHome).toFixed(1);
  return {
    headline: `${fav} favoured to win`,
    confHtml: `<b>${escRaw(conf)} confidence</b> &middot; ${escRaw(fav)} ${winPct}% win probability &middot; Draw ${pDraw.toFixed(1)}%`
  };
}

function invertPrediction(d) {
  if (!d) return null;
  const h = d.home_name, a = d.away_name;
  const hClean = String(h || '').replaceAll(' (National Team)', '').trim();
  const aClean = String(a || '').replaceAll(' (National Team)', '').trim();
  const [ga, gb] = (d.score_prediction?.most_likely_score || '0 - 0').split(' - ');
  const invScores = (d.score_prediction?.top_scores || []).map(s => ({
    ...s,
    score: `${s.team_b_goals} - ${s.team_a_goals}`,
    team_a_goals: s.team_b_goals,
    team_b_goals: s.team_a_goals
  }));
  const invGrid = (d.score_prediction?.score_grid || []).map((row, i) =>
    row.map((_, j) => d.score_prediction.score_grid[j]?.[i] ?? 0)
  );
  const invProb = { home: d.probabilities.away, draw: d.probabilities.draw, away: d.probabilities.home };
  const invXgHome = d.score_prediction.projected_away_xg;
  const invXgAway = d.score_prediction.projected_home_xg;
  const invWinnerKey = d.winner_key === 'home' ? 'away' : (d.winner_key === 'away' ? 'home' : 'draw');
  const invArgmax = d.verdict_argmax === 'home' ? 'away' : (d.verdict_argmax === 'away' ? 'home' : 'draw');
  const invTuned = d.verdict_tuned === 'home' ? 'away' : (d.verdict_tuned === 'away' ? 'home' : 'draw');
  const invHeadArgmax = invArgmax === 'draw' ? 'Even contest — Draw most likely' :
    (invArgmax === 'home' ? `${aClean} favoured to win` : `${hClean} favoured to win`);
  const invHeadTuned = invTuned === 'draw'
    ? (invProb.draw >= invProb.home && invProb.draw >= invProb.away
        ? 'Even contest — Draw most likely'
        : 'Tight contest — Draw risk flagged')
    : (invTuned === 'home' ? `${aClean} favoured to win` : `${hClean} favoured to win`);

  let invKo = null;
  if (d.knockout) {
    invKo = {
      ...d.knockout,
      advance_home: d.knockout.advance_away,
      advance_away: d.knockout.advance_home,
      shootout_home: 100 - d.knockout.shootout_home
    };
  }
  const invObj = {
    ...d,
    home_name: a, away_name: h,
    home_crest: d.away_crest || '', away_crest: d.home_crest || '',
    winner_key: invWinnerKey, verdict_argmax: invArgmax, verdict_tuned: invTuned,
    headline_argmax: invHeadArgmax, headline_tuned: invHeadTuned,
    probabilities: invProb, knockout: invKo,
    score_prediction: {
      ...d.score_prediction, projected_home_xg: invXgHome, projected_away_xg: invXgAway,
      most_likely_score: `${gb} - ${ga}`, top_scores: invScores, score_grid: invGrid
    },
    goalscorers: { home: d.goalscorers?.away || [], away: d.goalscorers?.home || [] },
    tactical_metrics: (d.tactical_metrics || []).map(m => ({ ...m, home: m.away, away: m.home })),
    summary: {
      ...d.summary,
      headline: invHeadTuned,
      points: [
        `Win probability: ${aClean} ${Number(invProb.home).toFixed(1)}% | Draw ${Number(invProb.draw).toFixed(1)}% | ${hClean} ${Number(invProb.away).toFixed(1)}%.`,
        `Most likely score ${gb} - ${ga} (xG ${Number(invXgHome).toFixed(2)} - ${Number(invXgAway).toFixed(2)}); over 2.5 goals ${Number(d.score_prediction.over_2_5_prob).toFixed(1)}%.`,
        `Biggest edge: favours ${invXgHome > invXgAway ? aClean : hClean}.`,
        `Top scoring threats: ${d.goalscorers?.away?.[0]?.name || aClean} (${aClean}), ${d.goalscorers?.home?.[0]?.name || hClean} (${hClean}).`
      ]
    }
  };
  invObj.summary.headline = formatVerdictCopy(invObj).headline;
  return invObj;
}

function swapSides() {
  const tmp = T.home;
  T.home = T.away;
  T.away = tmp;
  render();
  if (last) {
    last = invertPrediction(last);
    updateExecutiveView(last);
    updateAnalystView(last);
  }
  predict();
}

function buildPicker(t) {
  const sideLabel = t === 'home' ? 'Home' : 'Away';
  $('pick-' + t).innerHTML = `
    <div class="pk-head">
      <div class="pk-name" id="${t}-name"></div>
      <select class="field field-sm" id="${t}-f" aria-label="${sideLabel} formation">${FORMATIONS.map(f => `<option value="${f}">${f}</option>`).join('')}</select>
    </div>
    <div class="pk-search"><input class="field" id="${t}-q" placeholder="Change squad" autocomplete="off" aria-label="Change ${t} squad"><ul class="pk-list" id="${t}-list" hidden></ul></div>`;
  const q = $(t + '-q'), list = $(t + '-list');
  const show = () => {
    const s = q.value.trim().toLowerCase();
    const hits = flat.filter(x => !s || x.n.toLowerCase().includes(s) || x.c.toLowerCase().includes(s)).slice(0, 14);
    list.innerHTML = hits.map(x => `
      <li><button type="button" class="${x.isLegend ? 'is-legend' : ''}" data-n="${escRaw(x.n)}">
        <span>${esc(x.n)}</span>
        <span class="pk-meta-right">${x.isLegend ? '<span class="legend-tag">Legend</span>' : ''}<small>${escRaw(x.c)}</small></span>
      </button></li>`).join('') || '<li><small style="padding:8px 10px;display:block">No squad found</small></li>';
    list.hidden = false;
  };
  q.oninput = q.onfocus = show;
  list.onclick = async e => {
    const b = e.target.closest('button');
    if (b) {
      loadPreset(t, b.dataset.n);
      q.value = '';
      list.hidden = true;
      if (($('wi-date')?.value || '2026-11') !== '2026-11') await applySnapshot(t);
      predict();
    }
  };
  if ($(t + '-f')) {
    $(t + '-f').onchange = e => {
      rearrangeLineupForFormation(t, e.target.value, { useBench: false });
      render();
      predict();
    };
  }
  if ($(t + '-form')) {
    $(t + '-form').onchange = e => { T[t].form = +e.target.value; predict(); };
  }
}

function find(name) {
  const c = clean(name);
  return nameIdx.get(c) || players.find(p => clean(p.full_name).includes(c) || clean(p.name).includes(c)) || null;
}

function loadPreset(t, name) {
  const sq = presets[name]; if (!sq) return false;
  const s = (sq.starters || []).map(find);
  const f = FORMATIONS.includes(sq.formation) ? sq.formation : '4-3-3';
  T[t] = { name, formation: f, form: T[t].form, slots: Array.from({ length: 11 }, (_, i) => s[i] || null), subs: (sq.subs || []).map(find).filter(Boolean) };
  render();
  return true;
}

function fitScore(p, role) {
  if (!p) return -999;
  const nr = playerRole(p);
  const sameLine = roleToGroup(nr) === roleToGroup(role) ? 6 : 0;
  const exact = nr === role ? 2 : 0;
  const gkPenalty = (role === 'GK' && nr !== 'GK') || (role !== 'GK' && nr === 'GK') ? -25 : 0;
  return eff(p, role) + sameLine + exact + gkPenalty;
}

function rearrangeLineupForFormation(t, newFormation, opts = { useBench: false }) {
  T[t].formation = FORMATIONS.includes(newFormation) ? newFormation : '4-3-3';
  const useBench = Boolean(opts && opts.useBench);
  const roles = layout(T[t].formation).map(x => x.role);
  const seen = new Set();
  const rawPool = useBench ? [...T[t].slots, ...T[t].subs] : [...T[t].slots];
  const pool = rawPool.filter(p => {
    if (!p || seen.has(p.id)) return false;
    seen.add(p.id);
    return true;
  });
  if (!pool.length) return;

  const slots = Array(11).fill(null);
  const used = new Set();
  const byRtg = [...pool].sort((a, b) => (b.rating || 0) - (a.rating || 0));

  // Pass 1: exact natural-role match (highest rating first)
  roles.forEach((role, idx) => {
    const hit = byRtg.find(p => !used.has(p.id) && playerRole(p) === role);
    if (hit) { slots[idx] = hit; used.add(hit.id); }
  });

  // Pass 2: fill remaining slots with best fitScore (prefers same tactical line + highest rating)
  roles.forEach((role, idx) => {
    if (slots[idx]) return;
    let best = null, bestScore = -1e9;
    for (const p of byRtg) {
      if (used.has(p.id)) continue;
      const sc = fitScore(p, role) * 100 + (p.rating || 0);
      if (sc > bestScore) { bestScore = sc; best = p; }
    }
    if (best) { slots[idx] = best; used.add(best.id); }
  });

  // Pass 3: pairwise swap refinement across starters (and bench only when useBench is true)
  const bench = useBench ? byRtg.filter(p => !used.has(p.id)) : [];
  for (let pass = 0; pass < 4; pass++) {
    let improved = false;
    for (let i = 0; i < 11; i++) {
      for (let j = i + 1; j < 11; j++) {
        const pi = slots[i], pj = slots[j];
        if (!pi && !pj) continue;
        const cur = (pi ? fitScore(pi, roles[i]) : 0) + (pj ? fitScore(pj, roles[j]) : 0);
        const swp = (pj ? fitScore(pj, roles[i]) : 0) + (pi ? fitScore(pi, roles[j]) : 0);
        if (swp > cur + 0.01) {
          slots[i] = pj;
          slots[j] = pi;
          improved = true;
        }
      }
      if (useBench) {
        for (let k = 0; k < bench.length; k++) {
          const pi = slots[i], pk = bench[k];
          const cur = pi ? fitScore(pi, roles[i]) : -999;
          const swp = fitScore(pk, roles[i]);
          if (swp > cur + 0.01) {
            slots[i] = pk;
            if (pi) bench[k] = pi;
            else bench.splice(k, 1);
            improved = true;
          }
        }
      }
    }
    if (!improved) break;
  }

  T[t].slots = slots;
  if (useBench) {
    T[t].subs = bench.sort((a, b) => (b.rating || 0) - (a.rating || 0));
  }
}

function buildLineupFromRoster(roster, formation = '4-3-3') {
  const roles = layout(formation).map(x => x.role);
  const pool = roster.map(r => byId.get(r.id || r.player_id) || r).filter(Boolean);
  const slots = Array(11).fill(null);
  const used = new Set();
  roles.forEach((role, idx) => {
    const hit = pool.find(p => !used.has(p.id) && playerRole(p) === role);
    if (hit) { slots[idx] = hit; used.add(hit.id); }
  });
  roles.forEach((role, idx) => {
    if (!slots[idx]) {
      const hit = pool.find(p => !used.has(p.id) && roleToGroup(playerRole(p)) === roleToGroup(role));
      if (hit) { slots[idx] = hit; used.add(hit.id); }
    }
  });
  roles.forEach((_, idx) => {
    if (!slots[idx]) {
      const hit = pool.find(p => !used.has(p.id));
      if (hit) { slots[idx] = hit; used.add(hit.id); }
    }
  });
  const subs = pool.filter(p => !used.has(p.id)).slice(0, 7);
  return { slots, subs };
}

async function setPredictorTeam(side, teamName, detailObj = null) {
  const exact = presets[teamName] ? teamName : (presets[teamName + ' (National Team)'] ? teamName + ' (National Team)' : null);
  if (exact) {
    loadPreset(side, exact);
  } else if (detailObj?.preset?.starters?.length) {
    const pr = detailObj.preset;
    const f = FORMATIONS.includes(pr.formation) ? pr.formation : '4-3-3';
    T[side] = {
      name: teamName, formation: f, form: T[side].form,
      slots: Array.from({ length: 11 }, (_, i) => find(pr.starters[i]) || null),
      subs: (pr.subs || []).map(find).filter(Boolean)
    };
    render();
  } else if ((detailObj?.roster || detailObj?.top_players)?.length) {
    const list = detailObj.roster || detailObj.top_players;
    const { slots, subs } = buildLineupFromRoster(list, '4-3-3');
    T[side] = { name: teamName, formation: '4-3-3', form: T[side].form, slots, subs };
    render();
  } else {
    try {
      const d = await fetch(`/api/explore/club?name=${encodeURIComponent(teamName)}`).then(r => r.json());
      if (d?.status === 'success') return setPredictorTeam(side, d.club?.name || teamName, d);
    } catch (e) { console.error(e); }
    return false;
  }
  if (($('wi-date')?.value || '2026-11') !== '2026-11') await applySnapshot(side);
  return true;
}

async function applySnapshot(side = null, forceKeepLineup = false) {
  const dt = $('wi-date')?.value || '2026-11';
  const autoXi = forceKeepLineup ? false : ($('wi-hist-xi') ? $('wi-hist-xi').checked : true);
  const pickSlots = t => T[t].slots.map((p, i) => p ? { id: p.id, name: p.name, slot_pos: layout(T[t].formation)[i].role } : null);
  const body = {
    date: dt,
    home_name: T.home.name,
    away_name: T.away.name,
    auto_lineup: autoXi,
    home_formation: T.home.formation,
    away_formation: T.away.formation,
    home_starters: pickSlots('home'),
    home_subs: T.home.subs.map(p => ({ id: p.id, name: p.name, slot_pos: 'SUB' })),
    away_starters: pickSlots('away'),
    away_subs: T.away.subs.map(p => ({ id: p.id, name: p.name, slot_pos: 'SUB' }))
  };
  try {
    const res = await (await fetch('/api/snapshot', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    })).json();
    if (res.status !== 'success') return;
    const applySide = (t, form, slots, subs) => {
      if (form && FORMATIONS.includes(form)) T[t].formation = form;
      T[t].slots = Array.from({ length: 11 }, (_, i) => slots?.[i] || null);
      T[t].subs = Array.isArray(subs) ? subs.filter(Boolean) : [];
    };
    if (!side || side === 'home') applySide('home', res.home_formation, res.home_slots, res.home_subs);
    if (!side || side === 'away') applySide('away', res.away_formation, res.away_slots, res.away_subs);
    render();
  } catch (e) { console.error(e); }
}

function shortTeamLabel(t) {
  const raw = (T[t].name || t).replace(/ \(National Team\)/i, '').trim();
  const s = short(raw);
  return s.length > 14 ? raw.slice(0, 13) + '…' : (raw.length <= 14 ? raw : s);
}

function playerAt(ref) {
  if (!ref) return null;
  return ref.kind === 'slot' ? T[ref.t].slots[ref.i] : T[ref.t].subs[ref.i];
}

function updateSwapUI() {
  const btn = $('pitch-swap-mode-btn');
  if (btn) {
    btn.classList.toggle('active', pitchSwapMode);
    btn.setAttribute('aria-pressed', pitchSwapMode ? 'true' : 'false');
  }
  const banner = $('swap-banner'), txt = $('swap-banner-text');
  if (!banner || !txt) return;
  if (!swapArmed && !pitchSwapMode) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;
  if (swapArmed) {
    const p = playerAt(swapArmed);
    const pName = p ? short(p.name) : 'Empty slot';
    const teamNm = (T[swapArmed.t].name || swapArmed.t).replace(/ \(National Team\)/i, '');
    txt.textContent = `Tap another ${teamNm} starter or sub to swap with ${pName}.`;
  } else {
    txt.textContent = 'Quick Swap active: tap any starter or sub to select.';
  }
}

function cancelSwapMode() {
  pitchSwapMode = false;
  swapArmed = null;
  updateSwapUI();
  renderPitch();
  renderBench();
}

function handleSwapTap(t, kind, i) {
  if (!pitchSwapMode && !swapArmed) return false;
  if (!swapArmed) {
    swapArmed = { t, kind, i };
    updateSwapUI();
    renderPitch();
    renderBench();
    return true;
  }
  if (swapArmed.t === t && swapArmed.kind === kind && swapArmed.i === i) {
    swapArmed = null;
    updateSwapUI();
    renderPitch();
    renderBench();
    return true;
  }
  if (swapArmed.t !== t) {
    const teamNm = (T[swapArmed.t].name || swapArmed.t).replace(/ \(National Team\)/i, '');
    if ($('swap-banner-text')) {
      $('swap-banner-text').textContent = `Swap must stay within ${teamNm} — tap a ${teamNm} starter or sub.`;
    }
    return true;
  }

  const a = swapArmed;
  if (a.kind === 'slot' && kind === 'slot') {
    const tmp = T[t].slots[i];
    T[t].slots[i] = T[t].slots[a.i];
    T[t].slots[a.i] = tmp;
  } else if (a.kind === 'sub' && kind === 'sub') {
    const tmp = T[t].subs[i];
    T[t].subs[i] = T[t].subs[a.i];
    T[t].subs[a.i] = tmp;
  } else {
    const slotIdx = a.kind === 'slot' ? a.i : i;
    const subIdx = a.kind === 'sub' ? a.i : i;
    const slotP = T[t].slots[slotIdx];
    const subP = T[t].subs[subIdx];
    T[t].slots[slotIdx] = subP || null;
    if (slotP) T[t].subs[subIdx] = slotP;
    else T[t].subs.splice(subIdx, 1);
  }
  swapArmed = null;
  updateSwapUI();
  render();
  predict();
  return true;
}

function updatePitchToolbar() {
  const pvBoth = $('pv-both'), pvHome = $('pv-home'), pvAway = $('pv-away');
  if (pvBoth) pvBoth.textContent = 'Both 22';
  if (pvHome) pvHome.textContent = shortTeamLabel('home');
  if (pvAway) pvAway.textContent = shortTeamLabel('away');
  document.querySelectorAll('#pitch-view-tabs [data-pitch-view]').forEach(b => {
    b.classList.toggle('active', b.dataset.pitchView === pitchViewMode);
  });
  if ($('bench-home')) $('bench-home').classList.toggle('bench-focus-hidden', pitchViewMode === 'away');
  if ($('bench-away')) $('bench-away').classList.toggle('bench-focus-hidden', pitchViewMode === 'home');
  if ($('ptool-home')) $('ptool-home').classList.toggle('is-dimmed', pitchViewMode === 'away');
  if ($('ptool-away')) $('ptool-away').classList.toggle('is-dimmed', pitchViewMode === 'home');
  updateSwapUI();
}

function render() {
  TEAMS.forEach(t => {
    const nm = T[t].name.replace(' (National Team)', '') || 'Custom squad';
    const cUrl = crestUrlFor(T[t].name);
    const isLeg = /legends$/i.test(T[t].name);
    if ($(t + '-name')) {
      $(t + '-name').innerHTML = `${crestHtml(cUrl, nm, 'crest-sm')}<span>${escRaw(nm)}</span>${isLeg ? '<span class="legend-tag">Legend</span>' : ''}`;
    }
    if ($(t + '-f')) $(t + '-f').value = T[t].formation;
    if ($(t + '-form')) $(t + '-form').value = T[t].form;
    if ($('ptool-' + t + '-f')) $('ptool-' + t + '-f').value = T[t].formation;
  });
  if ($('whatif-summary')) $('whatif-summary').textContent = formatWhatIfSummary();
  updatePitchToolbar();
  renderPitch();
  renderBench();
  status();
}

function pitchSVG(v) {
  const g = `<g fill="none" stroke="rgba(255,252,245,0.44)" stroke-width=".38"><rect x="1" y="1" width="103" height="66"/><path d="M52.5 1V67"/><circle cx="52.5" cy="34" r="9.15"/><rect x="1" y="13.84" width="16.5" height="40.32"/><rect x="87.5" y="13.84" width="16.5" height="40.32"/><rect x="1" y="24.84" width="5.5" height="18.32"/><rect x="98.5" y="24.84" width="5.5" height="18.32"/><path d="M17.5 26.7A9.15 9.15 0 0 1 17.5 41.3M87.5 26.7A9.15 9.15 0 0 0 87.5 41.3"/><path d="M1 3A2 2 0 0 0 3 1M102 1A2 2 0 0 0 104 3M1 65A2 2 0 0 1 3 67M102 67A2 2 0 0 1 104 65"/></g><g fill="rgba(255,252,245,0.72)"><circle cx="52.5" cy="34" r=".55"/><circle cx="12" cy="34" r=".55"/><circle cx="93" cy="34" r=".55"/></g>`;
  return v ? `<svg viewBox="0 0 68 105" preserveAspectRatio="none" aria-hidden="true"><g transform="translate(0 105) rotate(-90)">${g}</g></svg>` : `<svg viewBox="0 0 105 68" preserveAspectRatio="none" aria-hidden="true">${g}</svg>`;
}

function renderPitch() {
  const v = matchMedia('(max-width:760px)').matches, el = $('pitch');
  const single = pitchViewMode === 'home' || pitchViewMode === 'away';
  el.classList.toggle('vert', v);
  el.classList.toggle('single-team', single);
  let h = pitchSVG(v);
  const visibleTeams = single ? [pitchViewMode] : TEAMS;
  visibleTeams.forEach(t => {
    const home = t === 'home';
    const wm = single
      ? 'left:50%;top:50%'
      : (v ? `left:50%;top:${home ? 78 : 22}%` : `left:${home ? 26 : 74}%;top:50%`);
    h += `<div class="wm" style="${wm}">${esc(short(T[t].name.replace(/ \(National Team\)/, '')) || '')}</div>`;
    layout(T[t].formation).forEach((pt, i) => {
      let left, top;
      if (single) {
        const norm = (pt.u - 0.04) / 0.40;
        left = v ? pt.v : (0.10 + norm * 0.80);
        top = v ? (0.88 - norm * 0.74) : pt.v;
      } else {
        const u = home ? pt.u : 1 - pt.u, w = home ? pt.v : 1 - pt.v;
        left = v ? w : u;
        top = v ? 1 - u : w;
      }
      const p = T[t].slots[i];
      const pen = p ? oopPenalty(p, pt.role) : 0;
      const e = p ? eff(p, pt.role) : 0;
      const natRole = p ? playerRole(p) : pt.role;
      const cardCls = pen >= 4 ? 'oop' : (pen >= 1 ? 'oop-warn' : '');
      const posLabel = pen > 0 ? `${natRole}→${pt.role} -${pen}` : pt.role;
      const label = p ? `${p.name}, ${natRole} in ${pt.role}, rating ${Math.round(e)}` : `Empty ${pt.role} spot`;
      const tip = pen > 0
        ? `${p.name} (natural ${natRole}) playing ${pt.role}: rating ${Number(p.rating).toFixed(1)} → ${Math.round(e)} (-${pen})`
        : label;
      const fd = p && p.form_delta !== undefined && p.form_delta !== null ? Number(p.form_delta) : 0;
      const deltaBadge = Math.abs(fd) >= 0.05
        ? `<span class="fut-delta ${fd > 0 ? 'pos' : 'neg'}">${fd > 0 ? '+' : ''}${fd.toFixed(1)}</span>`
        : '';
      const armedCls = (swapArmed && swapArmed.kind === 'slot' && swapArmed.t === t && swapArmed.i === i) ? ' swap-selected' : '';
      if (p) {
        const imgUrl = p.image_url || byId.get(p.id)?.image_url || '';
        const tierCls = ratingTier(e);
        h += `<button draggable="true" type="button" class="tok ${t} ${tierCls} ${cardCls}${armedCls}" style="left:${left * 100}%;top:${top * 100}%" data-t="${t}" data-i="${i}" aria-label="${escRaw(label)}" title="${escRaw(tip)}">
          <span class="tok-top">
            <span class="tok-av">${avatarHtml(imgUrl, p.name, 'tok-pic', e)}</span>
            ${deltaBadge}
            <span class="tok-rtg">${Math.round(e)}</span>
          </span>
          <span class="tok-name">${esc(short(p.name))}</span>
          <span class="tok-role">${escRaw(posLabel)}</span>
        </button>`;
      } else {
        h += `<button draggable="true" type="button" class="tok ${t} empty${armedCls}" style="left:${left * 100}%;top:${top * 100}%" data-t="${t}" data-i="${i}" aria-label="${escRaw(label)}" title="${escRaw(tip)}">
          <span class="fut-plus">+</span>
          <span class="tok-name">${escRaw(pt.role)}</span>
        </button>`;
      }
    });
  });
  el.innerHTML = h;
}

function renderBench() {
  TEAMS.forEach(t => {
    const teamName = (T[t].name || 'Team').replace(' (National Team)', '');
    $('bench-' + t).innerHTML = `<div class="bench"><div class="bench-head"><b>${esc(teamName)} bench (${T[t].subs.length})</b><button type="button" class="add">+ Add sub</button></div><div class="bench-list">` +
      T[t].subs.map((p, i) => {
        const imgUrl = p.image_url || byId.get(p.id)?.image_url || '';
        const r = playerRole(p);
        const rtg = p.rating != null ? Number(p.rating).toFixed(1) : '-';
        const isArmed = swapArmed && swapArmed.kind === 'sub' && swapArmed.t === t && swapArmed.i === i;
        return `<span class="bn ${ratingTier(p.rating)}${isArmed ? ' swap-selected' : ''}"><button type="button" class="bn-card-btn" draggable="true" data-i="${i}">${avatarHtml(imgUrl, p.name, 'av-sm', p.rating)}<span class="bn-rtg">${rtg}</span><span class="pos-mini">${escRaw(r)}</span><span class="bn-name">${esc(short(p.name))}</span></button><button type="button" data-rm="${i}" aria-label="Remove ${escRaw(p.name)}">&times;</button></span>`;
      }).join('') +
      `</div></div>`;
  });
}

function status() {
  const n = t => T[t].slots.filter(Boolean).length, nm = t => T[t].name.replace(' (National Team)', '') || t;
  const ok = n('home') && n('away');
  $('status').textContent = ok ? `${nm('home')} ${n('home')}/11 · ${nm('away')} ${n('away')}/11 starters` : 'Pick at least one starter for each team';
  $('predict-btn').disabled = busy || !ok;
}

function renderDlgSummary(currentP, kind, role) {
  const sumWrap = $('dlg-player-summary');
  const sumBody = $('dlg-sum-body');
  if (!sumWrap || !sumBody) return;
  if (!currentP) {
    sumWrap.hidden = true;
    sumBody.innerHTML = '';
    return;
  }
  const p = byId.get(currentP.id) ? { ...byId.get(currentP.id), ...currentP } : currentP;
  const nr = playerRole(p);
  const pen = kind === 'slot' ? oopPenalty(p, role) : 0;
  const e = kind === 'slot' ? eff(p, role) : p.rating;
  const imgUrl = p.image_url || '';
  const clubText = p.is_former ? (p.former_club || p.club || 'Retired') : (p.club || 'Free Agent');
  const legTag = p.is_former ? ' <span class="legend-tag">Legend</span>' : '';
  const fitText = kind === 'slot'
    ? (pen > 0 ? `Eff ${Number(e).toFixed(1)} (-${pen} OOP)` : `Natural ${role}`)
    : 'Bench sub';
  const rtgDisp = p.rating != null ? Number(p.rating).toFixed(1) : '-';

  sumBody.innerHTML = `
    <div class="dlg-sum-top">
      <div class="dlg-sum-ident">
        ${avatarHtml(imgUrl, p.name, 'av-md', e)}
        <div class="dlg-sum-meta">
          <div class="dlg-sum-name">${escRaw(p.full_name || p.name)}${legTag}</div>
          <div class="dlg-sum-sub">${escRaw(nr)} · ${escRaw(clubText)} · ${escRaw(p.nat || '-')}</div>
        </div>
      </div>
      <div class="dlg-sum-rtg">
        <b>${rtgDisp}</b>
        <small class="${pen > 0 ? 'warn' : 'ok'}">${escRaw(fitText)}</small>
      </div>
    </div>
    <div class="dlg-sum-stats" id="dlg-sum-stats">
      <div class="dlg-sum-stat"><span>Age</span><b>${p.age ?? '-'}</b></div>
      <div class="dlg-sum-stat"><span>Value</span><b>${fmtVal(p.val ?? p.market_val)}</b></div>
      <div class="dlg-sum-stat"><span>Career G/A</span><b>${p.total_goals ?? p.goals ?? '-'} / ${p.total_assists ?? p.assists ?? '-'}</b></div>
      <div class="dlg-sum-stat"><span>Foot</span><b>${escRaw(p.foot || '-')}</b></div>
    </div>`;
  sumWrap.hidden = false;
}

function openDlg(t, kind, i) {
  ctx = { t, kind, i };
  const role = kind === 'slot' ? layout(T[t].formation)[i].role : 'SUB';
  ctx.role = role;
  $('dlg-title').textContent = kind === 'slot' ? `${T[t].name.replace(' (National Team)', '') || t}: choose ${role}` : 'Choose a substitute';
  $('dlg-q').value = '';
  dlgUserPickedFilter = false;
  dlgFilterMode = role === 'SUB' ? 'all' : 'exact';
  dlgSourceMode = 'squad';

  document.querySelectorAll('#dlg-source-tabs .seg-btn').forEach(x => {
    x.classList.toggle('active', x.dataset.source === dlgSourceMode);
  });

  const bExact = $('dlg-f-exact'), bLine = $('dlg-f-line'), bAll = $('dlg-f-all');
  if (bExact && bLine && bAll) {
    if (role === 'SUB') {
      bExact.hidden = true;
      bLine.hidden = true;
      bAll.classList.add('active');
    } else {
      bExact.hidden = false;
      bLine.hidden = false;
      bExact.textContent = `Exact slot (${role})`;
      bLine.textContent = `Line (${roleToGroup(role)})`;
      bExact.classList.toggle('active', dlgFilterMode === 'exact');
      bLine.classList.toggle('active', dlgFilterMode === 'line');
      bAll.classList.toggle('active', dlgFilterMode === 'all');
    }
  }
  if ($('dlg-legends')) $('dlg-legends').checked = /legends$/i.test(T[t].name || '');

  const currentP = kind === 'slot' ? T[t].slots[i] : (i >= 0 ? T[t].subs[i] : null);
  $('dlg-clear').hidden = kind === 'slot' ? !T[t].slots[i] : i < 0;
  if ($('dlg-inspect')) $('dlg-inspect').hidden = !currentP?.id;
  if ($('dlg-quick-swap')) $('dlg-quick-swap').hidden = !currentP;

  const reqId = ++dlgSummaryReqId;
  renderDlgSummary(currentP, kind, role);
  if (currentP?.id) {
    fetch(`/api/explore/player/${currentP.id}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (reqId !== dlgSummaryReqId || !$('dlg')?.open || !ctx) return;
        const det = d?.player || d;
        if (!det || typeof det !== 'object') return;
        const statsEl = $('dlg-sum-stats');
        if (!statsEl) return;
        const g = det.total_goals ?? det.career_goals ?? det.goals ?? currentP.total_goals ?? currentP.goals;
        const a = det.total_assists ?? det.career_assists ?? det.assists ?? currentP.total_assists ?? currentP.assists;
        const g90 = det.goals_per_90 ?? det.g90;
        const gaStr = `${g ?? '-'} / ${a ?? '-'}${g90 !== undefined && g90 !== null ? ` (${Number(g90).toFixed(2)}/90)` : ''}`;
        statsEl.innerHTML = `
          <div class="dlg-sum-stat"><span>Age</span><b>${det.age ?? currentP.age ?? '-'}</b></div>
          <div class="dlg-sum-stat"><span>Value</span><b>${fmtVal(det.val ?? det.market_val ?? det.market_value ?? currentP.val ?? currentP.market_val)}</b></div>
          <div class="dlg-sum-stat"><span>Career G/A</span><b>${escRaw(gaStr)}</b></div>
          <div class="dlg-sum-stat"><span>Foot</span><b>${escRaw(det.foot || det.preferred_foot || currentP.foot || '-')}</b></div>`;
      })
      .catch(() => {});
  }

  fillDlg(); $('dlg').showModal(); $('dlg-q').focus();
}

function gatherSquadCandidates(t, kind, idx, activeId) {
  const out = [];
  const seen = new Set();
  if (activeId) seen.add(activeId);

  T[t].subs.forEach((p, si) => {
    if (!p || (kind === 'sub' && si === idx) || seen.has(p.id)) return;
    seen.add(p.id);
    out.push({ p, srcBadge: { cls: 'bench', text: 'On bench' }, order: 0 });
  });

  const roles = layout(T[t].formation).map(x => x.role);
  T[t].slots.forEach((p, si) => {
    if (!p || (kind === 'slot' && si === idx) || seen.has(p.id)) return;
    seen.add(p.id);
    out.push({ p, srcBadge: { cls: 'pitch', text: `On pitch · ${roles[si] || ''}` }, order: 1 });
  });

  const teamName = T[t].name || '';
  const preset = presets[teamName];
  if (preset) {
    [...(preset.starters || []), ...(preset.subs || [])].forEach(nm => {
      const p = find(nm);
      if (p && !seen.has(p.id)) {
        seen.add(p.id);
        out.push({ p, srcBadge: { cls: 'squad', text: 'Squad' }, order: 2 });
      }
    });
  }

  const isNat = / \(National Team\)$/i.test(teamName);
  const isLeg = /legends$/i.test(teamName);
  const baseClean = clean(teamName.replace(/ \(National Team\)$/i, '').replace(/\s+legends$/i, ''));
  if (baseClean) {
    for (const p of byRating) {
      if (seen.has(p.id)) continue;
      let match = false;
      if (isNat) match = clean(p.nat) === baseClean;
      else if (isLeg) match = Boolean(p.is_former) && (clean(p.former_club || p.club) === baseClean || clean(p.nat) === baseClean);
      else match = !p.is_former && clean(p.club) === baseClean;
      if (match) {
        seen.add(p.id);
        out.push({ p, srcBadge: { cls: 'squad', text: 'Squad' }, order: 2 });
      }
    }
  }
  return { items: out, seen };
}

function renderDlgCandidateItem(p, role, srcBadge) {
  const nr = playerRole(p);
  const pen = oopPenalty(p, role);
  const e = eff(p, role);
  const penCls = pen >= 4 ? 'pen-severe' : 'pen-warn';
  const legTag = p.is_former ? ' <span class="legend-tag">Legend</span>' : '';
  const badgeHtml = srcBadge ? ` <span class="src-badge src-badge-${escRaw(srcBadge.cls)}">${escRaw(srcBadge.text)}</span>` : '';
  const subMeta = p.is_former
    ? `Former: ${escRaw(p.former_club || p.club || 'Retired')} (Last: ${escRaw(p.last_season || '-')}) · ${escRaw(p.nat)}`
    : `${escRaw(p.club)} · ${escRaw(p.nat)}`;
  const rtgStr = p.rating != null ? Number(p.rating).toFixed(1) : '-';
  return `<li><button type="button" data-id="${p.id}">
    <span class="pos">${escRaw(nr)}</span>
    ${avatarHtml(p.image_url, p.name, 'av-sm', p.rating)}
    <span>${escRaw(p.full_name || p.name)}${legTag}${badgeHtml}<br><small>${subMeta}</small></span>
    <b class="r">${rtgStr}${pen > 0 ? ` <small class="${penCls}">&rarr; ${Number(e).toFixed(1)}</small>` : ''}</b>
  </button></li>`;
}

function fillDlg() {
  const s = $('dlg-q').value.trim().toLowerCase(), { t, kind, i, role } = ctx;
  const showLegends = $('dlg-legends')?.checked ?? false;
  const currentP = kind === 'slot' ? T[t].slots[i] : (i >= 0 ? T[t].subs[i] : null);

  const matchesSearchAndRole = p => {
    if (!showLegends && p.is_former) return false;
    if (role !== 'SUB') {
      if (dlgFilterMode === 'exact' && playerRole(p) !== role) return false;
      if (dlgFilterMode === 'line' && roleToGroup(playerRole(p)) !== roleToGroup(role)) return false;
    }
    if (s.length >= 1) {
      const hay = `${p.name} ${p.full_name} ${p.club} ${p.nat} ${playerRole(p)} ${p.pos}`.toLowerCase();
      if (!hay.includes(s)) return false;
    }
    return true;
  };

  const sortRanked = (arr) => [...arr].sort((a, b) => {
    const pa = oopPenalty(a.p, role), pb = oopPenalty(b.p, role);
    if (pa !== pb) return pa - pb;
    const ea = eff(a.p, role), eb = eff(b.p, role);
    if (eb !== ea) return eb - ea;
    return (b.p.rating || 0) - (a.p.rating || 0);
  });

  if (dlgSourceMode === 'squad') {
    const { items, seen } = gatherSquadCandidates(t, kind, i, currentP?.id);
    const squadHits = items.filter(it => matchesSearchAndRole(it.p)).sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      const pa = oopPenalty(a.p, role), pb = oopPenalty(b.p, role);
      if (pa !== pb) return pa - pb;
      return (eff(b.p, role) || 0) - (eff(a.p, role) || 0);
    });

    let html = squadHits.slice(0, 45).map(it => renderDlgCandidateItem(it.p, role, it.srcBadge)).join('');

    if (s.length >= 2) {
      const globalHits = sortRanked(
        byRating
          .filter(p => !seen.has(p.id) && matchesSearchAndRole(p))
          .slice(0, 120)
          .map(p => ({ p, srcBadge: { cls: 'global', text: 'Global' } }))
      ).slice(0, 25);
      if (globalHits.length) {
        html += `<li class="dlg-sec-hdr">Global 71k matches</li>` + globalHits.map(it => renderDlgCandidateItem(it.p, role, it.srcBadge)).join('');
      }
    }

    if (!html) {
      const exactHint = (role !== 'SUB' && dlgFilterMode === 'exact')
        ? `No exact ${role} candidates in this squad. Try switching to Line (${roleToGroup(role)}), All, or Global 71k database`
        : 'No matching squad candidates found. Try switching to Global 71k database or clearing your search';
      html = `<li><small style="padding:10px 6px;display:block;color:var(--mute)">${escRaw(exactHint)}</small></li>`;
    } else if (role !== 'SUB' && dlgFilterMode === 'exact' && squadHits.length === 0) {
      html = `<li><small style="padding:6px;display:block;color:var(--mute)">No exact ${escRaw(role)} in squad — showing Global 71k matches. Switch to Line or All to see other squad players</small></li>` + html;
    }

    $('dlg-list').innerHTML = html;
    return;
  }

  // Global 71k Database mode
  const pool = byRating.filter(p => (!currentP || p.id !== currentP.id) && matchesSearchAndRole(p));
  const ranked = sortRanked(pool.slice(0, 250).map(p => ({ p, srcBadge: null }))).slice(0, 35);

  $('dlg-list').innerHTML = ranked.map(it => renderDlgCandidateItem(it.p, role, null)).join('')
    || `<li><small style="padding:10px 6px;display:block;color:var(--mute)">${role !== 'SUB' && dlgFilterMode === 'exact' ? `No exact ${escRaw(role)} players found. Try switching to Line or All, or enable Show legends` : 'No matching players found. Try switching to Line or All, or enable Show legends'}</small></li>`;
}

async function assign(p) {
  const { t, kind, i } = ctx;
  const prevSlotIdx = p ? T[t].slots.findIndex(x => x && x.id === p.id) : -1;
  const prevSubIdx = p ? T[t].subs.findIndex(x => x && x.id === p.id) : -1;

  if (kind === 'slot') {
    const oldPlayer = T[t].slots[i];
    T[t].slots[i] = p;
    if (p) {
      if (prevSlotIdx >= 0 && prevSlotIdx !== i) {
        T[t].slots[prevSlotIdx] = oldPlayer;
      } else if (prevSubIdx >= 0) {
        if (oldPlayer) T[t].subs[prevSubIdx] = oldPlayer;
        else T[t].subs.splice(prevSubIdx, 1);
      }
    }
  } else {
    const oldPlayer = i >= 0 ? T[t].subs[i] : null;
    if (!p) {
      if (i >= 0) T[t].subs.splice(i, 1);
    } else {
      if (i < 0) T[t].subs.push(p);
      else T[t].subs[i] = p;

      if (prevSlotIdx >= 0) {
        T[t].slots[prevSlotIdx] = oldPlayer;
      } else if (prevSubIdx >= 0 && prevSubIdx !== i) {
        if (oldPlayer) T[t].subs[prevSubIdx] = oldPlayer;
        else T[t].subs.splice(prevSubIdx, 1);
      }
    }
  }

  $('dlg').close();
  render();
  if (p && ($('wi-date')?.value || '2026-11') !== '2026-11') await applySnapshot(t, true);
  predict();
}

async function predict() {
  const pick = t => T[t].slots.map((p, i) => p && { id: p.id, name: p.name, slot_pos: layout(T[t].formation)[i].role }).filter(Boolean);
  const body = {
    home_name: T.home.name || 'Team A', away_name: T.away.name || 'Team B',
    home_starters: pick('home'), away_starters: pick('away'),
    home_subs: T.home.subs.map(p => ({ id: p.id, name: p.name, slot_pos: 'SUB' })),
    away_subs: T.away.subs.map(p => ({ id: p.id, name: p.name, slot_pos: 'SUB' })),
    home_form_pts: T.home.form, away_form_pts: T.away.form, knockout: $('knockout').checked,
    neutral: $('neutral') ? $('neutral').checked : true,
    threshold_mode: 'tuned',
    league_tier_factor: +($('wi-tier')?.value || 0.95),
    report_date: $('wi-date')?.value || '2026-11'
  };
  let err = '';
  busy = true; $('predict-btn').textContent = 'Predicting...'; status();
  try {
    const d = await (await fetch('/api/predict', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json();
    if (d.status !== 'success') throw new Error(d.message);
    last = d;
    updateExecutiveView(d);
    updateAnalystView(d);
  } catch (e) { err = e.message; console.error(e); }
  busy = false; $('predict-btn').textContent = 'Predict match'; status();
  if (err) $('status').textContent = `Could not predict: ${err}`;
}

function updateExecutiveView(d) {
  const h = esc(d.home_name), a = esc(d.away_name), pr = d.probabilities, sp = d.score_prediction;
  const hCrest = crestUrlFor(d.home_name, d.home_crest || '');
  const aCrest = crestUrlFor(d.away_name, d.away_crest || '');
  const seg = (c, v) => {
    const n = Number(v || 0);
    return `<div class="${c}" style="flex:${n}">${n >= 8 ? n.toFixed(1) + '%' : ''}</div>`;
  };
  const vc = formatVerdictCopy(d);

  const elMatchup = $('exec-matchup');
  if (elMatchup) {
    const rd = d.inputs?.report_date;
    const rdTag = rd && !rd.startsWith('2026-11') ? ` &nbsp;&middot;&nbsp; As of ${escRaw(rd.slice(0, 7))}` : '';
    elMatchup.innerHTML = `<span class="matchup-team">${crestHtml(hCrest, h, 'crest-sm')}<span class="c-home">${h}</span> (Home)</span> <span>vs</span> <span class="matchup-team">${crestHtml(aCrest, a, 'crest-sm')}<span class="c-away">${a}</span> (Away)</span>${rdTag}`;
  }

  $('exec-headline').textContent = vc.headline;
  $('exec-conf').innerHTML = vc.confHtml;
  $('exec-strip').innerHTML = `${seg('s-home', pr.home)}${seg('s-draw', pr.draw)}${seg('s-away', pr.away)}`;
  $('exec-legend').innerHTML = `<span><b class="c-home">${h}</b> win</span><span>Draw</span><span><b class="c-away">${a}</b> win</span>`;

  if (d.knockout) {
    $('exec-ko-container').innerHTML = `
      <div class="ko"><p>Knockout match: if level after 90' (${Number(d.knockout.shootout_prob).toFixed(1)}%), penalties decide advancement</p>
      <div class="strip thin">${seg('s-home', d.knockout.advance_home)}${seg('s-away', d.knockout.advance_away)}</div>
      <div class="legend"><span><b>${h}</b> ${Number(d.knockout.advance_home).toFixed(1)}%</span><span><b>${a}</b> ${Number(d.knockout.advance_away).toFixed(1)}%</span></div></div>`;
  } else {
    $('exec-ko-container').innerHTML = '';
  }

  const [ga, gb] = sp.most_likely_score.split(' - ');
  if ($('score-crest-h')) $('score-crest-h').innerHTML = crestHtml(hCrest, h, 'crest-md');
  if ($('score-crest-a')) $('score-crest-a').innerHTML = crestHtml(aCrest, a, 'crest-md');
  $('score-h').textContent = h;
  $('score-val').textContent = `${ga} - ${gb}`;
  $('score-a').textContent = a;
  $('exec-xg').textContent = `Expected goals: ${Number(sp.projected_home_xg).toFixed(2)} to ${Number(sp.projected_away_xg).toFixed(2)} · Over 2.5: ${Number(sp.over_2_5_prob).toFixed(1)}%`;
  $('exec-points').innerHTML = d.summary.points.map(p => `<li>${esc(p)}</li>`).join('');
  $('exp').disabled = false;
}

function renderTacticalRadar(metrics, homeName, awayName) {
  const wrap = $('analyst-radar');
  if (!wrap) return;
  const pickAxes = [
    { key: 'Starting XI', match: l => l.includes('Starting XI') },
    { key: 'Attack', match: l => l.includes('Attack line') },
    { key: 'Midfield', match: l => l.includes('Midfield') },
    { key: 'Defence', match: l => l.includes('Defence line') },
    { key: 'GK', match: l => l.includes('Goalkeeper') },
    { key: 'Bench', match: l => l.includes('Bench depth') },
  ];
  const axes = pickAxes.map(ax => {
    const m = (metrics || []).find(x => ax.match(x.label));
    return { label: ax.key, home: m ? Number(m.home) : 75, away: m ? Number(m.away) : 75 };
  });
  const cx = 150, cy = 140, R = 95, minV = 45, maxV = 98;
  const norm = v => Math.max(0.08, Math.min(1, (v - minV) / (maxV - minV)));
  const ptAt = (idx, frac) => {
    const ang = -Math.PI / 2 + (idx / axes.length) * Math.PI * 2;
    return [cx + Math.cos(ang) * R * frac, cy + Math.sin(ang) * R * frac];
  };
  const rings = [0.33, 0.66, 1].map(f => {
    const pts = axes.map((_, i) => ptAt(i, f).map(n => n.toFixed(1)).join(',')).join(' ');
    return `<polygon points="${pts}" fill="none" stroke="rgba(31,27,22,0.12)" stroke-width="1"/>`;
  }).join('');
  const spokes = axes.map((ax, i) => {
    const [x2, y2] = ptAt(i, 1);
    const [lx, ly] = ptAt(i, 1.2);
    return `<line x1="${cx}" y1="${cy}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="rgba(31,27,22,0.12)" stroke-width="1"/><text x="${lx.toFixed(1)}" y="${(ly + 4).toFixed(1)}" text-anchor="middle" font-size="11" font-weight="500" fill="#5e554a">${ax.label}</text>`;
  }).join('');
  const polyH = axes.map((ax, i) => ptAt(i, norm(ax.home)).map(n => n.toFixed(1)).join(',')).join(' ');
  const polyA = axes.map((ax, i) => ptAt(i, norm(ax.away)).map(n => n.toFixed(1)).join(',')).join(' ');

  wrap.innerHTML = `
    <svg class="radar-svg" viewBox="0 0 300 280" role="img" aria-label="Tactical radar chart">
      ${rings}${spokes}
      <polygon points="${polyH}" fill="rgba(184,67,46,0.18)" stroke="#b8432e" stroke-width="2"/>
      <polygon points="${polyA}" fill="rgba(29,78,137,0.18)" stroke="#1d4e89" stroke-width="2"/>
    </svg>
    <div class="radar-legend">
      <span><i style="background:#b8432e"></i>${homeName}</span>
      <span><i style="background:#1d4e89"></i>${awayName}</span>
    </div>`;
}

function updateAnalystView(d) {
  const h = esc(d.home_name), a = esc(d.away_name), sp = d.score_prediction;
  const top = Math.max(...sp.score_grid.flat());

  if ($('heat-x-title')) $('heat-x-title').innerHTML = `Away goals (&rarr;): ${a} (0 to 5)`;
  if ($('heat-y-title')) $('heat-y-title').innerHTML = `Home goals (&darr;): ${h} (0 to 5)`;

  let homeSum = 0, drawSum = 0, awaySum = 0;
  let heat = `<span class="ax">H\\A</span>${[0, 1, 2, 3, 4, 5].map(n => `<span class="ax ax-x">${n}</span>`).join('')}`;
  sp.score_grid.forEach((row, i) => {
    heat += `<span class="ax ax-y">${i}</span>` + row.map((v, j) => {
      if (i > j) homeSum += v;
      else if (i < j) awaySum += v;
      else drawSum += v;
      const zoneCls = i > j ? 'cell-home' : (i < j ? 'cell-away' : 'cell-draw');
      const heatCls = v === top ? 'heat-top1 top1' : (v >= 10 ? 'heat-high' : (v >= 4 ? 'heat-mod' : 'heat-low'));
      return `<span data-ga="${i}" data-gb="${j}" data-p="${v}" class="${zoneCls} ${heatCls}">${Number(v).toFixed(1)}</span>`;
    }).join('');
  });
  $('analyst-heat').innerHTML = heat;

  if ($('heat-sums')) {
    $('heat-sums').innerHTML = `
      <span class="heat-sum-pill home">Home win cells <b>${homeSum.toFixed(1)}%</b></span>
      <span class="heat-sum-pill draw">Draw diagonal <b>${drawSum.toFixed(1)}%</b></span>
      <span class="heat-sum-pill away">Away win cells <b>${awaySum.toFixed(1)}%</b></span>`;
  }

  const max = Math.max(...d.goalscorers.home.concat(d.goalscorers.away).map(p => p.anytime_prob), 1);
  const scorers = (side, name, c) => `<div><h4>${name}</h4>${d.goalscorers[side].map(p => {
    const pObj = p.id ? byId.get(p.id) : find(p.name);
    const imgUrl = p.image_url || pObj?.image_url || '';
    const pidAttr = p.id || pObj?.id ? `data-player-id="${p.id || pObj.id}"` : '';
    const roleBadge = p.pos_role || p.role || pObj?.role || p.slot_pos || p.pos || '';
    return `<div class="sr">${avatarHtml(imgUrl, p.name, 'av-xs')}<span class="sc-name-wrap"><button type="button" class="sc-link" ${pidAttr} data-player-name="${escRaw(p.name)}">${escRaw(p.name)}</button>${roleBadge ? `<span class="pos-mini">${escRaw(roleBadge)}</span>` : ''}</span><b>${Number(p.anytime_prob).toFixed(1)}%</b><i style="--w:${p.anytime_prob / max * 100}%;--c:var(${c})"></i></div>`;
  }).join('')}</div>`;
  $('analyst-scorers').innerHTML = `${scorers('home', h, '--home')}${scorers('away', a, '--away')}`;

  renderTacticalRadar(d.tactical_metrics, h, a);
  const metrics = d.tactical_metrics.map(m => {
    const len = Math.min(100, Math.abs(m.home - m.away) / Math.max(m.home, m.away, 1) * 500).toFixed(0) + '%';
    return `<div class="mr"><span>${esc(m.label)}</span><b>${Number(m.home).toFixed(1)}</b><div class="bar" style="--l:${m.home > m.away ? len : '0%'};--r:${m.away > m.home ? len : '0%'}"></div><b>${Number(m.away).toFixed(1)}</b></div>`;
  }).join('');
  $('analyst-metrics-bars').innerHTML = metrics;
  $('analyst-results').hidden = false;
}

async function exportXlsx() {
  if (!last) return;
  const payload = {
    ...last,
    preset_meta: {
      home_name: T.home.name,
      away_name: T.away.name,
      home_formation: T.home.formation,
      away_formation: T.away.formation,
      home_form_pts: T.home.form,
      away_form_pts: T.away.form,
      knockout: !!$('knockout')?.checked,
      neutral: $('neutral') ? $('neutral').checked : true,
      league_tier_factor: +($('wi-tier')?.value || 0.95),
      report_date: $('wi-date')?.value || '2026-11',
      home_slots: T.home.slots.map(p => p ? { id: p.id, name: p.name } : null),
      away_slots: T.away.slots.map(p => p ? { id: p.id, name: p.name } : null),
      home_subs: T.home.subs.map(p => ({ id: p.id, name: p.name })),
      away_subs: T.away.subs.map(p => ({ id: p.id, name: p.name })),
    }
  };
  const r = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const url = URL.createObjectURL(await r.blob());
  const fn = `PitchPulse AI - ${last.home_name} v ${last.away_name}.xlsx`.replaceAll(' (National Team)', '');
  Object.assign(document.createElement('a'), { href: url, download: fn }).click();
  URL.revokeObjectURL(url);
}

function resolveImportedPlayer(entry) {
  if (!entry) return null;
  if (entry.id != null && byId.has(entry.id)) return byId.get(entry.id);
  const nm = String(entry.name || '').trim().toLowerCase();
  const cl = String(entry.club || '').trim().toLowerCase();
  if (!nm) return null;
  if (cl) {
    const exactClub = players.find(p => p.name.toLowerCase() === nm && (p.club || '').toLowerCase() === cl);
    if (exactClub) return exactClub;
  }
  return players.find(p => p.name.toLowerCase() === nm) || null;
}

async function importXlsx(e) {
  const file = e.target.files?.[0];
  e.target.value = '';
  if (!file) return;
  const btn = $('imp-xlsx');
  if (btn) { btn.disabled = true; btn.textContent = 'Importing...'; }
  try {
    const fd = new FormData();
    fd.append('file', file);
    const d = await (await fetch('/api/import-xlsx', { method: 'POST', body: fd })).json();
    if (d.status !== 'success' || !d.preset) throw new Error(d.message || 'Invalid Excel preset');
    const p = d.preset;

    // Load base team names (helps populate fallback if a slot is null)
    const resolveTeamName = rawName => {
      const s = String(rawName || '').trim();
      if (flat.some(x => x.n === s)) return s;
      const nt = `${s} (National Team)`;
      if (flat.some(x => x.n === nt)) return nt;
      return s;
    };

    const hName = resolveTeamName(p.home_name);
    const aName = resolveTeamName(p.away_name);
    if (flat.some(x => x.n === hName)) loadPreset('home', hName); else T.home.name = hName;
    if (flat.some(x => x.n === aName)) loadPreset('away', aName); else T.away.name = aName;

    if (p.home_formation && FORMATIONS.includes(p.home_formation)) T.home.formation = p.home_formation;
    if (p.away_formation && FORMATIONS.includes(p.away_formation)) T.away.formation = p.away_formation;
    if ($('home-f')) $('home-f').value = T.home.formation;
    if ($('away-f')) $('away-f').value = T.away.formation;

    if (Array.isArray(p.home_slots) && p.home_slots.length) {
      T.home.slots = Array.from({ length: 11 }, (_, i) => resolveImportedPlayer(p.home_slots[i]));
    }
    if (Array.isArray(p.away_slots) && p.away_slots.length) {
      T.away.slots = Array.from({ length: 11 }, (_, i) => resolveImportedPlayer(p.away_slots[i]));
    }
    if (Array.isArray(p.home_subs)) T.home.subs = p.home_subs.map(resolveImportedPlayer).filter(Boolean);
    if (Array.isArray(p.away_subs)) T.away.subs = p.away_subs.map(resolveImportedPlayer).filter(Boolean);

    if (p.home_form_pts != null) T.home.form = +p.home_form_pts;
    if (p.away_form_pts != null) T.away.form = +p.away_form_pts;
    if ($('home-form')) $('home-form').value = String(T.home.form);
    if ($('away-form')) $('away-form').value = String(T.away.form);
    if ($('wi-hf')) { $('wi-hf').value = T.home.form; $('wi-hf-val').textContent = T.home.form.toFixed(1); }
    if ($('wi-af')) { $('wi-af').value = T.away.form; $('wi-af-val').textContent = T.away.form.toFixed(1); }

    if ($('knockout')) $('knockout').checked = !!p.knockout;
    if ($('neutral') && p.neutral !== undefined) $('neutral').checked = !!p.neutral;
    if (p.league_tier_factor != null && $('wi-tier')) {
      $('wi-tier').value = String(p.league_tier_factor);
      $('wi-tier-val').textContent = (+p.league_tier_factor).toFixed(2);
    }
    if (p.report_date && $('wi-date')) $('wi-date').value = String(p.report_date).slice(0, 7);

    render();
    if (($('wi-date')?.value || '2026-11') !== '2026-11') await applySnapshot();
    await predict();
  } catch (err) {
    $('status').textContent = `Could not import Excel: ${err.message}`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Import'; }
  }
}

async function loadThesisAndRecent() {
  try {
    const [tm, rec] = await Promise.all([
      fetch('/api/thesis-metrics').then(r => r.ok ? r.json() : null),
      fetch('/api/matches/recent').then(r => r.ok ? r.json() : null)
    ]);
    if (tm && $('thesis-summary')) {
      const m3 = tm.model_3class_metrics, mb = tm.model_binary_metrics;
      const tunedF1 = tm.model_3class_tuned_metrics?.macro_f1;
      const f1Txt = tunedF1 !== undefined ? ` | Tuned τ=0.27 Macro-F1 ${tunedF1}` : '';
      $('thesis-summary').textContent = `Hold-out (${tm.methodology.test_period}, ${tm.methodology.dataset_size_total_matches.toLocaleString()} matches): 3-Class Acc ${m3.accuracy}%${f1Txt} | Log Loss ${m3.log_loss} | Binary ROC-AUC ${mb.roc_auc}`;
    }
    thesisData = tm; recentData = rec; renderThesisTab();
    if ($('sync-dlg')?.open) renderSyncModalBody();
  } catch (e) { console.error(e); }
}

async function syncMatches() {
  const b = $('sync-btn');
  if (b) { b.disabled = true; b.textContent = 'Syncing...'; }
  let ok = false;
  try {
    const r = await (await fetch('/api/sync', { method: 'POST' })).json();
    if (r.status === 'skipped' && $('recent-matches-box')) {
      $('recent-matches-box').innerHTML = `<small>${escRaw(r.message)}</small>`;
    } else if (r.status === 'error' && $('recent-matches-box')) {
      $('recent-matches-box').innerHTML = `<small>${escRaw(r.message || 'Sync error')}</small>`;
    } else {
      ok = r.status === 'success' || r.status === 'ok';
      activeThesisTab = 'finished';
      document.querySelectorAll('#thesis-tabs .tab-btn').forEach(x => x.classList.toggle('active', x.dataset.tab === 'finished'));
      await loadThesisAndRecent();
    }
    await loadSyncStatus();
  } catch (e) { console.error(e); }
  if (b) {
    b.disabled = false;
    if (ok) {
      b.textContent = 'Synced';
      setTimeout(() => { b.textContent = 'Sync finished matches'; }, 2000);
    } else {
      b.textContent = 'Sync finished matches';
    }
  }
  return ok;
}

// ---- INTERACTIVE ENHANCEMENTS ----
let dragSrc = null, activeThesisTab = 'finished', thesisData = null, recentData = null, wiTimer = null;

function enableDragAndDrop() {
  const pitch = $('pitch');
  if (pitch) {
    pitch.addEventListener('dragstart', e => {
      const b = e.target.closest('.tok'); if (!b) return;
      dragSrc = { t: b.dataset.t, kind: 'slot', i: +b.dataset.i };
      b.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    pitch.addEventListener('dragend', () => {
      document.querySelectorAll('.tok.dragging,.tok.drag-over').forEach(el => el.classList.remove('dragging', 'drag-over'));
    });
    pitch.addEventListener('dragover', e => {
      const b = e.target.closest('.tok');
      if (!b || !dragSrc || b.dataset.t !== dragSrc.t) return;
      e.preventDefault();
      b.classList.add('drag-over');
    });
    pitch.addEventListener('dragleave', e => { const b = e.target.closest('.tok'); if (b) b.classList.remove('drag-over'); });
    pitch.addEventListener('drop', e => {
      const b = e.target.closest('.tok');
      if (!b || !dragSrc || b.dataset.t !== dragSrc.t) return;
      e.preventDefault();
      const t = b.dataset.t, dstI = +b.dataset.i;
      if (dragSrc.kind === 'slot') {
        const tmp = T[t].slots[dstI];
        T[t].slots[dstI] = T[t].slots[dragSrc.i];
        T[t].slots[dragSrc.i] = tmp;
      } else if (dragSrc.kind === 'sub') {
        const subP = T[t].subs[dragSrc.i], slotP = T[t].slots[dstI];
        T[t].slots[dstI] = subP;
        if (slotP) T[t].subs[dragSrc.i] = slotP;
        else T[t].subs.splice(dragSrc.i, 1);
      }
      dragSrc = null; render(); predict();
    });
  }
  TEAMS.forEach(t => {
    const bench = $('bench-' + t);
    if (!bench) return;
    bench.addEventListener('dragstart', e => {
      const b = e.target.closest('button[data-i]'); if (!b) return;
      dragSrc = { t, kind: 'sub', i: +b.dataset.i };
      e.dataTransfer.effectAllowed = 'move';
    });
  });
}

function formatWhatIfSummary() {
  const hf = (+($('wi-hf')?.value ?? T.home.form ?? 2.0)).toFixed(1);
  const af = (+($('wi-af')?.value ?? T.away.form ?? 2.0)).toFixed(1);
  const tr = (+($('wi-tier')?.value ?? 0.95)).toFixed(2);
  const dt = $('wi-date')?.value || '2026-11';
  return `Form ${hf} vs ${af} · Tier ${tr} · ${dt}`;
}

function wireWhatIf() {
  const hf = $('wi-hf'), af = $('wi-af'), tr = $('wi-tier'), dt = $('wi-date'), hx = $('wi-hist-xi');
  const toggleBtn = $('whatif-toggle'), bar = $('whatif-bar'), summary = $('whatif-summary');
  const updateSummary = () => {
    if (!summary) return;
    summary.textContent = formatWhatIfSummary();
  };
  if (toggleBtn && bar) {
    toggleBtn.onclick = () => {
      const open = bar.classList.toggle('is-open');
      toggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    };
  }
  if (hf && af && tr) {
    const sync = () => {
      T.home.form = +hf.value; $('wi-hf-val').textContent = (+hf.value).toFixed(1);
      T.away.form = +af.value; $('wi-af-val').textContent = (+af.value).toFixed(1);
      $('wi-tier-val').textContent = (+tr.value).toFixed(2);
      if ($('home-form')) $('home-form').value = hf.value;
      if ($('away-form')) $('away-form').value = af.value;
      updateSummary();
      clearTimeout(wiTimer);
      wiTimer = setTimeout(predict, 180);
    };
    [hf, af, tr].forEach(el => el.addEventListener('input', sync));
  }
  if (dt) {
    dt.addEventListener('change', async () => {
      if (!dt.value) dt.value = '2026-11';
      updateSummary();
      await applySnapshot();
      predict();
    });
  }
  if (hx) {
    hx.addEventListener('change', async () => {
      if (($('wi-date')?.value || '2026-11') !== '2026-11') {
        await applySnapshot();
        predict();
      }
    });
  }
  updateSummary();
}

function wireHeatMap() {
  const heat = $('analyst-heat'), ro = $('heat-readout');
  if (!heat || !ro) return;
  const inspect = e => {
    const cell = e.target.closest('span[data-ga]'); if (!cell || !last) return;
    heat.querySelectorAll('.active-cell').forEach(x => x.classList.remove('active-cell'));
    cell.classList.add('active-cell');
    const ga = +cell.dataset.ga, gb = +cell.dataset.gb, p = +cell.dataset.p;
    const outcome = ga > gb ? `${esc(last.home_name)} win` : ga < gb ? `${esc(last.away_name)} win` : 'Draw';
    const btts = ga > 0 && gb > 0 ? 'Yes' : 'No';
    ro.innerHTML = `<span><b>${esc(last.home_name)} ${ga} - ${gb} ${esc(last.away_name)}</b> (${outcome})</span><span>Probability: <b>${p.toFixed(1)}%</b> · Total Goals: <b>${ga + gb}</b> · BTTS: <b>${btts}</b></span>`;
  };
  heat.addEventListener('mouseover', inspect);
  heat.addEventListener('click', inspect);
}

function renderThesisTab() {
  const box = $('recent-matches-box'); if (!box) return;
  if (activeThesisTab === 'finished') {
    const fm = recentData?.finished_matches || [];
    box.innerHTML = fm.length
      ? fm.slice(0, 6).map(m => `<div class="recent-row"><b>${esc(m.home_team)} ${m.home_goals} - ${m.away_goals} ${esc(m.away_team)}</b><small class="sub">${escRaw(m.league)} · ${escRaw((m.match_date || '').slice(0, 10))}</small></div>`).join('')
      : '<small>No finished matches synced yet. Click Sync Finished Matches to fetch latest fixtures.</small>';
  } else if (activeThesisTab === 'preds') {
    const pr = recentData?.recent_predictions || [];
    box.innerHTML = pr.length
      ? pr.slice(0, 6).map(p => `<div class="recent-row"><b>${esc(p.home_team)} v ${esc(p.away_team)}</b><span>${escRaw(p.predicted_score)} <small class="sub">(${p.p_home}% / ${p.p_draw}% / ${p.p_away}%)</small></span></div>`).join('')
      : '<small>No predictions logged in Supabase yet.</small>';
  } else if (activeThesisTab === 'features') {
    const fi = thesisData?.feature_importance_ranking || [];
    const maxFi = Math.max(...fi.map(x => x.importance_mean), 0.01);
    box.innerHTML = fi.slice(0, 8).map(f => `<div class="fi-row"><span>${escRaw(f.label)}</span><b>${(f.importance_mean * 100).toFixed(2)}%</b><div class="fi-bar"><i style="width:${Math.max(2, f.importance_mean / maxFi * 100)}%"></i></div></div>`).join('');
  }
}

// =========================================================================
// TAB 2: LEAGUE STANDINGS & STATS
// =========================================================================
const CONFED_TO_CONTINENT = {
  UEFA: 'Europe',
  AFC: 'Asia & Oceania',
  CAF: 'Africa',
  CONMEBOL: 'South America',
  CONCACAF: 'North America',
  FIFA: 'World / International',
};

function leagueContinent(l) {
  return CONFED_TO_CONTINENT[String(l?.confederation || '').toUpperCase()] || 'World / International';
}

function leagueCountry(l) {
  return (l?.country_name && String(l.country_name).trim()) || 'International / Continental';
}

async function ensureLeaguesLoaded(preferredCompId = null, preferredSeason = null) {
  const st = $('lg-status');
  if (!leaguesCache) {
    if (st) { st.textContent = 'Loading competitions...'; st.classList.remove('error'); st.hidden = false; }
    try {
      leaguesCache = await fetch('/api/explore/leagues').then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
      populateClubLeagueFilter(leaguesCache.leagues || []);
      populateContinentSelect();
    } catch (e) {
      if (st) { st.textContent = `Could not load leagues: ${e.message}`; st.classList.add('error'); st.hidden = false; }
      return;
    }
  }
  if (preferredCompId) {
    const lg = (leaguesCache.leagues || []).find(l => l.comp_id === preferredCompId);
    if (lg) {
      activeContinent = leagueContinent(lg);
      activeCountry = leagueCountry(lg);
    } else {
      activeContinent = 'All';
      activeCountry = 'All';
    }
    populateContinentSelect();
    populateCountrySelect();
    populateLeagueSelect(preferredCompId);
  } else if (!$('lg-select').options.length) {
    populateContinentSelect();
    populateCountrySelect();
    populateLeagueSelect('GB1');
  }
  await loadSelectedLeague(preferredSeason);
}

function populateContinentSelect() {
  const sel = $('lg-continent'); if (!sel || !leaguesCache) return;
  const order = ['Europe', 'Asia & Oceania', 'South America', 'North America', 'Africa', 'World / International'];
  const present = new Set((leaguesCache.leagues || []).map(leagueContinent));
  const continents = order.filter(c => present.has(c)).concat([...present].filter(c => !order.includes(c)).sort());
  sel.innerHTML = '<option value="All">All Continents</option>' +
    continents.map(c => `<option value="${escRaw(c)}">${escRaw(c)}</option>`).join('');
  sel.value = continents.includes(activeContinent) ? activeContinent : 'All';
  activeContinent = sel.value;
}

function populateCountrySelect() {
  const sel = $('lg-country'); if (!sel || !leaguesCache) return;
  const inCont = (leaguesCache.leagues || []).filter(l => activeContinent === 'All' || leagueContinent(l) === activeContinent);
  const countries = Array.from(new Set(inCont.map(leagueCountry))).sort((a, b) => {
    if (a === 'International / Continental') return 1;
    if (b === 'International / Continental') return -1;
    return a.localeCompare(b);
  });
  sel.innerHTML = '<option value="All">All Countries</option>' +
    countries.map(c => `<option value="${escRaw(c)}">${escRaw(c)}</option>`).join('');
  sel.value = countries.includes(activeCountry) ? activeCountry : 'All';
  activeCountry = sel.value;
}

function populateLeagueSelect(preferId = null) {
  const sel = $('lg-select'); if (!sel || !leaguesCache) return;
  const prev = preferId || sel.value;
  const list = (leaguesCache.leagues || []).filter(l =>
    (activeContinent === 'All' || leagueContinent(l) === activeContinent) &&
    (activeCountry === 'All' || leagueCountry(l) === activeCountry)
  );
  sel.innerHTML = list.map(l => `<option value="${escRaw(l.comp_id)}">${escRaw(l.name)}${l.country_name ? ` (${escRaw(l.country_name)})` : ''}</option>`).join('');
  if (list.some(l => l.comp_id === prev)) sel.value = prev;
  else if (list.length) sel.value = list[0].comp_id;
}

function populateClubLeagueFilter(leagues) {
  const sel = $('ex-c-comp'); if (!sel) return;
  sel.innerHTML = '<option value="">All competitions</option>' +
    leagues.map(l => `<option value="${escRaw(l.comp_id)}">${escRaw(l.name)}</option>`).join('');
}

async function loadSelectedLeague(preferSeason = null) {
  const compId = $('lg-select')?.value; if (!compId) return;
  const seasonSel = $('lg-season');
  const season = preferSeason || seasonSel?.value || '';
  const st = $('lg-status');
  if (st) { st.textContent = 'Loading standings and statistics...'; st.classList.remove('error'); st.hidden = false; }
  try {
    const q = `comp_id=${encodeURIComponent(compId)}${season ? `&season=${encodeURIComponent(season)}` : ''}`;
    const d = await fetch(`/api/explore/league?${q}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    if (d.status && d.status !== 'success') throw new Error(d.message || 'No league data');
    lastLeagueData = d;
    const seasons = d.available_seasons || [2026, 2025, 2024, 2023, 2022, 2021, 2020];
    seasonSel.innerHTML = seasons.map(s => `<option value="${s}">${s}</option>`).join('');
    seasonSel.value = String(d.season ?? seasons[0]);
    if (st) st.hidden = true;
    renderLeagueView(d);
  } catch (e) {
    if (st) { st.textContent = `Could not load league standings: ${e.message}`; st.classList.add('error'); st.hidden = false; }
    $('lg-standings-body').innerHTML = '';
  }
}

function renderFormBadges(formStr) {
  const arr = Array.isArray(formStr) ? formStr : String(formStr || '').split('').filter(c => 'WDL'.includes(c));
  if (!arr.length) return '<span class="sub">-</span>';
  return `<span class="form-strip">${arr.slice(-5).map(c => `<span class="wdl ${c}">${c}</span>`).join('')}</span>`;
}

function standingsZoneClass(rank, totalRows, isNt) {
  if (isNt || totalRows < 8) return '';
  if (rank <= 4) return 'zone-ucl';
  if (rank <= 6) return 'zone-uel';
  if (totalRows >= 12 && rank > totalRows - 3) return 'zone-rel';
  return '';
}

function renderLeagueView(d) {
  const sm = d.summary || {};
  const isNt = d.league?.type === 'national_team_competition';
  $('lg-table-title').textContent = `${d.league?.name || d.league?.comp_id || 'League'} (${d.season || ''})`;
  $('lg-kpis').innerHTML = [
    ['Matches played', fmtNum(sm.total_matches)],
    ['Goals / match', sm.avg_goals_per_match != null ? Number(sm.avg_goals_per_match).toFixed(2) : '-'],
    ['Home win %', sm.home_win_pct !== undefined ? `${Number(sm.home_win_pct).toFixed(1)}%` : '-'],
    ['Draw %', sm.draw_pct !== undefined ? `${Number(sm.draw_pct).toFixed(1)}%` : '-'],
    ['Away win %', sm.away_win_pct !== undefined ? `${Number(sm.away_win_pct).toFixed(1)}%` : '-'],
    ['Clean sheet %', sm.clean_sheet_pct !== undefined ? `${Number(sm.clean_sheet_pct).toFixed(1)}%` : '-'],
  ].map(([k, v]) => `<div class="kpi-card"><span class="kpi-label">${k}</span><span class="kpi-val">${v}</span></div>`).join('');

  const rows = d.standings || [];
  $('lg-standings-body').innerHTML = rows.length ? rows.map(r => {
    const zCls = standingsZoneClass(Number(r.rank), rows.length, isNt);
    const cUrl = r.crest_url || (isNt ? crestUrlFor(r.club_name) : clubCrestUrl(r));
    const ppgStr = r.ppg != null ? Number(r.ppg).toFixed(1) : '-';
    const avgRtgStr = r.avg_rating != null ? Number(r.avg_rating).toFixed(1) : '-';
    return `
    <tr class="clickable ${zCls}" data-club-name="${escRaw(r.club_name)}" data-club-id="${r.club_id ?? ''}">
      <td class="num"><b>${r.rank ?? '-'}</b></td>
      <td><button type="button" class="club-cell-btn">${crestHtml(cUrl, r.club_name, 'crest-xs')}<span>${escRaw(r.club_name)}</span></button></td>
      <td class="num">${r.played ?? 0}</td>
      <td class="num">${r.won ?? 0}</td>
      <td class="num">${r.drawn ?? 0}</td>
      <td class="num">${r.lost ?? 0}</td>
      <td class="num">${r.gf ?? 0}</td>
      <td class="num">${r.ga ?? 0}</td>
      <td class="num">${r.gd > 0 ? `+${r.gd}` : (r.gd ?? 0)}</td>
      <td class="num"><b>${r.pts ?? 0}</b></td>
      <td class="num">${ppgStr}</td>
      <td>${renderFormBadges(r.form_last5)}</td>
      <td class="num">${avgRtgStr}</td>
      <td class="num">${fmtVal(r.squad_val)}</td>
    </tr>`;
  }).join('') : '<tr><td colspan="14" class="empty-msg">No standings computed for this competition and season</td></tr>';

  renderLeagueLeaders();

  const fx = d.recent_matches || [];
  $('lg-fixtures-list').innerHTML = fx.length ? fx.map(m => {
    const hn = m.home_club_name || m.home_team || 'Home', an = m.away_club_name || m.away_team || 'Away';
    return `<div class="fixture-item">
      <div>
        <div class="fixture-teams">${escRaw(hn)} ${m.home_goals ?? '-'} - ${m.away_goals ?? '-'} ${escRaw(an)}</div>
        <div class="fixture-meta">${escRaw((m.date || m.match_date || '').slice(0, 10))}</div>
      </div>
      <button type="button" class="btn ghost btn-sm" data-sim-home="${escRaw(hn)}" data-sim-away="${escRaw(an)}">Simulate</button>
    </div>`;
  }).join('') : '<p class="empty-msg">No recent fixtures recorded for this season</p>';
}

function renderLeagueLeaders() {
  const box = $('lg-leaders-list'); if (!box || !lastLeagueData) return;
  const list = lastLeagueData[activeLeaderKey] || [];
  const label = activeLeaderKey === 'top_scorers' ? 'G' : (activeLeaderKey === 'top_assisters' ? 'A' : 'Rtg');
  const valOf = p => activeLeaderKey === 'top_scorers' ? (p.goals ?? p.total_goals ?? 0)
    : (activeLeaderKey === 'top_assisters' ? (p.assists ?? p.total_assists ?? 0) : (p.rating != null ? Number(p.rating).toFixed(1) : '-'));
  box.innerHTML = list.length ? list.slice(0, 12).map((p, idx) => {
    const pid = p.player_id ?? p.id;
    const imgUrl = p.image_url || byId.get(pid)?.image_url || '';
    const role = p.role || p.pos || '';
    return `
    <button type="button" class="leader-row" data-player-id="${pid}">
      <span class="leader-rank">${idx + 1}</span>
      ${avatarHtml(imgUrl, p.name, 'av-sm')}
      <span><b>${escRaw(p.name)}</b><span class="leader-meta">${escRaw(p.club_name || p.club || '')} · ${escRaw(role)}</span></span>
      <span class="leader-stat num">${valOf(p)} <small>${label}</small></span>
    </button>`;
  }).join('') : '<p class="empty-msg">No player stats available for this season</p>';
}

async function simulateFixture(homeName, awayName) {
  switchView('predictor');
  const [okH, okA] = await Promise.all([setPredictorTeam('home', homeName), setPredictorTeam('away', awayName)]);
  if (okH && okA) {
    if ($('neutral')) $('neutral').checked = false;
    predict();
  }
}

function openLeagueStandings(compId, season = null) {
  switchView('leagues');
  ensureLeaguesLoaded(compId, season);
}

function wireLeaguesView() {
  if ($('lg-continent')) $('lg-continent').onchange = () => {
    activeContinent = $('lg-continent').value || 'All';
    activeCountry = 'All';
    populateCountrySelect();
    populateLeagueSelect();
    loadSelectedLeague();
  };
  if ($('lg-country')) $('lg-country').onchange = () => {
    activeCountry = $('lg-country').value || 'All';
    populateLeagueSelect();
    loadSelectedLeague();
  };
  if ($('lg-select')) $('lg-select').onchange = () => loadSelectedLeague();
  if ($('lg-season')) $('lg-season').onchange = () => loadSelectedLeague($('lg-season').value);
  if ($('lg-standings-body')) $('lg-standings-body').onclick = e => {
    const tr = e.target.closest('tr[data-club-name]');
    if (tr) openClubInspector(tr.dataset.clubName, tr.dataset.clubId ? +tr.dataset.clubId : null);
  };
  if ($('lg-leader-tabs')) $('lg-leader-tabs').onclick = e => {
    const b = e.target.closest('button[data-leader]'); if (!b) return;
    activeLeaderKey = b.dataset.leader;
    document.querySelectorAll('#lg-leader-tabs .tab-btn').forEach(x => x.classList.toggle('active', x === b));
    renderLeagueLeaders();
  };
  if ($('lg-leaders-list')) $('lg-leaders-list').onclick = e => {
    const b = e.target.closest('button[data-player-id]');
    if (b?.dataset.playerId) openPlayerInspector(+b.dataset.playerId);
  };
  if ($('lg-fixtures-list')) $('lg-fixtures-list').onclick = e => {
    const b = e.target.closest('button[data-sim-home]');
    if (b) simulateFixture(b.dataset.simHome, b.dataset.simAway);
  };
}

// =========================================================================
// TAB 3: SCOUTING & INSPECTOR
// =========================================================================
function switchExplorerSub(sub) {
  activeExSub = sub;
  document.querySelectorAll('#ex-subtabs .seg-btn').forEach(b => {
    const on = b.dataset.sub === sub;
    b.classList.toggle('active', on);
    b.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  ['players', 'clubs', 'countries'].forEach(s => {
    const pane = $('ex-pane-' + s);
    if (pane) pane.hidden = s !== sub;
  });
  ensureExplorerSubLoaded(sub);
}

function ensureExplorerSubLoaded(sub) {
  if (sub === 'players' && !$('ex-p-list').children.length) searchExplorerPlayers();
  if (sub === 'clubs') {
    if (!leaguesCache) fetch('/api/explore/leagues').then(r => r.ok ? r.json() : null).then(d => { if (d) { leaguesCache = d; populateClubLeagueFilter(d.leagues || []); } }).catch(() => {});
    if (!$('ex-c-list').children.length) searchExplorerClubs();
  }
  if (sub === 'countries' && !$('ex-n-list').children.length) searchExplorerCountries();
}

async function searchExplorerPlayers() {
  const list = $('ex-p-list'); if (!list) return;
  const q = $('ex-p-q')?.value.trim() || '';
  const pos = document.querySelector('#ex-p-pos .filter-pill.active')?.dataset.pos || '';
  const statusFilter = document.querySelector('#ex-p-status .filter-pill.active')?.dataset.status || 'active';
  const sort = $('ex-p-sort')?.value || 'rating';
  const ctxBtn = $('ex-p-clear-ctx');
  if (ctxBtn) {
    if (exPlayersCtx.club || exPlayersCtx.nat) {
      ctxBtn.textContent = `Filter: ${exPlayersCtx.club || exPlayersCtx.nat} ×`;
      ctxBtn.hidden = false;
    } else ctxBtn.hidden = true;
  }
  list.innerHTML = '<p class="empty-msg">Loading players...</p>';
  try {
    const params = new URLSearchParams({ q, pos, status: statusFilter, sort, limit: '40' });
    if (exPlayersCtx.club) params.set('club', exPlayersCtx.club);
    if (exPlayersCtx.nat) params.set('nat', exPlayersCtx.nat);
    const d = await fetch(`/api/explore/players?${params}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    const rows = d.players || [];
    list.innerHTML = rows.length ? rows.map(p => {
      const role = playerRole(p);
      const legBadge = p.is_former ? '<span class="legend-tag">Legend</span>' : '';
      const clubLine = p.is_former
        ? `Former: ${escRaw(p.former_club || p.club || 'Retired')} (Last: ${escRaw(p.last_season || '-')})`
        : escRaw(p.club || 'Free Agent');
      const rtgStr = p.rating != null ? Number(p.rating).toFixed(1) : '-';
      return `
      <button type="button" class="entity-card ${currentPlayerDetail?.player?.id === p.id ? 'active' : ''}" data-pid="${p.id}">
        ${avatarHtml(p.image_url, p.name, 'av-md', p.rating)}
        <div>
          <div class="entity-title"><span>${escRaw(p.name)}</span>${legBadge}</div>
          <div class="entity-sub"><span class="pos-mini">${escRaw(role)}</span><span>${clubLine}${p.nat ? ` · ${escRaw(p.nat)}` : ''}</span></div>
        </div>
        <div class="entity-score">${rtgStr}<small>${fmtVal(p.val)}</small></div>
      </button>`;
    }).join('') : '<p class="empty-msg">No players matched your filter</p>';
  } catch (e) {
    list.innerHTML = `<p class="state-banner error">Could not load players: ${escRaw(e.message)}</p>`;
  }
}

async function openPlayerInspector(playerId) {
  if (!playerId) return;
  switchView('explorer');
  switchExplorerSub('players');
  const panel = $('ex-p-detail');
  panel.innerHTML = '<p class="empty-msg">Loading player profile and snapshot timeline...</p>';
  try {
    const d = await fetch(`/api/explore/player/${playerId}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    if (d.status && d.status !== 'success') throw new Error(d.message || 'Player not found');
    currentPlayerDetail = d;
    document.querySelectorAll('#ex-p-list .entity-card').forEach(c => c.classList.toggle('active', +c.dataset.pid === playerId));
    renderPlayerDetail(d);
  } catch (e) {
    panel.innerHTML = `<p class="state-banner error">Could not load player profile: ${escRaw(e.message)}</p>`;
  }
}

function renderSnapshotChart(snapshots) {
  if (!snapshots || !snapshots.length) {
    return '<p class="empty-msg">No monthly snapshot history recorded for this player (2020-01 to 2026-11).</p>';
  }
  const W = 640, H = 200, padL = 48, padR = 16, padT = 16, padB = 28;
  const pw = W - padL - padR, ph = H - padT - padB;
  const valOf = s => activeChartMetric === 'val' ? ((s.val || 0) / 1e6) : (activeChartMetric === 'form_delta' ? (s.form_delta || 0) : (s.rating || 0));
  const rawVals = snapshots.map(valOf);
  let minV = Math.min(...rawVals), maxV = Math.max(...rawVals);
  if (activeChartMetric === 'rating') { minV = Math.min(minV, 52); maxV = Math.max(maxV, minV + 5); }
  if (maxV === minV) { maxV += 1; minV -= 1; }
  const xAt = i => snapshots.length === 1 ? padL + pw / 2 : padL + (i / (snapshots.length - 1)) * pw;
  const yAt = v => padT + ph - ((v - minV) / (maxV - minV)) * ph;

  const pts = snapshots.map((s, i) => ({ x: xAt(i), y: yAt(valOf(s)), s, v: valOf(s) }));
  const poly = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `${padL},${padT + ph} ${poly} ${pts[pts.length - 1].x.toFixed(1)},${padT + ph}`;
  const fmtAxis = v => activeChartMetric === 'val' ? `€${v.toFixed(1)}M` : v.toFixed(1);
  const strokeCol = activeChartMetric === 'val' ? '#1d4e89' : (activeChartMetric === 'form_delta' ? '#166534' : '#b8432e');
  const fillCol = activeChartMetric === 'val' ? 'rgba(29,78,137,0.14)' : (activeChartMetric === 'form_delta' ? 'rgba(22,101,52,0.14)' : 'rgba(184,67,46,0.14)');

  const gridYs = [0, 0.5, 1].map(t => {
    const val = minV + (1 - t) * (maxV - minV), y = padT + t * ph;
    return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="rgba(31,27,22,0.12)" stroke-dasharray="3 3"/><text x="${padL - 6}" y="${(y + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="#7b7266">${fmtAxis(val)}</text>`;
  }).join('');

  const xTicks = [0, Math.floor((snapshots.length - 1) / 2), snapshots.length - 1]
    .filter((v, idx, a) => a.indexOf(v) === idx)
    .map(idx => `<text x="${xAt(idx).toFixed(1)}" y="${H - 6}" text-anchor="${idx === 0 ? 'start' : (idx === snapshots.length - 1 ? 'end' : 'middle')}" font-size="11" fill="#7b7266">${escRaw((snapshots[idx].report_date || '').slice(0, 7))}</text>`).join('');

  const lastPt = pts[pts.length - 1];
  const circles = pts.map((pt, i) => `<circle class="chart-pt ${i === pts.length - 1 ? 'active' : ''}" data-sidx="${i}" tabindex="0" cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="${snapshots.length > 40 ? 3 : 4}" fill="${strokeCol}" stroke="#ffffff" stroke-width="1.5" aria-label="${escRaw(pt.s.report_date)}: ${fmtAxis(pt.v)}"/>`).join('');

  return `
    <svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Player monthly snapshot timeline">
      ${gridYs}
      <polygon points="${area}" fill="${fillCol}"/>
      <polyline points="${poly}" fill="none" stroke="${strokeCol}" stroke-width="2.2" stroke-linejoin="round"/>
      ${circles}
      ${xTicks}
    </svg>
    <div class="chart-readout num" id="ex-chart-readout">
      <span><b>${escRaw((lastPt.s.report_date || '').slice(0, 7))}</b> · ${escRaw(lastPt.s.club || '-')}</span>
      <span>Rating: <b>${lastPt.s.rating != null ? Number(lastPt.s.rating).toFixed(1) : '-'}</b> · Form delta: <b>${lastPt.s.form_delta >= 0 ? '+' : ''}${lastPt.s.form_delta != null ? Number(lastPt.s.form_delta).toFixed(1) : '0.0'}</b> · Value: <b>${fmtVal(lastPt.s.val)}</b> · g/90: <b>${lastPt.s.goals_per_90 != null ? Number(lastPt.s.goals_per_90).toFixed(2) : '0.00'}</b></span>
    </div>`;
}

function renderPlayerDetail(d) {
  const p = d.player || {}, seasons = d.seasons || [], snaps = d.snapshots || [];
  const panel = $('ex-p-detail');
  const fullName = p.full_name || p.name || 'Player';
  const role = playerRole(p);
  const clubLabel = p.is_former ? (p.former_club || p.club || 'Retired') : p.club;
  const legendBanner = p.is_former
    ? `<span class="legend-badge-hero">Retired / Legend (Last season ${escRaw(p.last_season || '-')})</span>`
    : '';
  const rtgStr = p.rating != null ? Number(p.rating).toFixed(1) : '-';
  const potStr = p.potential != null ? Number(p.potential).toFixed(1) : '-';
  panel.innerHTML = `
    <div class="detail-head">
      <div class="hero-ident">
        ${avatarHtml(p.image_url, fullName, 'av-lg', p.rating)}
        <div>
          <span class="pos">${escRaw(role)}</span>${p.pos && p.pos !== role ? ` <span class="pos-mini">${escRaw(p.pos)}</span>` : ''}${legendBanner}
          <h3 style="margin-top:6px">${escRaw(fullName)}</h3>
          <div class="sub">
            ${clubLabel ? `${p.is_former ? 'Former: ' : ''}<button type="button" class="row-link-btn" id="ex-p-club-link">${escRaw(clubLabel)}</button>` : 'Free Agent'}
            ${p.nat ? ` · <button type="button" class="row-link-btn" id="ex-p-nat-link">${escRaw(p.nat)}</button>` : ''}
            ${p.sub_pos ? ` · ${escRaw(p.sub_pos)}` : ''}
          </div>
          <div class="hero-shields">
            <span class="stat-shield gold num">Rating ${rtgStr}</span>
            <span class="stat-shield cyan num">Potential ${potStr}</span>
            <span class="stat-shield num">Value ${fmtVal(p.val)}</span>
          </div>
        </div>
      </div>
      <div class="detail-actions">
        <button type="button" class="btn btn-sm" id="ex-load-home">Load into Home XI</button>
        <button type="button" class="btn ghost btn-sm" id="ex-load-away">Load into Away XI</button>
      </div>
    </div>

    <div class="bio-grid num">
      <div class="bio-cell"><span>Rating / Potential</span><b>${rtgStr} / ${potStr}</b></div>
      <div class="bio-cell"><span>Market Value</span><b>${fmtVal(p.val)}</b></div>
      <div class="bio-cell"><span>Peak Value</span><b>${fmtVal(p.highest_val)}</b></div>
      <div class="bio-cell"><span>Age / DOB</span><b>${p.age ?? '-'} (${escRaw((p.dob || '').slice(0, 10) || '-')})</b></div>
      <div class="bio-cell"><span>Height / Foot</span><b>${p.height ? `${Math.round(p.height)} cm` : '-'} / ${escRaw(p.foot || '-')}</b></div>
      <div class="bio-cell"><span>Career G / A / g90</span><b>${p.total_goals ?? 0} / ${p.total_assists ?? 0} / ${p.goals_per_90 ?? 0}</b></div>
      <div class="bio-cell"><span>Int'l Caps / Goals</span><b>${p.caps ?? '-'} / ${p.int_goals ?? '-'}</b></div>
      <div class="bio-cell"><span>${p.is_former ? 'Last Active Season' : 'Contract'}</span><b>${p.is_former ? escRaw(p.last_season || '-') : escRaw((p.contract || '').slice(0, 10) || '-')}</b></div>
    </div>

    <div class="chart-box">
      <div class="card-head-row">
        <div>
          <h4>Monthly Report Date Trajectory (2020-01 to 2026-11)</h4>
          <p class="sub">Hover, focus, or click any monthly point to inspect historical condition.</p>
        </div>
        <div class="tab-row compact" id="ex-chart-metrics">
          <button type="button" class="tab-btn ${activeChartMetric === 'rating' ? 'active' : ''}" data-metric="rating">Rating</button>
          <button type="button" class="tab-btn ${activeChartMetric === 'val' ? 'active' : ''}" data-metric="val">Value</button>
          <button type="button" class="tab-btn ${activeChartMetric === 'form_delta' ? 'active' : ''}" data-metric="form_delta">Form Delta</button>
        </div>
      </div>
      <div id="ex-chart-wrap">${renderSnapshotChart(snaps)}</div>
    </div>

    <h4>Season-by-Season Record (2020 to 2026)</h4>
    <div class="tbl-wrap">
      <table class="data-tbl">
        <thead><tr><th>Season</th><th>Competition</th><th>Club</th><th class="num">Apps</th><th class="num">Mins</th><th class="num">Goals</th><th class="num">Assists</th><th class="num">YC</th><th class="num">RC</th></tr></thead>
        <tbody>
          ${seasons.length ? seasons.map(s => `
            <tr>
              <td class="num"><b>${s.season}</b></td>
              <td>${escRaw(s.comp_name || s.comp_id || '-')}</td>
              <td>${escRaw(s.club || '-')}</td>
              <td class="num">${s.apps ?? 0}</td>
              <td class="num">${fmtNum(s.minutes)}</td>
              <td class="num"><b>${s.goals ?? 0}</b></td>
              <td class="num">${s.assists ?? 0}</td>
              <td class="num">${s.yellow_cards ?? 0}</td>
              <td class="num">${s.red_cards ?? 0}</td>
            </tr>`).join('') : '<tr><td colspan="9" class="empty-msg">No match appearances recorded since 2020.</td></tr>'}
        </tbody>
      </table>
    </div>`;

  if ($('ex-p-club-link')) $('ex-p-club-link').onclick = () => openClubInspector(clubLabel);
  if ($('ex-p-nat-link')) $('ex-p-nat-link').onclick = () => openCountryInspector(p.nat);
  if ($('ex-load-home')) $('ex-load-home').onclick = () => insertPlayerIntoSide('home', p);
  if ($('ex-load-away')) $('ex-load-away').onclick = () => insertPlayerIntoSide('away', p);
  if ($('ex-chart-metrics')) $('ex-chart-metrics').onclick = e => {
    const b = e.target.closest('button[data-metric]'); if (!b) return;
    activeChartMetric = b.dataset.metric;
    document.querySelectorAll('#ex-chart-metrics .tab-btn').forEach(x => x.classList.toggle('active', x === b));
    $('ex-chart-wrap').innerHTML = renderSnapshotChart(snaps);
    wireChartPoints(snaps);
  };
  wireChartPoints(snaps);
}

function wireChartPoints(snaps) {
  const wrap = $('ex-chart-wrap'); if (!wrap || !snaps.length) return;
  const showPt = e => {
    const pt = e.target.closest('.chart-pt'); if (!pt) return;
    wrap.querySelectorAll('.chart-pt').forEach(c => c.classList.remove('active'));
    pt.classList.add('active');
    const s = snaps[+pt.dataset.sidx]; if (!s) return;
    const ro = $('ex-chart-readout');
    if (ro) ro.innerHTML = `<span><b>${escRaw((s.report_date || '').slice(0, 7))}</b> · ${escRaw(s.club || '-')}</span><span>Rating: <b>${s.rating != null ? Number(s.rating).toFixed(1) : '-'}</b> · Form delta: <b>${s.form_delta >= 0 ? '+' : ''}${s.form_delta != null ? Number(s.form_delta).toFixed(1) : '0.0'}</b> · Value: <b>${fmtVal(s.val)}</b> · g/90: <b>${s.goals_per_90 != null ? Number(s.goals_per_90).toFixed(2) : '0.00'}</b></span>`;
  };
  wrap.addEventListener('mouseover', showPt);
  wrap.addEventListener('focusin', showPt);
  wrap.addEventListener('click', showPt);
}

async function insertPlayerIntoSide(side, playerObj) {
  const p = byId.get(playerObj.id) || playerObj;
  const nr = playerRole(p);
  const ng = roleToGroup(nr);
  const roles = layout(T[side].formation).map(x => x.role);
  let idx = T[side].slots.findIndex((x, i) => !x && roles[i] === nr);
  if (idx < 0) idx = T[side].slots.findIndex((x, i) => !x && roleToGroup(roles[i]) === ng);
  if (idx < 0) {
    let bestIdx = -1, lowestScore = 9999;
    roles.forEach((r, i) => {
      const pen = oopPenalty(p, r);
      const curR = T[side].slots[i]?.rating ?? 0;
      const score = pen * 100 + curR;
      if (score < lowestScore) { lowestScore = score; bestIdx = i; }
    });
    idx = bestIdx >= 0 ? bestIdx : 10;
  }
  T[side].slots[idx] = p;
  render();
  if (($('wi-date')?.value || '2026-11') !== '2026-11') await applySnapshot(side, true);
  switchView('predictor');
  predict();
}

async function searchExplorerClubs() {
  const list = $('ex-c-list'); if (!list) return;
  const q = $('ex-c-q')?.value.trim() || '';
  const compId = $('ex-c-comp')?.value || '';
  const sort = $('ex-c-sort')?.value || 'total_val';
  const ctxBtn = $('ex-c-clear-ctx');
  if (ctxBtn) {
    if (exClubsCtx.country) { ctxBtn.textContent = `Country: ${exClubsCtx.country} ×`; ctxBtn.hidden = false; }
    else ctxBtn.hidden = true;
  }
  list.innerHTML = '<p class="empty-msg">Loading clubs...</p>';
  try {
    const params = new URLSearchParams({ q, comp_id: compId, sort, limit: '45' });
    if (exClubsCtx.country) params.set('country', exClubsCtx.country);
    const d = await fetch(`/api/explore/clubs?${params}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    const rows = d.clubs || [];
    list.innerHTML = rows.length ? rows.map(c => `
      <button type="button" class="entity-card ${currentClubDetail?.club?.name === c.name ? 'active' : ''}" data-cname="${escRaw(c.name)}" data-cid="${c.club_id ?? ''}">
        ${crestHtml(clubCrestUrl(c), c.name, 'crest-md')}
        <div>
          <div class="entity-title">${escRaw(c.name)}</div>
          <div class="entity-sub">${escRaw(c.comp_name || c.comp_id || '')}${c.country_name ? ` · ${escRaw(c.country_name)}` : ''}</div>
        </div>
        <div class="entity-score">${c.avg_rating != null ? Number(c.avg_rating).toFixed(1) : '-'}<small>${fmtVal(c.total_val)}</small></div>
      </button>`).join('') : '<p class="empty-msg">No clubs matched your filter</p>';
  } catch (e) {
    list.innerHTML = `<p class="state-banner error">Could not load clubs: ${escRaw(e.message)}</p>`;
  }
}

async function openClubInspector(clubName, clubId = null) {
  if (!clubName && !clubId) return;
  switchView('explorer');
  switchExplorerSub('clubs');
  const panel = $('ex-c-detail');
  panel.innerHTML = '<p class="empty-msg">Loading club details, season records, and roster...</p>';
  try {
    const params = new URLSearchParams();
    if (clubName) params.set('name', clubName);
    if (clubId) params.set('id', String(clubId));
    const d = await fetch(`/api/explore/club?${params}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    if (d.status && d.status !== 'success') throw new Error(d.message || 'Club not found');
    currentClubDetail = d;
    document.querySelectorAll('#ex-c-list .entity-card').forEach(c => c.classList.toggle('active', c.dataset.cname === d.club?.name));
    renderClubDetail(d);
  } catch (e) {
    panel.innerHTML = `<p class="state-banner error">Could not load club: ${escRaw(e.message)}</p>`;
  }
}

function renderClubDetail(d) {
  const c = d.club || {}, recs = d.season_records || [], fx = d.recent_matches || [], roster = d.roster || [], former = d.former_players || [];
  const panel = $('ex-c-detail');
  const avgRtg = c.avg_rating != null ? Number(c.avg_rating).toFixed(1) : '-';
  const maxRtg = c.max_rating != null ? Number(c.max_rating).toFixed(1) : '-';
  panel.innerHTML = `
    <div class="detail-head">
      <div class="hero-ident">
        ${crestHtml(clubCrestUrl(c), c.name, 'crest-lg')}
        <div>
          <h3>${escRaw(c.name || 'Club')}</h3>
          <div class="sub">
            ${c.comp_id ? `<button type="button" class="row-link-btn" id="ex-c-lg-link">${escRaw(c.comp_name || c.comp_id)}</button>` : escRaw(c.comp_name || '-')}
            ${c.country_name ? ` · <button type="button" class="row-link-btn" id="ex-c-ct-link">${escRaw(c.country_name)}</button>` : ''}
          </div>
          <div class="hero-shields">
            <span class="stat-shield gold num">Avg ${avgRtg}</span>
            <span class="stat-shield cyan num">Max ${maxRtg}</span>
            <span class="stat-shield num">Value ${fmtVal(c.total_val)}</span>
          </div>
        </div>
      </div>
      <div class="detail-actions">
        <button type="button" class="btn btn-sm" id="ex-c-home">Set as Home team</button>
        <button type="button" class="btn ghost btn-sm" id="ex-c-away">Set as Away team</button>
      </div>
    </div>

    <div class="bio-grid num">
      <div class="bio-cell"><span>Squad value</span><b>${fmtVal(c.total_val)}</b></div>
      <div class="bio-cell"><span>Avg / Max rating</span><b>${avgRtg} / ${maxRtg}</b></div>
      <div class="bio-cell"><span>Squad size / Age</span><b>${c.squad_size ?? roster.length} / ${c.avg_age != null ? Number(c.avg_age).toFixed(1) : '-'}</b></div>
      <div class="bio-cell"><span>Stadium</span><b>${escRaw(c.stadium_name || '-')}${c.stadium_seats ? ` (${fmtNum(c.stadium_seats)})` : ''}</b></div>
      <div class="bio-cell"><span>Coach</span><b>${escRaw(c.coach_name || '-')}</b></div>
    </div>

    <h4>Season records (2020 to 2026)</h4>
    <div class="pill-grid num">
      ${recs.length ? recs.map(r => `<button type="button" class="season-pill" data-lg="${escRaw(r.comp_id || c.comp_id || '')}" data-season="${r.season}"><b>${r.season}</b>: ${r.won ?? 0}W-${r.drawn ?? 0}D-${r.lost ?? 0}L (${r.pts ?? 0} pts)</button>`).join('') : '<span class="empty-msg">No seasonal records available</span>'}
    </div>

    <h4>Recent matches</h4>
    <div class="compact-list">
      ${fx.length ? fx.slice(0, 10).map(m => {
        const res = m.result || '';
        const hn = m.home_club_name || m.home_team || 'Home', an = m.away_club_name || m.away_team || 'Away';
        return `<div class="compact-row">
          <span>${res ? `<span class="wdl ${res}">${res}</span> ` : ''}<b>${escRaw(hn)} ${m.home_goals ?? '-'} - ${m.away_goals ?? '-'} ${escRaw(an)}</b> <small class="sub">${escRaw((m.date || '').slice(0, 10))}</small></span>
          <button type="button" class="btn ghost btn-sm" data-sim-h="${escRaw(hn)}" data-sim-a="${escRaw(an)}">Simulate</button>
        </div>`;
      }).join('') : '<span class="empty-msg">No recent fixtures recorded</span>'}
    </div>

    <h4 style="margin-top:16px">Active first-team squad (${roster.length})</h4>
    <div class="tbl-wrap">
      <table class="data-tbl">
        <thead><tr><th>Player</th><th>Role</th><th class="num">Age</th><th class="num">Rating</th><th class="num">Goals</th><th class="num">Value</th></tr></thead>
        <tbody>
          ${roster.length ? roster.map(p => `
            <tr class="clickable" data-pid="${p.id}">
              <td><button type="button" class="row-link-btn">${avatarHtml(p.image_url, p.name, 'av-xs', p.rating)}<span>${escRaw(p.name)}</span></button></td>
              <td><span class="pos" style="padding:2px 6px">${escRaw(playerRole(p))}</span></td>
              <td class="num">${p.age ?? '-'}</td>
              <td class="num"><b>${p.rating != null ? Number(p.rating).toFixed(1) : '-'}</b></td>
              <td class="num">${p.total_goals ?? 0}</td>
              <td class="num">${fmtVal(p.val)}</td>
            </tr>`).join('') : '<tr><td colspan="6" class="empty-msg">No active squad players found</td></tr>'}
        </tbody>
      </table>
    </div>

    <div class="legends-section">
      <h4>Club legends &amp; former icons (${former.length})</h4>
      <div class="tbl-wrap">
        <table class="data-tbl">
          <thead><tr><th>Player</th><th>Role</th><th class="num">Last season</th><th class="num">Rating</th><th class="num">Goals</th><th class="num">Peak / Last value</th></tr></thead>
          <tbody>
            ${former.length ? former.map(p => `
              <tr class="clickable" data-pid="${p.id}">
                <td><button type="button" class="row-link-btn">${avatarHtml(p.image_url, p.name, 'av-xs', p.rating)}<span>${escRaw(p.name)}</span><span class="legend-tag">Legend</span></button></td>
                <td><span class="pos" style="padding:2px 6px">${escRaw(playerRole(p))}</span></td>
                <td class="num">${escRaw(p.last_season ?? '-')}</td>
                <td class="num"><b>${p.rating != null ? Number(p.rating).toFixed(1) : '-'}</b></td>
                <td class="num">${p.total_goals ?? 0}</td>
                <td class="num">${fmtVal(p.highest_val || p.val)}</td>
              </tr>`).join('') : '<tr><td colspan="6" class="empty-msg">No retired or former legends recorded for this club</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>`;

  if ($('ex-c-lg-link')) $('ex-c-lg-link').onclick = () => openLeagueStandings(c.comp_id);
  if ($('ex-c-ct-link')) $('ex-c-ct-link').onclick = () => openCountryInspector(c.country_name);
  if ($('ex-c-home')) $('ex-c-home').onclick = async () => { if (await setPredictorTeam('home', c.preset_name || c.name, d)) { switchView('predictor'); predict(); } };
  if ($('ex-c-away')) $('ex-c-away').onclick = async () => { if (await setPredictorTeam('away', c.preset_name || c.name, d)) { switchView('predictor'); predict(); } };
  panel.querySelectorAll('.season-pill[data-lg]').forEach(b => b.onclick = () => { if (b.dataset.lg) openLeagueStandings(b.dataset.lg, b.dataset.season); });
  panel.querySelectorAll('button[data-sim-h]').forEach(b => b.onclick = () => simulateFixture(b.dataset.simH, b.dataset.simA));
  panel.querySelectorAll('tbody tr[data-pid]').forEach(tr => tr.onclick = () => openPlayerInspector(+tr.dataset.pid));
}

async function searchExplorerCountries() {
  const list = $('ex-n-list'); if (!list) return;
  const q = $('ex-n-q')?.value.trim() || '';
  const conf = document.querySelector('#ex-n-conf .filter-pill.active')?.dataset.conf || '';
  list.innerHTML = '<p class="empty-msg">Loading countries...</p>';
  try {
    const params = new URLSearchParams({ q, confederation: conf, sort: 'top11_avg_rating', limit: '80' });
    const d = await fetch(`/api/explore/countries?${params}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    const rows = d.countries || [];
    list.innerHTML = rows.length ? rows.map(c => {
      const cUrl = c.team_image_url || crestUrlFor(c.nt_preset_name || `${c.name} (National Team)`);
      return `
      <button type="button" class="entity-card ${currentCountryDetail?.country?.name === c.name ? 'active' : ''}" data-nname="${escRaw(c.name)}">
        ${crestHtml(cUrl, c.name, 'crest-md')}
        <div>
          <div class="entity-title">${escRaw(c.name)}</div>
          <div class="entity-sub">${escRaw(c.confederation || 'FIFA')}${c.fifa_ranking ? ` · FIFA #${c.fifa_ranking}` : ''} · ${c.total_players ?? 0} players</div>
        </div>
        <div class="entity-score">${c.top11_avg_rating != null ? Number(c.top11_avg_rating).toFixed(1) : '-'}<small>Top 11 avg</small></div>
      </button>`;
    }).join('') : '<p class="empty-msg">No countries matched your filter</p>';
  } catch (e) {
    list.innerHTML = `<p class="state-banner error">Could not load countries: ${escRaw(e.message)}</p>`;
  }
}

async function openCountryInspector(countryName) {
  if (!countryName) return;
  switchView('explorer');
  switchExplorerSub('countries');
  const panel = $('ex-n-detail');
  panel.innerHTML = '<p class="empty-msg">Loading country profile, leagues, and top players...</p>';
  try {
    const d = await fetch(`/api/explore/country?name=${encodeURIComponent(countryName)}`).then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
    if (d.status && d.status !== 'success') throw new Error(d.message || 'Country not found');
    currentCountryDetail = d;
    document.querySelectorAll('#ex-n-list .entity-card').forEach(c => c.classList.toggle('active', c.dataset.nname === d.country?.name));
    renderCountryDetail(d);
  } catch (e) {
    panel.innerHTML = `<p class="state-banner error">Could not load country: ${escRaw(e.message)}</p>`;
  }
}

function renderCountryDetail(d) {
  const c = d.country || {}, lgs = d.domestic_leagues || [], clubs = d.top_clubs || [], topP = d.top_players || [];
  const ntName = c.nt_preset_name || `${c.name} (National Team)`;
  const canLoadNT = Boolean(d.preset || c.has_preset || presets[ntName] || topP.length >= 11);
  const cUrl = c.team_image_url || crestUrlFor(ntName);
  const top11Str = c.top11_avg_rating != null ? Number(c.top11_avg_rating).toFixed(1) : '-';
  const panel = $('ex-n-detail');
  panel.innerHTML = `
    <div class="detail-head">
      <div class="hero-ident">
        ${crestHtml(cUrl, c.name, 'crest-lg')}
        <div>
          <h3>${escRaw(c.name || 'Country')}</h3>
          <div class="sub">${escRaw(c.confederation || 'FIFA')}${c.fifa_ranking ? ` · FIFA ranking #${c.fifa_ranking}` : ''}${c.coach_name ? ` · Coach: ${escRaw(c.coach_name)}` : ''}</div>
          <div class="hero-shields">
            ${c.fifa_ranking ? `<span class="stat-shield cyan num">FIFA #${c.fifa_ranking}</span>` : ''}
            <span class="stat-shield gold num">Top 11 ${top11Str}</span>
            <span class="stat-shield">${escRaw(c.confederation || 'FIFA')}</span>
          </div>
        </div>
      </div>
      <div class="detail-actions">
        <button type="button" class="btn btn-sm" id="ex-n-home" ${canLoadNT ? '' : 'disabled'}>Load national team (Home)</button>
        <button type="button" class="btn ghost btn-sm" id="ex-n-away" ${canLoadNT ? '' : 'disabled'}>Load national team (Away)</button>
      </div>
    </div>

    <div class="bio-grid num">
      <div class="bio-cell"><span>Player pool</span><b>${fmtNum(c.total_players)}</b></div>
      <div class="bio-cell"><span>Clubs tracked</span><b>${fmtNum(c.total_clubs)}</b></div>
      <div class="bio-cell"><span>Top-11 avg rating</span><b>${top11Str}</b></div>
      <div class="bio-cell"><span>Top-25 value</span><b>${fmtVal(c.top25_val)}</b></div>
      <div class="bio-cell"><span>Pool avg age</span><b>${c.avg_age != null ? Number(c.avg_age).toFixed(1) : '-'}</b></div>
    </div>

    <div class="detail-split">
      <div>
        <h4>Domestic leagues</h4>
        <div class="compact-list">
          ${lgs.length ? lgs.map(l => `<button type="button" class="compact-row clickable" data-lg="${escRaw(l.comp_id)}"><span><b>${escRaw(l.name)}</b></span><span class="sub">${escRaw(l.comp_id)}</span></button>`).join('') : '<span class="empty-msg">No domestic leagues tracked</span>'}
        </div>
      </div>
      <div>
        <h4>Top domestic clubs</h4>
        <div class="compact-list">
          ${clubs.length ? clubs.map(cl => `<button type="button" class="compact-row clickable" data-club="${escRaw(cl.name)}" data-cid="${cl.club_id ?? ''}"><span style="display:inline-flex;align-items:center;gap:8px">${crestHtml(clubCrestUrl(cl), cl.name, 'crest-xs')}<b>${escRaw(cl.name)}</b></span><span class="sub num">Rtg ${cl.avg_rating != null ? Number(cl.avg_rating).toFixed(1) : '-'} · ${fmtVal(cl.total_val)}</span></button>`).join('') : '<span class="empty-msg">No domestic clubs tracked</span>'}
        </div>
      </div>
    </div>

    <h4 style="margin-top:16px">Top players by nationality</h4>
    <div class="tbl-wrap">
      <table class="data-tbl">
        <thead><tr><th>Player</th><th>Role</th><th>Club</th><th class="num">Age</th><th class="num">Rating</th><th class="num">Value</th></tr></thead>
        <tbody>
          ${topP.length ? topP.map(p => `
            <tr class="clickable" data-pid="${p.id}">
              <td><button type="button" class="row-link-btn">${avatarHtml(p.image_url, p.name, 'av-xs', p.rating)}<span>${escRaw(p.name)}</span></button></td>
              <td><span class="pos" style="padding:2px 6px">${escRaw(playerRole(p))}</span></td>
              <td>${escRaw(p.club || '-')}</td>
              <td class="num">${p.age ?? '-'}</td>
              <td class="num"><b>${p.rating != null ? Number(p.rating).toFixed(1) : '-'}</b></td>
              <td class="num">${fmtVal(p.val)}</td>
            </tr>`).join('') : '<tr><td colspan="6" class="empty-msg">No players recorded</td></tr>'}
        </tbody>
      </table>
    </div>`;

  if ($('ex-n-home')) $('ex-n-home').onclick = async () => { if (await setPredictorTeam('home', ntName, d)) { switchView('predictor'); predict(); } };
  if ($('ex-n-away')) $('ex-n-away').onclick = async () => { if (await setPredictorTeam('away', ntName, d)) { switchView('predictor'); predict(); } };
  panel.querySelectorAll('button[data-lg]').forEach(b => b.onclick = () => openLeagueStandings(b.dataset.lg));
  panel.querySelectorAll('button[data-club]').forEach(b => b.onclick = () => openClubInspector(b.dataset.club, b.dataset.cid ? +b.dataset.cid : null));
  panel.querySelectorAll('tbody tr[data-pid]').forEach(tr => tr.onclick = () => openPlayerInspector(+tr.dataset.pid));
}

function wireExplorerView() {
  if ($('ex-subtabs')) $('ex-subtabs').onclick = e => {
    const b = e.target.closest('button[data-sub]');
    if (b) switchExplorerSub(b.dataset.sub);
  };

  let pTimer = null, cTimer = null, nTimer = null;
  if ($('ex-p-q')) $('ex-p-q').addEventListener('input', () => { clearTimeout(pTimer); pTimer = setTimeout(searchExplorerPlayers, 180); });
  if ($('ex-p-sort')) $('ex-p-sort').onchange = searchExplorerPlayers;
  if ($('ex-p-status')) $('ex-p-status').onclick = e => {
    const b = e.target.closest('button[data-status]'); if (!b) return;
    document.querySelectorAll('#ex-p-status .filter-pill').forEach(x => x.classList.toggle('active', x === b));
    searchExplorerPlayers();
  };
  if ($('ex-p-pos')) $('ex-p-pos').onclick = e => {
    const b = e.target.closest('button[data-pos]'); if (!b) return;
    document.querySelectorAll('#ex-p-pos .filter-pill').forEach(x => x.classList.toggle('active', x === b));
    searchExplorerPlayers();
  };
  if ($('ex-p-clear-ctx')) $('ex-p-clear-ctx').onclick = () => { exPlayersCtx = { club: '', nat: '' }; searchExplorerPlayers(); };
  if ($('ex-p-list')) $('ex-p-list').onclick = e => {
    const b = e.target.closest('button[data-pid]');
    if (b) openPlayerInspector(+b.dataset.pid);
  };

  if ($('ex-c-q')) $('ex-c-q').addEventListener('input', () => { clearTimeout(cTimer); cTimer = setTimeout(searchExplorerClubs, 180); });
  if ($('ex-c-comp')) $('ex-c-comp').onchange = searchExplorerClubs;
  if ($('ex-c-sort')) $('ex-c-sort').onchange = searchExplorerClubs;
  if ($('ex-c-clear-ctx')) $('ex-c-clear-ctx').onclick = () => { exClubsCtx = { country: '' }; searchExplorerClubs(); };
  if ($('ex-c-list')) $('ex-c-list').onclick = e => {
    const b = e.target.closest('button[data-cname]');
    if (b) openClubInspector(b.dataset.cname, b.dataset.cid ? +b.dataset.cid : null);
  };

  if ($('ex-n-q')) $('ex-n-q').addEventListener('input', () => { clearTimeout(nTimer); nTimer = setTimeout(searchExplorerCountries, 180); });
  if ($('ex-n-conf')) $('ex-n-conf').onclick = e => {
    const b = e.target.closest('button[data-conf]'); if (!b) return;
    document.querySelectorAll('#ex-n-conf .filter-pill').forEach(x => x.classList.toggle('active', x === b));
    searchExplorerCountries();
  };
  if ($('ex-n-sea')) $('ex-n-sea').onclick = e => {
    const b = e.target.closest('button[data-country]');
    if (b) openCountryInspector(b.dataset.country);
  };
  if ($('ex-n-list')) $('ex-n-list').onclick = e => {
    const b = e.target.closest('button[data-nname]');
    if (b) openCountryInspector(b.dataset.nname);
  };
}

// =========================================================================
// TAB 4: MATCH CALENDAR (PREVIOUS, TODAY & INCOMING)
// =========================================================================
function shiftMonthStr(monthStr, delta) {
  const [y, m] = monthStr.split('-').map(Number);
  const dt = new Date(Date.UTC(y, (m - 1) + delta, 1));
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}`;
}

function formatMonthLabel(monthStr) {
  const [y, m] = monthStr.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
}

function formatKickoffTime(isoStr) {
  if (!isoStr) return '';
  const dt = new Date(isoStr);
  if (Number.isNaN(dt.getTime())) return '';
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

async function ensureCalendarLoaded(forceMonth = null) {
  const target = forceMonth || calActiveMonth;
  if (calData && calData.month === target) {
    renderCalendarView();
    return;
  }
  await loadCalendarMonth(target);
}

async function loadCalendarMonth(monthStr) {
  calActiveMonth = monthStr;
  if ($('cal-month-label')) $('cal-month-label').textContent = formatMonthLabel(monthStr);
  const st = $('cal-status');
  if (calCache.has(monthStr)) {
    calData = calCache.get(monthStr);
    if (st) st.hidden = true;
    renderCalendarView();
    return;
  }
  if (st) { st.textContent = 'Loading fixtures for ' + formatMonthLabel(monthStr) + '...'; st.classList.remove('error'); st.hidden = false; }
  try {
    const d = await fetch(`/api/calendar?month=${encodeURIComponent(monthStr)}`).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
    if (d.status && d.status !== 'success') throw new Error(d.message || 'Calendar unavailable');
    calCache.set(monthStr, d);
    calData = d;
    if (!calSelectedDate.startsWith(monthStr)) {
      calSelectedDate = d.today?.startsWith(monthStr) ? d.today : `${monthStr}-01`;
    }
    if (st) st.hidden = true;
    renderCalendarView();
  } catch (e) {
    if (st) { st.textContent = `Could not load match calendar: ${e.message}`; st.classList.add('error'); st.hidden = false; }
  }
}

function renderCalendarView() {
  if (!calData) return;
  const c = calData.counts || {};
  if ($('cal-month-label')) $('cal-month-label').textContent = formatMonthLabel(calData.month);
  if ($('cal-kpis')) {
    $('cal-kpis').innerHTML = [
      ['Month Fixtures', fmtNum(c.total || 0)],
      ['Upcoming', fmtNum(c.upcoming || 0)],
      ['Live Now', fmtNum(c.live || 0)],
      ['Previous / FT', fmtNum(c.finished || 0)],
    ].map(([k, v]) => `<div class="kpi-card"><span class="kpi-label">${k}</span><span class="kpi-val">${v}</span></div>`).join('');
  }
  renderCalendarGrid();
  renderCalendarMatches();
}

function renderCalendarGrid() {
  const grid = $('cal-grid');
  if (!grid || !calData) return;
  const [y, m] = calData.month.split('-').map(Number);
  const firstDay = new Date(Date.UTC(y, m - 1, 1));
  const daysInMonth = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const startOffset = (firstDay.getUTCDay() + 6) % 7; // Mon=0 .. Sun=6
  const todayStr = calData.today || new Date().toISOString().slice(0, 10);
  const daysMap = calData.days || {};

  const cells = [];
  for (let i = 0; i < startOffset; i++) cells.push('<div class="cal-day pad" aria-hidden="true"></div>');
  for (let day = 1; day <= daysInMonth; day++) {
    const dStr = `${calData.month}-${String(day).padStart(2, '0')}`;
    const info = daysMap[dStr];
    const isToday = dStr === todayStr;
    const isSel = dStr === calSelectedDate && calScope === 'day';
    const badges = info ? [
      info.finished ? `<span class="cal-cnt finished" title="${info.finished} previous">${info.finished} FT</span>` : '',
      info.live ? `<span class="cal-cnt live" title="${info.live} live">${info.live} LIVE</span>` : '',
      info.upcoming ? `<span class="cal-cnt upcoming" title="${info.upcoming} upcoming">${info.upcoming} UP</span>` : '',
    ].filter(Boolean).join('') : '';
    cells.push(`
      <button type="button" class="cal-day ${isToday ? 'is-today' : ''} ${isSel ? 'selected' : ''}" data-date="${dStr}" role="gridcell" aria-selected="${isSel}">
        <div class="cal-day-num"><span>${day}</span>${isToday ? '<span class="cal-today-tag">Today</span>' : ''}</div>
        <div class="cal-badges">${badges}</div>
      </button>`);
  }
  grid.innerHTML = cells.join('');
}

function renderCalendarMatches() {
  const list = $('cal-match-list'), title = $('cal-feed-title');
  if (!list || !calData) return;
  const q = ($('cal-q')?.value || '').trim().toLowerCase();
  const todayStr = calData.today || new Date().toISOString().slice(0, 10);
  let rows = calData.matches || [];

  if (calScope === 'day') {
    rows = rows.filter(m => m.date === calSelectedDate);
    if (title) title.textContent = calSelectedDate === todayStr ? `Today's Matches (${calSelectedDate})` : `Matches on ${calSelectedDate}`;
  } else if (calScope === 'today') {
    rows = rows.filter(m => m.date === todayStr);
    if (title) title.textContent = `Today's Matches (${todayStr})`;
  } else if (calScope === 'upcoming') {
    rows = rows.filter(m => m.bucket === 'upcoming' || m.bucket === 'live');
    if (title) title.textContent = `Upcoming Matches (${formatMonthLabel(calData.month)})`;
  } else if (calScope === 'finished') {
    rows = rows.filter(m => m.bucket === 'finished').slice().reverse();
    if (title) title.textContent = `Previous Results (${formatMonthLabel(calData.month)})`;
  } else {
    if (title) title.textContent = `All Fixtures (${formatMonthLabel(calData.month)})`;
  }

  if (q) {
    rows = rows.filter(m => `${m.home_team} ${m.away_team} ${m.league}`.toLowerCase().includes(q));
  }

  list.innerHTML = rows.length ? rows.slice(0, 200).map(m => {
    const scoreTxt = (m.bucket !== 'upcoming' && m.home_goals != null && m.away_goals != null)
      ? `${m.home_goals} - ${m.away_goals}`
      : 'vs';
    const koTime = formatKickoffTime(m.match_date);
    const badgeLbl = m.bucket === 'finished' ? (m.status || 'FT') : (m.bucket === 'live' ? (m.status || 'LIVE') : 'UPCOMING');
    return `
      <div class="cal-match-row">
        <div>
          <div class="cal-match-meta">
            <span class="cal-status-badge ${escRaw(m.bucket)}">${escRaw(badgeLbl)}</span>
            <span>${escRaw(m.date)}${koTime ? ` · ${escRaw(koTime)}` : ''}</span>
            <span>${escRaw(m.league)}</span>
          </div>
          <div class="cal-match-teams">${escRaw(m.home_team)} <span>${scoreTxt}</span> ${escRaw(m.away_team)}</div>
        </div>
        <button type="button" class="btn ghost btn-sm" data-cal-h="${escRaw(m.home_team)}" data-cal-a="${escRaw(m.away_team)}">Predict</button>
      </div>`;
  }).join('') : '<p class="empty-msg">No matches recorded for this selection. Try another day or switch to Upcoming / Previous.</p>';
}

function wireCalendarView() {
  if ($('cal-prev')) $('cal-prev').onclick = () => loadCalendarMonth(shiftMonthStr(calActiveMonth, -1));
  if ($('cal-next')) $('cal-next').onclick = () => loadCalendarMonth(shiftMonthStr(calActiveMonth, 1));
  if ($('cal-today')) $('cal-today').onclick = () => {
    const todayStr = (calData?.today) || new Date().toISOString().slice(0, 10);
    calSelectedDate = todayStr;
    calScope = 'day';
    document.querySelectorAll('#cal-scope-tabs .filter-pill').forEach(x => x.classList.toggle('active', x.dataset.scope === 'day'));
    loadCalendarMonth(todayStr.slice(0, 7));
  };
  if ($('cal-grid')) $('cal-grid').onclick = e => {
    const b = e.target.closest('button[data-date]');
    if (!b) return;
    calSelectedDate = b.dataset.date;
    calScope = 'day';
    document.querySelectorAll('#cal-scope-tabs .filter-pill').forEach(x => x.classList.toggle('active', x.dataset.scope === 'day'));
    renderCalendarGrid();
    renderCalendarMatches();
  };
  if ($('cal-scope-tabs')) $('cal-scope-tabs').onclick = e => {
    const b = e.target.closest('button[data-scope]');
    if (!b) return;
    calScope = b.dataset.scope;
    document.querySelectorAll('#cal-scope-tabs .filter-pill').forEach(x => x.classList.toggle('active', x === b));
    renderCalendarGrid();
    renderCalendarMatches();
  };
  if ($('cal-q')) $('cal-q').addEventListener('input', renderCalendarMatches);
  if ($('cal-match-list')) $('cal-match-list').onclick = e => {
    const b = e.target.closest('button[data-cal-h]');
    if (b) simulateFixture(b.dataset.calH, b.dataset.calA);
  };
}

init();
