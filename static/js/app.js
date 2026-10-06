/**
 * TacticalPredict Frontend App with 400+ Clubs & National Teams Presets & XAI Breakdown
 */

let allPlayers = [];
let presetLineups = {};
let presetCategories = {};

const FORMATIONS = {
  '4-3-3':   ['GK', 'DEF', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'ATT', 'ATT', 'ATT'],
  '4-2-3-1': ['GK', 'DEF', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'MID', 'ATT'],
  '4-4-2':   ['GK', 'DEF', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'ATT', 'ATT'],
  '3-5-2':   ['GK', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'MID', 'ATT', 'ATT'],
  '3-4-3':   ['GK', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'ATT', 'ATT', 'ATT'],
  '5-3-2':   ['GK', 'DEF', 'DEF', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'ATT', 'ATT'],
  '5-4-1':   ['GK', 'DEF', 'DEF', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'ATT'],
  '4-1-4-1': ['GK', 'DEF', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'MID', 'ATT']
};

let currentHomeFormation = '4-3-3';
let currentAwayFormation = '4-2-3-1';

document.addEventListener('DOMContentLoaded', async () => {
  await loadDatabase();
  renderPresetDropdowns();
  buildSlotsForTeam('home', currentHomeFormation);
  buildSlotsForTeam('away', currentAwayFormation);
  loadMatchPreset('Spain (National Team)', 'England (National Team)');
});

async function loadDatabase() {
  try {
    const [playersRes, presetsRes, catRes] = await Promise.all([
      fetch('/api/players'),
      fetch('/api/presets'),
      fetch('/api/categories'),
      ]);
    allPlayers = await playersRes.json();
    presetLineups = await presetsRes.json();
    presetCategories = await catRes.json();
    console.log(`Loaded ${allPlayers.length} players, ${Object.keys(presetLineups).length} presets, and Academic Sidang Report.`);
  } catch (err) {
    console.error('Failed to load database:', err);
  }
}

function renderPresetDropdowns(homeFilter = '', awayFilter = '') {
  renderSinglePresetDropdown('home', homeFilter);
  renderSinglePresetDropdown('away', awayFilter);
}

function renderSinglePresetDropdown(team, filterText = '') {
  const select = document.getElementById(`${team}-preset-select`);
  const curVal = select.value;
  select.innerHTML = '<option value="">-- Choose Squad --</option>';

  const fLow = filterText.trim().toLowerCase();

  for (const [catName, squadNames] of Object.entries(presetCategories)) {
    const filteredSquads = fLow ? squadNames.filter(s => s.toLowerCase().includes(fLow) || catName.toLowerCase().includes(fLow)) : squadNames;
    
    if (filteredSquads.length > 0) {
      const optgroup = document.createElement('optgroup');
      optgroup.label = catName;

      filteredSquads.forEach(sName => {
        const opt = document.createElement('option');
        opt.value = sName;
        opt.innerText = sName;
        if (sName === curVal) opt.selected = true;
        optgroup.appendChild(opt);
      });

      select.appendChild(optgroup);
    }
  }
}

function filterPresetDropdown(team, filterText) {
  renderSinglePresetDropdown(team, filterText);
}

function buildSlotsForTeam(team, formationName) {
  const container = document.getElementById(`${team}-starters-container`);
  const posList = FORMATIONS[formationName] || FORMATIONS['4-3-3'];
  
  const existingValues = [];
  container.querySelectorAll('.player-slot').forEach(slot => {
    const input = slot.querySelector('.search-input');
    existingValues.push({
      name: input.value,
      playerId: input.dataset.playerId,
      rating: input.dataset.rating,
      pos: input.dataset.pos
    });
  });

  container.innerHTML = '';
  document.getElementById(`${team}-formation-display`).innerText = formationName;

  posList.forEach((pos, idx) => {
    const slot = createPlayerSlot(team, 'starter', idx, pos);
    container.appendChild(slot);
    
    if (existingValues[idx] && existingValues[idx].name) {
      const input = slot.querySelector('.search-input');
      const ratingBadge = slot.querySelector('.slot-rating-badge');
      const ev = existingValues[idx];
      
      input.value = ev.name;
      input.dataset.playerId = ev.playerId || '';
      input.dataset.rating = ev.rating || '';
      input.dataset.pos = ev.pos || pos;
      
      if (ev.rating) {
        ratingBadge.innerText = ev.rating;
        setRatingBadgeClass(ratingBadge, parseFloat(ev.rating));
      }
    }
  });

  updateTeamAverages(team);
}

function changeFormation(team, formationName) {
  if (team === 'home') currentHomeFormation = formationName;
  else currentAwayFormation = formationName;
  buildSlotsForTeam(team, formationName);
}

function createPlayerSlot(team, type, index, posLabel) {
  const slot = document.createElement('div');
  slot.className = 'player-slot';
  slot.id = `${team}-${type}-${index}`;
  slot.dataset.team = team;
  slot.dataset.type = type;
  slot.dataset.index = index;
  slot.dataset.posSlot = posLabel;

  const posBadge = document.createElement('span');
  posBadge.className = `slot-pos-badge pos-${posLabel}`;
  posBadge.innerText = posLabel;

  const searchWrapper = document.createElement('div');
  searchWrapper.className = 'player-search-wrapper';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'search-input';
  input.placeholder = `Type player name (${posLabel})...`;
  input.autocomplete = 'off';

  const dropdown = document.createElement('div');
  dropdown.className = 'search-dropdown';

  const ratingBadge = document.createElement('span');
  ratingBadge.className = 'slot-rating-badge';
  ratingBadge.innerText = '--';

  searchWrapper.appendChild(input);
  searchWrapper.appendChild(dropdown);

  slot.appendChild(posBadge);
  slot.appendChild(searchWrapper);
  slot.appendChild(ratingBadge);

  if (type === 'sub') {
    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn-remove-sub';
    removeBtn.innerHTML = '✕';
    removeBtn.title = 'Remove substitute';
    removeBtn.onclick = () => {
      slot.remove();
      updateTeamAverages(team);
    };
    slot.appendChild(removeBtn);
  }

  setupAutocomplete(input, dropdown, ratingBadge, posBadge, team);
  return slot;
}

function setupAutocomplete(input, dropdown, ratingBadge, posBadge, team) {
  input.addEventListener('input', () => {
    const query = input.value.trim().toLowerCase();
    if (query.length < 2) {
      dropdown.classList.remove('open');
      dropdown.innerHTML = '';
      return;
    }

    const matches = allPlayers
      .filter(p => p.name.toLowerCase().includes(query) || p.full_name.toLowerCase().includes(query) || p.club.toLowerCase().includes(query) || p.nat.toLowerCase().includes(query))
      .slice(0, 15);

    renderDropdownItems(matches, dropdown, input, ratingBadge, posBadge, team);
  });

  input.addEventListener('focus', () => {
    if (input.value.trim().length >= 2 && dropdown.children.length > 0) {
      dropdown.classList.add('open');
    }
  });

  document.addEventListener('click', (e) => {
    if (!input.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.remove('open');
    }
  });
}

function renderDropdownItems(players, dropdown, input, ratingBadge, posBadge, team) {
  dropdown.innerHTML = '';
  if (players.length === 0) {
    dropdown.classList.remove('open');
    return;
  }

  players.forEach(p => {
    const item = document.createElement('div');
    item.className = 'dropdown-item';
    
    let ratingClass = 'rating-avg';
    if (p.rating >= 88) ratingClass = 'rating-elite';
    else if (p.rating >= 80) ratingClass = 'rating-great';
    else if (p.rating >= 74) ratingClass = 'rating-good';

    item.innerHTML = `
      <div class="dropdown-item-left">
        <span class="slot-pos-badge pos-${p.pos}" style="font-size: 10px; width: 28px;">${p.pos}</span>
        <div>
          <span class="dropdown-item-name">${p.full_name || p.name}</span>
          <span class="dropdown-item-club">${p.club} • ${p.nat}</span>
        </div>
      </div>
      <div class="dropdown-item-right">
        <span class="slot-rating-badge ${ratingClass}">${p.rating}</span>
      </div>
    `;

    item.onclick = () => {
      selectPlayerForSlot(p, input, ratingBadge, posBadge, team);
      dropdown.classList.remove('open');
    };

    dropdown.appendChild(item);
  });

  dropdown.classList.add('open');
}


const OOP_PENALTY_MAP = {
  'GK':  { 'GK': 0, 'DEF': 40, 'MID': 45, 'ATT': 45 },
  'DEF': { 'GK': 45, 'DEF': 0, 'MID': 4, 'ATT': 18 },
  'MID': { 'GK': 45, 'DEF': 6, 'MID': 0, 'ATT': 4 },
  'ATT': { 'GK': 45, 'DEF': 18, 'MID': 5, 'ATT': 0 }
};

function selectPlayerForSlot(player, input, ratingBadge, posBadge, team) {
  input.value = player.name;
  input.dataset.playerId = player.id;
  input.dataset.rating = player.rating;
  input.dataset.nativePos = player.pos;

  const slotPos = input.closest('.player-slot').dataset.posSlot;
  input.dataset.pos = slotPos;

  // Calculate Out-of-Position Penalty
  const nativePos = player.pos || 'MID';
  let penalty = 0;
  if (slotPos && slotPos !== 'SUB' && OOP_PENALTY_MAP[nativePos]) {
    penalty = OOP_PENALTY_MAP[nativePos][slotPos] || 0;
  }
  
  const effectiveRating = Math.max(35, player.rating - penalty);
  input.dataset.effectiveRating = effectiveRating;
  input.dataset.penalty = penalty;

  if (penalty > 0) {
    ratingBadge.innerText = `${effectiveRating} (-${penalty})`;
    ratingBadge.title = `Native Pos: ${nativePos} (${player.rating}). Out-of-Position penalty: -${penalty}`;
    ratingBadge.className = 'slot-rating-badge rating-oop-penalty';
  } else {
    ratingBadge.innerText = player.rating;
    ratingBadge.title = `Rating: ${player.rating}`;
    setRatingBadgeClass(ratingBadge, player.rating);
  }

  updateTeamAverages(team);
}


function setRatingBadgeClass(badge, rating) {
  badge.className = 'slot-rating-badge';
  if (rating >= 88) badge.classList.add('rating-elite');
  else if (rating >= 80) badge.classList.add('rating-great');
  else if (rating >= 74) badge.classList.add('rating-good');
  else badge.classList.add('rating-avg');
}

function addSubstituteSlot(team) {
  const container = document.getElementById(`${team}-subs-container`);
  const idx = container.children.length;
  const slot = createPlayerSlot(team, 'sub', idx, 'SUB');
  container.appendChild(slot);
}

function updateTeamLabels() {
  const hName = document.getElementById('home-team-name').value || 'Squad 1';
  const aName = document.getElementById('away-team-name').value || 'Squad 2';
  document.getElementById('prob-home-name').innerText = `${hName} Win`;
  document.getElementById('prob-away-name').innerText = `${aName} Win`;
}

function updateTeamAverages(team) {
  const starters = Array.from(document.querySelectorAll(`#${team}-starters-container .search-input`))
    .map(inp => parseFloat(inp.dataset.effectiveRating || inp.dataset.rating))
    .filter(r => !isNaN(r));

  const subs = Array.from(document.querySelectorAll(`#${team}-subs-container .search-input`))
    .map(inp => parseFloat(inp.dataset.rating))
    .filter(r => !isNaN(r));

  const xiAvg = starters.length > 0 ? (starters.reduce((a, b) => a + b, 0) / starters.length).toFixed(1) : '--';
  const benchAvg = subs.length > 0 ? (subs.reduce((a, b) => a + b, 0) / subs.length).toFixed(1) : '--';

  document.getElementById(`${team}-xi-avg`).innerText = xiAvg;
  document.getElementById(`${team}-bench-avg`).innerText = benchAvg;
  document.getElementById(`${team}-starters-count`).innerText = `${starters.length}/11`;
}

function loadMatchPreset(squad1Name, squad2Name) {
  document.getElementById('home-team-name').value = squad1Name;
  document.getElementById('away-team-name').value = squad2Name;
  
  loadSingleTeamPreset('home', squad1Name);
  loadSingleTeamPreset('away', squad2Name);
  updateTeamLabels();
}

function cleanStr(text) {
  return (text || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]/g, ' ').trim();
}

function loadSingleTeamPreset(team, squadName) {
  if (!squadName || !presetLineups[squadName]) return;
  const squad = presetLineups[squadName];

  const select = document.getElementById(`${team}-preset-select`);
  if (select) select.value = squadName;

  const nameInput = document.getElementById(`${team}-team-name`);
  if (nameInput) nameInput.value = squadName;
  updateTeamLabels();

  const formName = squad.formation || '4-3-3';
  document.getElementById(`${team}-formation-select`).value = formName;
  if (team === 'home') currentHomeFormation = formName;
  else currentAwayFormation = formName;
  buildSlotsForTeam(team, formName);

  const starterSlots = document.querySelectorAll(`#${team}-starters-container .player-slot`);
  squad.starters.forEach((pName, idx) => {
    if (idx < starterSlots.length) {
      const slot = starterSlots[idx];
      const input = slot.querySelector('.search-input');
      const ratingBadge = slot.querySelector('.slot-rating-badge');
      const posBadge = slot.querySelector('.slot-pos-badge');

      const clName = cleanStr(pName);
      const found = allPlayers.find(p => cleanStr(p.name) === clName || cleanStr(p.full_name) === clName || cleanStr(p.tm_name) === clName) ||
                    allPlayers.find(p => cleanStr(p.full_name).includes(clName) || cleanStr(p.name).includes(clName));
      if (found) {
        selectPlayerForSlot(found, input, ratingBadge, posBadge, team);
      } else {
        input.value = pName;
      }
    }
  });

  const subsContainer = document.getElementById(`${team}-subs-container`);
  subsContainer.innerHTML = '';
  squad.subs.forEach((pName, idx) => {
    const slot = createPlayerSlot(team, 'sub', idx, 'SUB');
    subsContainer.appendChild(slot);

    const input = slot.querySelector('.search-input');
    const ratingBadge = slot.querySelector('.slot-rating-badge');
    const posBadge = slot.querySelector('.slot-pos-badge');

    const clName = cleanStr(pName);
    const found = allPlayers.find(p => cleanStr(p.name) === clName || cleanStr(p.full_name) === clName || cleanStr(p.tm_name) === clName) ||
                  allPlayers.find(p => cleanStr(p.full_name).includes(clName) || cleanStr(p.name).includes(clName));
    if (found) {
      selectPlayerForSlot(found, input, ratingBadge, posBadge, team);
    } else {
      input.value = pName;
    }
  });

  updateTeamAverages(team);
}

function switchViewMode(mode) {
  const tabs = ['3class', 'scores', 'binary', 'xai'];
  tabs.forEach(t => {
    const tabEl = document.getElementById(`tab-${t}`);
    const viewEl = document.getElementById(`view-${t}`);
    if (tabEl) tabEl.classList.remove('active');
    if (viewEl) viewEl.classList.add('hidden');
  });

  const activeTab = document.getElementById(`tab-${mode}`);
  const activeView = document.getElementById(`view-${mode}`);
  if (activeTab) activeTab.classList.add('active');
  if (activeView) activeView.classList.remove('hidden');
}

async function runPrediction() {
  const predictBtn = document.getElementById('predict-btn');
  predictBtn.disabled = true;
  predictBtn.innerHTML = '<span>⏳ Simulating Match & Scorers...</span>';

  const homeName = document.getElementById('home-team-name').value || 'Squad 1';
  const awayName = document.getElementById('away-team-name').value || 'Squad 2';

  const homeStarters = Array.from(document.querySelectorAll('#home-starters-container .player-slot')).map(slot => {
    const inp = slot.querySelector('.search-input');
    return {
      name: inp.value.trim(),
      id: inp.dataset.playerId ? parseInt(inp.dataset.playerId) : null,
      slot_pos: slot.dataset.posSlot
    };
  }).filter(p => Boolean(p.name));

  const homeSubs = Array.from(document.querySelectorAll('#home-subs-container .player-slot')).map(slot => {
    const inp = slot.querySelector('.search-input');
    return {
      name: inp.value.trim(),
      id: inp.dataset.playerId ? parseInt(inp.dataset.playerId) : null,
      slot_pos: 'SUB'
    };
  }).filter(p => Boolean(p.name));

  const awayStarters = Array.from(document.querySelectorAll('#away-starters-container .player-slot')).map(slot => {
    const inp = slot.querySelector('.search-input');
    return {
      name: inp.value.trim(),
      id: inp.dataset.playerId ? parseInt(inp.dataset.playerId) : null,
      slot_pos: slot.dataset.posSlot
    };
  }).filter(p => Boolean(p.name));

  const awaySubs = Array.from(document.querySelectorAll('#away-subs-container .player-slot')).map(slot => {
    const inp = slot.querySelector('.search-input');
    return {
      name: inp.value.trim(),
      id: inp.dataset.playerId ? parseInt(inp.dataset.playerId) : null,
      slot_pos: 'SUB'
    };
  }).filter(p => Boolean(p.name));

  const homeFormPts = parseFloat(document.getElementById('home-form-select').value) || 1.8;
  const awayFormPts = parseFloat(document.getElementById('away-form-select').value) || 1.8;

  if (homeStarters.length === 0 || awayStarters.length === 0) {
    alert('Please enter starting players for both teams.');
    predictBtn.disabled = false;
    predictBtn.innerHTML = '<span class="btn-icon">⚽</span><span class="btn-text">Predict Match, Goalscorers & XAI Breakdown</span>';
    return;
  }

  try {
    const res = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        home_name: homeName,
        away_name: awayName,
        home_starters: homeStarters,
        home_subs: homeSubs,
        away_starters: awayStarters,
        away_subs: awaySubs,
        home_form_pts: homeFormPts,
        away_form_pts: awayFormPts
      })
    });

    const data = await res.json();
    if (data.status === 'success') {
      displayResults(data, homeName, awayName);
    } else {
      alert(`Prediction Error: ${data.message}`);
    }
  } catch (err) {
    alert(`Failed to run prediction: ${err}`);
  } finally {
    predictBtn.disabled = false;
    predictBtn.innerHTML = '<span class="btn-icon">⚽</span><span class="btn-text">Predict Match, Goalscorers & XAI Breakdown</span>';
  }
}

function displayResults(data, homeName, awayName) {

  const resultsCard = document.getElementById('results-card');
  resultsCard.classList.remove('hidden');

  const winnerDisplay = document.getElementById('winner-display');
  winnerDisplay.innerText = data.winner_label;
  winnerDisplay.className = 'sb-winner-tag';
  if (data.winner_key === 'draw') {
    winnerDisplay.classList.add('sb-winner-tag-draw');
  } else if (data.winner_key === 'team_a') {
    winnerDisplay.classList.add('sb-winner-tag-home');
  } else if (data.winner_key === 'team_b') {
    winnerDisplay.classList.add('sb-winner-tag-away');
  }

  document.getElementById('score-home-name').innerText = homeName;
  document.getElementById('score-away-name').innerText = awayName;
  document.getElementById('score-home-xg').innerText = `xG ${data.score_prediction.projected_home_xg}`;
  document.getElementById('score-away-xg').innerText = `xG ${data.score_prediction.projected_away_xg}`;
  document.getElementById('score-projected-val').innerText = data.score_prediction.most_likely_score;

  document.getElementById('prob-home-name').innerText = `${homeName} Win`;
  document.getElementById('prob-home-val').innerText = `${data.probabilities.home}%`;
  document.getElementById('prob-home-bar').style.width = `${data.probabilities.home}%`;

  document.getElementById('prob-draw-val').innerText = `${data.probabilities.draw}%`;
  document.getElementById('prob-draw-bar').style.width = `${data.probabilities.draw}%`;

  document.getElementById('prob-away-name').innerText = `${awayName} Win`;
  document.getElementById('prob-away-val').innerText = `${data.probabilities.away}%`;
  document.getElementById('prob-away-bar').style.width = `${data.probabilities.away}%`;

  if (data.binary_mode) {
    document.getElementById('bin-home-val').innerText = `${data.binary_mode.home_win_probability}%`;
    document.getElementById('bin-home-bar').style.width = `${data.binary_mode.home_win_probability}%`;
    document.getElementById('bin-verdict').innerText = data.binary_mode.verdict;
    document.getElementById('bin-tier').innerText = data.binary_mode.confidence_tier;
  }

  // Render Redesigned XAI Tactical Driver Cards
  const xaiGrid = document.getElementById('xai-factors-list');
  xaiGrid.innerHTML = '';
  
  const featureIcons = {
    'diff_overall_mean': '👑',
    'diff_overall_max': '⭐',
    'diff_overall_min': '🛡️',
    'diff_attack_vs_defense': '⚔️',
    'diff_defense_vs_attack': '🛡️',
    'diff_midfield': '🎯',
    'diff_sub_mean': '🔄',
    'diff_depth_gap': '📉',
    'diff_market_val_log': '💰',
    'diff_form_pts_5': '📈',
    'diff_form_gd_5': '🔥',
    'diff_aerial_att_vs_def': '🪂',
    'diff_aerial_def_vs_att': '🧱',
    'diff_prime_score': '⚡',
    'diff_cohesion': '🤝',
    'league_tier_factor': '🏆'
  };

  if (data.xai_attributions && data.xai_attributions.length > 0) {
    data.xai_attributions.forEach(f => {
      const card = document.createElement('div');
      card.className = 'xai-factor-card';
      const sign = f.impact_pct >= 0 ? '+' : '';
      const badgeClass = f.is_positive ? 'xai-positive-badge' : 'xai-negative-badge';
      const icon = featureIcons[f.feature] || '⚡';
      
      let deltaDetail = `${homeName} advantage: ${f.value > 0 ? '+' : ''}${f.value}`;
      if (f.feature.includes('aerial')) deltaDetail = `Aerial mismatch: ${f.value > 0 ? '+' : ''}${f.value} cm`;
      else if (f.feature.includes('overall') || f.feature.includes('midfield')) deltaDetail = `Rating differential: ${f.value > 0 ? '+' : ''}${f.value}`;
      else if (f.feature.includes('form')) deltaDetail = `Form points delta: ${f.value > 0 ? '+' : ''}${f.value}`;

      card.innerHTML = `
        <div class="xai-factor-top">
          <div class="xai-factor-title-box">
            <span class="xai-factor-icon">${icon}</span>
            <span class="xai-factor-name">${f.name}</span>
          </div>
          <span class="xai-factor-badge ${badgeClass}">${sign}${f.impact_pct}% Impact</span>
        </div>
        <div class="xai-factor-bottom">
          <span>Tactical Delta: <strong class="xai-delta-highlight">${deltaDetail}</strong></span>
          <span>Direction: <strong style="color: ${f.is_positive ? 'var(--emerald)' : 'var(--red)'}">${f.is_positive ? 'Favors ' + homeName : 'Favors ' + awayName}</strong></span>
        </div>
      `;
      xaiGrid.appendChild(card);
    });
  }

  // Render High-Legibility Exact Scorelines Matrix
  const scoresGrid = document.getElementById('exact-scores-grid');
  scoresGrid.innerHTML = '';

  const overUnderDisplay = document.getElementById('over-under-display');
  if (overUnderDisplay && data.score_prediction.over_2_5_prob !== undefined) {
    const overPct = data.score_prediction.over_2_5_prob;
    const underPct = (100 - overPct).toFixed(1);
    overUnderDisplay.innerHTML = `Over 2.5 Goals: <strong>${overPct}%</strong> • Under: <strong>${underPct}%</strong>`;
  }

  data.score_prediction.top_scores.forEach((s, idx) => {
    const card = document.createElement('div');
    const isTop = idx === 0;
    card.className = `score-card-detailed ${isTop ? 'is-top-prediction' : ''}`;

    const ga = s.team_a_goals;
    const gb = s.team_b_goals;

    let winnerText = 'Draw Match';
    let winnerTagClass = 'winner-tag-draw';
    let barClass = 'fill-draw';

    if (ga > gb) {
      winnerText = `${homeName} Victory`;
      winnerTagClass = 'winner-tag-home';
      barClass = 'fill-home-win';
    } else if (gb > ga) {
      winnerText = `${awayName} Victory`;
      winnerTagClass = 'winner-tag-away';
      barClass = 'fill-away-win';
    }

    const rankLabel = isTop ? '🏆 Most Likely Score' : `#${idx + 1} Projected Score`;

    card.innerHTML = `
      <div class="score-card-top-bar">
        <span class="score-rank-badge">${rankLabel}</span>
        <span class="score-winner-tag ${winnerTagClass}">${winnerText}</span>
      </div>

      <div class="score-teams-matchup">
        <div class="score-team-col col-home">
          <span class="team-col-name" title="${homeName}">${homeName}</span>
          <span class="team-col-score score-home-digit">${ga}</span>
        </div>
        <span class="score-vs-divider">—</span>
        <div class="score-team-col col-away">
          <span class="team-col-name" title="${awayName}">${awayName}</span>
          <span class="team-col-score score-away-digit">${gb}</span>
        </div>
      </div>

      <div class="score-prob-meter">
        <div class="score-prob-header">
          <span class="score-prob-label">Exact Score Probability</span>
          <span class="score-prob-val">${s.prob}%</span>
        </div>
        <div class="score-track">
          <div class="score-bar-fill ${barClass}" style="width: ${Math.min(100, s.prob * 4)}%"></div>
        </div>
      </div>
    `;

    scoresGrid.appendChild(card);
  });

  document.getElementById('home-scorers-title').innerText = homeName;
  document.getElementById('away-scorers-title').innerText = awayName;

  renderScorersList('home-scorers-list', data.goalscorers.home);
  renderScorersList('away-scorers-list', data.goalscorers.away);

  const metricsList = document.getElementById('tactical-metrics-list');
  metricsList.innerHTML = '';
  data.tactical_metrics.forEach(m => {
    const total = m.home + m.away;
    const homePct = total > 0 ? ((m.home / total) * 100).toFixed(1) : 50;
    const awayPct = (100 - homePct).toFixed(1);

    const row = document.createElement('div');
    row.className = 'metric-row';
    row.innerHTML = `
      <span class="metric-name">${m.label}</span>
      <span class="metric-val-home">${m.home}</span>
      <div class="metric-bar-container">
        <div class="bar-home-portion" style="width: ${homePct}%"></div>
        <div class="bar-away-portion" style="width: ${awayPct}%"></div>
      </div>
      <span class="metric-val-away">${m.away}</span>
    `;
    metricsList.appendChild(row);
  });

  resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderScorersList(containerId, scorers) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  scorers.forEach(p => {
    const row = document.createElement('div');
    row.className = 'scorer-row';
    row.innerHTML = `
      <div class="scorer-info">
        <span class="slot-pos-badge pos-${p.pos}" style="font-size: 10px; width: 28px;">${p.pos}</span>
        <div>
          <span class="scorer-name">${p.name}</span>
          <span class="scorer-career">Rating ${p.rating} • ${p.career_goals} goals (${p.goals_per_90} G/90)</span>
        </div>
      </div>
      <span class="scorer-prob-badge">${p.anytime_prob}% Goal</span>
    `;
    container.appendChild(row);
  });
}



let lastPredictedData = null;
