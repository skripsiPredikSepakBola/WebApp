"""Deterministic single state builder (rebuild_state.py).

Rebuilds models/team_state.json and models/league_state.json from:
  1. Immutable base state as of 2026-11-12 (models/base_state_2026-11-12.json,
     generated from Transfermarkt games.csv without season_regress to match
     history_features.parquet), plus
  2. All finished matches in Supabase with match_date > 2026-11-12, mapped to
     Transfermarkt club_id and competition_id.

Unmappable matches (e.g. youth teams or unmapped competitions) are skipped and
counted in mapping_coverage. Everything is keyed by Transfermarkt ID.
"""
from collections import deque
import json
import os
import re
import unicodedata

import numpy as np
import pandas as pd

from elo import EloTracker
from features import LeagueStats, TeamState, is_neutral_match
from league_tiers import LEAGUE_TIER_MAP, resolve_league_tier
from sync_matches import _sb_cfg, _sb_req

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(WEB_DIR, '..'))
TM_DIR = os.path.join(ROOT_DIR, 'Football Data from Transfermarkt')
GAMES_CSV = os.path.join(TM_DIR, 'games.csv')
CLUBS_CSV = os.path.join(TM_DIR, 'clubs.csv')
COMPS_CSV = os.path.join(TM_DIR, 'competitions.csv')

BASE_CUTOFF_DATE = '2026-11-12'
BASE_STATE_PATH = os.path.join(WEB_DIR, 'models', 'base_state_2026-11-12.json')
TEAM_STATE_PATH = os.path.join(WEB_DIR, 'models', 'team_state.json')
LEAGUE_STATE_PATH = os.path.join(WEB_DIR, 'models', 'league_state.json')

# Ambiguous league names shared across countries: never map via name-only fallback without a competition code.
AMBIGUOUS_COMP_SLUGS = {
    'premier league',
    'bundesliga',
    'super league',
    'liga 1',
    'superliga',
    'premier liga',
    'primera division',
    'segunda division',
    'super cup',
    'national league',
}

# Known unambiguous live competition name -> Transfermarkt competition_id overrides
LIVE_COMP_ALIASES = {
    'laliga': 'ES1',
    'la liga': 'ES1',
    'serie a': 'IT1',
    'ligue 1': 'FR1',
    'eredivisie': 'NL1',
    'liga portugal': 'PO1',
    'primeira liga': 'PO1',
    'uefa champions league': 'CL',
    'uefa europa league': 'EL',
    'uefa conference league': 'UCOL',
    'uefa nations league a': 'UNLA',
    'uefa nations league b': 'UNLB',
    'uefa nations league c': 'UNLC',
    'uefa nations league d': 'UNLD',
    'world cup': 'FIWC',
    'euro': 'EURO',
    'copa america': 'COPA',
    'liga 1 indonesia': 'IN1L',
    'bri liga 1': 'IN1L',
    'indonesia super league': 'IN1L',
    'malaysia super league': 'MYS1',
    'thai league 1': 'THA1',
    'v.league 1': 'VIE1',
    'singapore premier league': 'SIN1',
}


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
    return s


def build_base_state_from_games(cutoff_date=BASE_CUTOFF_DATE, save_path=BASE_STATE_PATH):
    """Build immutable 2026-11-12 base state from Transfermarkt CSVs (matches history_features.parquet)."""
    games = pd.read_csv(
        GAMES_CSV,
        usecols=['game_id', 'season', 'competition_id', 'round', 'date',
                 'home_club_id', 'away_club_id', 'home_club_name', 'away_club_name',
                 'home_club_goals', 'away_club_goals'],
    )
    for col in ('game_id', 'season', 'home_club_id', 'away_club_id', 'home_club_goals', 'away_club_goals'):
        games[col] = pd.to_numeric(games[col], errors='coerce')
    games['date'] = pd.to_datetime(games['date'], errors='coerce')
    games = games.dropna(subset=[
        'game_id', 'season', 'date', 'home_club_id', 'away_club_id',
        'home_club_goals', 'away_club_goals',
    ]).drop_duplicates(subset=['game_id'], keep='last').copy()
    for col in ('game_id', 'season', 'home_club_id', 'away_club_id'):
        games[col] = games[col].astype(np.int64)
    games = games[games['date'] <= pd.Timestamp(cutoff_date)]
    games = games.sort_values(['date', 'game_id'], kind='mergesort').reset_index(drop=True)

    club_names = {}
    club_name_to_id = {}
    if os.path.exists(CLUBS_CSV):
        cdf = pd.read_csv(CLUBS_CSV, usecols=['club_id', 'name'])
        for _, r in cdf.dropna().iterrows():
            cid = int(r['club_id'])
            nm = str(r['name']).strip()
            club_names[cid] = nm
            club_name_to_id.setdefault(_norm(nm), cid)

    comp_conf, comp_name_to_id = {}, dict(LIVE_COMP_ALIASES)
    if os.path.exists(COMPS_CSV):
        comps = pd.read_csv(COMPS_CSV, usecols=['competition_id', 'name', 'confederation'])
        for _, r in comps.dropna(subset=['competition_id']).iterrows():
            cid = str(r['competition_id']).strip()
            if pd.notna(r.get('confederation')):
                comp_conf[cid] = str(r['confederation']).strip()
            if pd.notna(r.get('name')):
                comp_name_to_id.setdefault(_norm(r['name']), cid)
            comp_name_to_id.setdefault(_norm(cid), cid)
    for cid in LEAGUE_TIER_MAP:
        comp_name_to_id.setdefault(_norm(cid), cid)

    elo, leagues, teams = EloTracker(), LeagueStats(), TeamState()
    all_cids = set()
    for r in games.itertuples(index=False):
        hid, aid = int(r.home_club_id), int(r.away_club_id)
        if pd.notna(r.home_club_name):
            hn = str(r.home_club_name).strip()
            club_names.setdefault(hid, hn)
            club_name_to_id.setdefault(_norm(hn), hid)
        if pd.notna(r.away_club_name):
            an = str(r.away_club_name).strip()
            club_names.setdefault(aid, an)
            club_name_to_id.setdefault(_norm(an), aid)

        cid = str(r.competition_id or '').strip()
        all_cids.add(cid)
        neutral = is_neutral_match(cid, r.round)
        elo.update(hid, aid, r.home_club_goals, r.away_club_goals, neutral=neutral)
        leagues.update(cid, r.home_club_goals, r.away_club_goals)
        teams.update(hid, r.home_club_goals, r.away_club_goals, r.date)
        teams.update(aid, r.away_club_goals, r.home_club_goals, r.date)

    teams_out = {}
    for tid, rating in elo.r.items():
        last_dt = teams.last.get(tid)
        teams_out[str(tid)] = {
            'name': club_names.get(tid, ''),
            'elo': float(rating),
            'last10': [[int(gf), int(ga)] for gf, ga in teams.hist[tid]],
            'last_date': last_dt.strftime('%Y-%m-%d') if last_dt is not None else None,
        }

    leagues_out = {}
    for cid in sorted(all_cids):
        tier_v, known = resolve_league_tier(cid, comp_conf.get(cid))
        leagues_out[cid] = {
            'n': int(leagues.n[cid]),
            'goals': float(leagues.goals[cid]),
            'home': float(leagues.home[cid]),
            'tier': tier_v,
            'tier_known': known,
        }

    base = {
        'as_of': cutoff_date,
        'teams': teams_out,
        'leagues': leagues_out,
        'club_name_to_id': club_name_to_id,
        'comp_name_to_id': comp_name_to_id,
    }
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(base, f)
    return base


def load_trackers_from_base(base):
    """Hydrate EloTracker, TeamState, LeagueStats from base_state dict."""
    elo, leagues, teams = EloTracker(), LeagueStats(), TeamState()
    club_names = {}
    for tid_s, v in (base.get('teams') or {}).items():
        tid = int(tid_s)
        elo.r[tid] = float(v.get('elo', 1500.0))
        teams.hist[tid] = deque([(int(g[0]), int(g[1])) for g in (v.get('last10') or [])], maxlen=10)
        if v.get('last_date'):
            teams.last[tid] = pd.Timestamp(v['last_date'])
        if v.get('name'):
            club_names[tid] = str(v['name']).strip()

    league_meta = {}
    for cid, v in (base.get('leagues') or {}).items():
        leagues.n[cid] = int(v.get('n', 0))
        leagues.goals[cid] = float(v.get('goals', 0.0))
        leagues.home[cid] = float(v.get('home', 0.0))
        league_meta[cid] = {'tier': v.get('tier', 0.90), 'tier_known': bool(v.get('tier_known', False))}

    return elo, leagues, teams, club_names, league_meta


def map_match_ids(match, club_name_to_id, comp_name_to_id, known_cids=None):
    """Map a live Supabase match row to (home_club_id, away_club_id, competition_id) or Nones."""
    raw = match.get('raw_json') or {}
    hid = None
    aid = None
    cid = ''

    # 1. Transfermarkt API raw_json carries exact clubId and competition code
    if isinstance(raw, dict):
        hc = raw.get('homeClub') or {}
        ac = raw.get('awayClub') or {}
        if isinstance(hc, dict) and hc.get('clubId') is not None:
            try:
                hid = int(hc['clubId'])
            except (TypeError, ValueError):
                hid = None
        if isinstance(ac, dict) and ac.get('clubId') is not None:
            try:
                aid = int(ac['clubId'])
            except (TypeError, ValueError):
                aid = None
        bd = raw.get('baseDetails') or {}
        if isinstance(bd, dict):
            cid = str(bd.get('competition') or bd.get('competitionId') or '').strip()

    # 2. Fallback to normalized club & competition name lookup
    if hid is None:
        hid = club_name_to_id.get(_norm(match.get('home_team')))
    if aid is None:
        aid = club_name_to_id.get(_norm(match.get('away_team')))
    if not cid:
        lg_raw = str(match.get('league') or '').strip()
        lg_norm = _norm(lg_raw)
        if known_cids and lg_raw in known_cids:
            cid = lg_raw
        elif lg_norm in AMBIGUOUS_COMP_SLUGS:
            cid = ''
        else:
            cid = LIVE_COMP_ALIASES.get(lg_norm) or comp_name_to_id.get(lg_norm, '')

    if hid is None or aid is None or not cid:
        return None, None, None
    return hid, aid, cid


def fetch_finished_matches_paginated(after_date=BASE_CUTOFF_DATE, page_size=1000, max_pages=100, req_fn=None):
    """Fetch all finished matches after after_date using deterministic pagination, failing loudly on truncation."""
    req_fn = req_fn or _sb_req
    out = []
    for page in range(max_pages):
        batch = req_fn(
            f'finished_matches?select=match_id,home_team,away_team,home_goals,away_goals,match_date,league,raw_json'
            f'&match_date=gt.{after_date}&order=match_date.asc,match_id.asc'
            f'&limit={page_size}&offset={page * page_size}'
        ) or []
        if len(batch) > page_size:
            raise RuntimeError(f'Page returned {len(batch)} > page_size={page_size}')
        out.extend(batch)
        if len(batch) < page_size:
            return out
    raise RuntimeError(f'Pagination cap hit ({max_pages * page_size} matches); refusing silent truncation')


def rebuild(matches=None, base_path=BASE_STATE_PATH, write_files=True):
    """Deterministically rebuild team_state.json and league_state.json from base_state + all > 2026-11-12 matches."""
    with open(base_path, 'r', encoding='utf-8') as f:
        base = json.load(f)

    if matches is None:
        url, _ = _sb_cfg()
        if not url:
            return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}
        matches = fetch_finished_matches_paginated(after_date=BASE_CUTOFF_DATE)

    elo, leagues, teams, club_names, league_meta = load_trackers_from_base(base)
    club_name_to_id = base.get('club_name_to_id') or {}
    comp_name_to_id = base.get('comp_name_to_id') or {}
    known_cids = set(league_meta.keys()) | set(LEAGUE_TIER_MAP.keys())

    dedup = {}
    for m in matches:
        mid = m.get('match_id') or m.get('id')
        dt_str = str(m.get('match_date') or '')[:10]
        if mid and dt_str > BASE_CUTOFF_DATE and m.get('home_goals') is not None and m.get('away_goals') is not None:
            dedup[str(mid)] = (dt_str, str(mid), m)

    max_date = base.get('as_of', BASE_CUTOFF_DATE)
    mapped_count, skipped_unmapped = 0, 0

    for dt_str, _, m in sorted(dedup.values(), key=lambda x: (x[0], x[1])):
        hid, aid, cid = map_match_ids(m, club_name_to_id, comp_name_to_id, known_cids=known_cids)
        if hid is None or aid is None or cid is None:
            skipped_unmapped += 1
            continue

        hg, ag = int(m['home_goals']), int(m['away_goals'])
        dt = pd.to_datetime(dt_str, errors='coerce')
        neutral = is_neutral_match(cid)
        elo.update(hid, aid, hg, ag, neutral=neutral)
        leagues.update(cid, hg, ag)
        if pd.notna(dt):
            teams.update(hid, hg, ag, dt)
            teams.update(aid, ag, hg, dt)
            max_date = max(max_date, dt_str)
        club_names.setdefault(hid, str(m.get('home_team') or '').strip())
        club_names.setdefault(aid, str(m.get('away_team') or '').strip())
        mapped_count += 1

    ref_dt = pd.Timestamp(max_date)
    by_id, by_name = {}, {}
    for tid, rating in sorted(elo.r.items()):
        gf, ga, _ = teams.get(tid, ref_dt)
        last_dt = teams.last.get(tid)
        entry = {
            'elo': round(float(rating), 2),
            'gf10': round(float(gf), 4),
            'ga10': round(float(ga), 4),
            'last_date': last_dt.strftime('%Y-%m-%d') if last_dt is not None else None,
        }
        by_id[str(tid)] = entry
        nm = club_names.get(tid)
        if nm:
            by_name.setdefault(nm, entry)
            by_name.setdefault(nm.lower(), entry)

    ts_out = {
        'as_of': max_date,
        'by_id': by_id,
        'by_name': by_name,
        'mapping_stats': {
            'total_post_cutoff': len(dedup),
            'mapped': mapped_count,
            'skipped_unmapped': skipped_unmapped,
            'coverage': round(mapped_count / max(len(dedup), 1), 4),
        },
    }

    lg_out = {}
    for cid in sorted(set(leagues.n.keys()) | set(league_meta.keys())):
        avg_g, home_w = leagues.get(cid)
        meta = league_meta.get(cid)
        if meta is None:
            tier_v, known = resolve_league_tier(cid)
        else:
            tier_v, known = meta['tier'], meta['tier_known']
        lg_out[cid] = {
            'n': int(leagues.n[cid]),
            'goals': float(leagues.goals[cid]),
            'home': float(leagues.home[cid]),
            'avg_goals': round(float(avg_g), 4),
            'home_win': round(float(home_w), 4),
            'tier': tier_v,
            'tier_known': known,
        }

    if write_files:
        with open(TEAM_STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(ts_out, f)
        with open(LEAGUE_STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(lg_out, f, indent=2)

    return {
        'status': 'rebuilt',
        'as_of': max_date,
        'total_post_cutoff': len(dedup),
        'mapped_matches': mapped_count,
        'skipped_unmapped': skipped_unmapped,
        'mapping_coverage': ts_out['mapping_stats']['coverage'],
    }


if __name__ == '__main__':
    print(json.dumps(rebuild()))
