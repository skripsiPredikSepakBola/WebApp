"""Safe gated retrain using shared features.py, league_tiers.py, and history_features.parquet."""
import json
import os
import joblib
import pandas as pd

from app import aggregate_team_advanced, cohesion_proxy, model_advanced_3class, advanced_features
from features import FEATURE_COLS, build_feature_row, is_neutral_match, mirror
from league_tiers import LEAGUE_TIER_MAP, resolve_league_tier
from rebuild_state import (
    BASE_CUTOFF_DATE,
    BASE_STATE_PATH,
    fetch_finished_matches_paginated,
    load_trackers_from_base,
    map_match_ids,
)
from retrain_gate import BUNDLE_PATH, retrain as gated_retrain
from sync_matches import _sb_cfg, _sb_req

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.environ.get('HISTORY_FEATURES_PATH', os.path.join(BASE_DIR, 'data', 'history_features.parquet'))
TEAM_STATE_PATH = os.path.join(BASE_DIR, 'models', 'team_state.json')
LEAGUE_STATE_PATH = os.path.join(BASE_DIR, 'models', 'league_state.json')

_POS_MAP = {
    'G': 'GK', 'GK': 'GK', 'GOALKEEPER': 'GK',
    'D': 'DEF', 'DEF': 'DEF', 'DEFENDER': 'DEF',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF', 'LCB': 'DEF', 'RCB': 'DEF', 'LWB': 'DEF', 'RWB': 'DEF',
    'M': 'MID', 'MID': 'MID', 'MIDFIELDER': 'MID', 'MIDFIELD': 'MID',
    'CM': 'MID', 'DM': 'MID', 'AM': 'MID', 'LM': 'MID', 'RM': 'MID',
    'F': 'ATT', 'ATT': 'ATT', 'ATTACK': 'ATT', 'ATTACKER': 'ATT', 'STRIKER': 'ATT', 'FORWARD': 'ATT',
    'CF': 'ATT', 'LW': 'ATT', 'RW': 'ATT', 'SS': 'ATT',
}


def _norm_pos(val):
    return _POS_MAP.get(str(val or '').strip().upper(), 'MID')


def _tm_player(p):
    pos_obj = p.get('position') or {}
    slot_pos = _norm_pos(pos_obj.get('category') or pos_obj.get('shortName'))
    item = {'slot_pos': slot_pos}
    pid = p.get('id')
    if pid is not None and str(pid).isdigit():
        item['id'] = int(pid)
    if p.get('name'):
        item['name'] = p['name']
    return item


def _extract_lineups(raw):
    lineups = raw.get('lineups') or []
    if len(lineups) >= 2:
        home_id = (raw.get('teams') or {}).get('home', {}).get('id')
        h_lu = next((x for x in lineups if (x.get('team') or {}).get('id') == home_id), lineups[0])
        a_lu = next((x for x in lineups if x is not h_lu), lineups[1])
        to_af = lambda arr: [{
            'name': (p.get('player') or {}).get('name', ''),
            'slot_pos': _norm_pos((p.get('player') or {}).get('pos')),
        } for p in (arr or [])]
        hs, as_ = to_af(h_lu.get('startXI')), to_af(a_lu.get('startXI'))
        if len(hs) >= 7 and len(as_) >= 7:
            return hs, to_af(h_lu.get('substitutes')), as_, to_af(a_lu.get('substitutes'))

    hc_lu = (raw.get('homeClub') or {}).get('lineup') or {}
    ac_lu = (raw.get('awayClub') or {}).get('lineup') or {}
    if hc_lu and ac_lu:
        hs = [_tm_player(p) for p in (hc_lu.get('players') or [])]
        as_ = [_tm_player(p) for p in (ac_lu.get('players') or [])]
        if len(hs) >= 7 and len(as_) >= 7:
            hb = [_tm_player(p) for p in (hc_lu.get('substitutes') or [])]
            ab = [_tm_player(p) for p in (ac_lu.get('substitutes') or [])]
            return hs, hb, as_, ab
    return None


def _seed_trackers(base_path=BASE_STATE_PATH):
    with open(base_path, 'r', encoding='utf-8') as f:
        base = json.load(f)
    elo, leagues, teams, _, _ = load_trackers_from_base(base)
    return elo, leagues, teams


def build_dataset(matches, base_path=BASE_STATE_PATH):
    with open(base_path, 'r', encoding='utf-8') as f:
        base = json.load(f)
    elo, leagues, teams = _seed_trackers(base_path=base_path)
    club_name_to_id = base.get('club_name_to_id') or {}
    comp_name_to_id = base.get('comp_name_to_id') or {}
    known_cids = set((base.get('leagues') or {}).keys()) | set(LEAGUE_TIER_MAP.keys())
    rows = []

    dedup = {}
    for idx, m in enumerate(matches):
        if m.get('home_goals') is None or m.get('away_goals') is None:
            continue
        mid = str(m.get('match_id') or m.get('id') or f'row_{idx}')
        dt_str = str(m.get('match_date') or '')[:10]
        if dt_str and dt_str <= BASE_CUTOFF_DATE:
            continue
        dedup[mid] = (dt_str, mid, m)

    for dt_str, mid, m in sorted(dedup.values(), key=lambda x: (x[0], x[1])):
        hid, aid, cid = map_match_ids(m, club_name_to_id, comp_name_to_id, known_cids=known_cids)
        if hid is None or aid is None or cid is None:
            continue

        hg, ag = int(m['home_goals']), int(m['away_goals'])
        ht, at = str(m.get('home_team') or '').strip(), str(m.get('away_team') or '').strip()
        dt = pd.to_datetime(dt_str or m.get('match_date'), errors='coerce')
        season = m.get('season') or (dt.year if pd.notna(dt) else 2026)
        neutral = bool(m.get('neutral', False)) or is_neutral_match(cid)

        eh, ea = elo.rating(hid), elo.rating(aid)
        lg_g, lg_h = leagues.get(cid)
        tier_val, _ = resolve_league_tier(cid)
        gfh, gah, rh = teams.get(hid, dt if pd.notna(dt) else None)
        gfa, gaa, ra = teams.get(aid, dt if pd.notna(dt) else None)

        lu = _extract_lineups(m.get('raw_json') or {})
        if lu:
            hs, hb, as_, ab = lu
            try:
                sa, st_a, _ = aggregate_team_advanced(hs, hb, ht)
                sb, st_b, _ = aggregate_team_advanced(as_, ab, at)
                f_ab = build_feature_row(
                    sa, sb, cohesion_proxy(st_a), cohesion_proxy(st_b),
                    eh, ea, gfh, gah, rh, gfa, gaa, ra,
                    (gfh - gah) - (gfa - gaa),
                    lg_g, lg_h, tier_val, neutral=neutral,
                )
                f_ba = mirror(f_ab)
                y_ab = 2 if hg > ag else (1 if hg == ag else 0)
                common = dict(
                    match_id=m.get('match_id') or m.get('id') or f"{dt_str}-{hid}-{aid}",
                    date=dt_str,
                    season=int(season),
                    competition_id=cid,
                )
                rows.append({**f_ab, **common, 'is_forward': 1, 'y3': y_ab, 'goals_a': float(hg), 'goals_b': float(ag)})
                rows.append({**f_ba, **common, 'is_forward': 0, 'y3': 2 - y_ab, 'goals_a': float(ag), 'goals_b': float(hg)})
            except Exception:
                pass

        # Always update Elo, league stats, and team rolling state (keyed by Transfermarkt ID) even if lineup is missing
        elo.update(hid, aid, hg, ag, neutral=neutral)
        leagues.update(cid, hg, ag)
        if pd.notna(dt):
            teams.update(hid, hg, ag, dt)
            teams.update(aid, ag, hg, dt)

    return pd.DataFrame(rows) if rows else None


def _wrap_legacy_models():
    return {
        'clf': model_advanced_3class,
        'reg': None,
        'rho': 0.0,
        'blend_w': 0.0,
        'feats': list(advanced_features),
    }


def retrain():
    url, _ = _sb_cfg()
    if not url:
        return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}
    if not os.path.exists(HISTORY_PATH):
        return {'status': 'skipped', 'reason': f'missing {HISTORY_PATH}'}

    live = fetch_finished_matches_paginated(after_date=BASE_CUTOFF_DATE)
    live_df = build_dataset(live)
    history = pd.read_parquet(HISTORY_PATH)
    df = pd.concat([history, live_df], ignore_index=True) if live_df is not None else history
    df = df.drop_duplicates(['match_id', 'is_forward'], keep='last')

    current = joblib.load(BUNDLE_PATH) if os.path.exists(BUNDLE_PATH) else _wrap_legacy_models()
    return gated_retrain(df, FEATURE_COLS, current)


if __name__ == '__main__':
    print(json.dumps(retrain()))
