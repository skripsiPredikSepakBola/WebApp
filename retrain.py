"""Safe gated retrain using shared features.py, league_tiers.py, and history_features.parquet."""
import json
import os
import joblib
import pandas as pd

from app import aggregate_team_advanced, cohesion_proxy, model_advanced_3class, advanced_features
from elo import EloTracker
from features import FEATURE_COLS, LeagueStats, TeamState, build_feature_row, is_neutral_match, mirror
from league_tiers import resolve_league_tier
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


def _seed_trackers():
    elo, leagues, teams = EloTracker(), LeagueStats(), TeamState()
    if os.path.exists(TEAM_STATE_PATH):
        with open(TEAM_STATE_PATH, 'r', encoding='utf-8') as f:
            ts = json.load(f)
        for name, v in (ts.get('by_name') or {}).items():
            elo.r[name] = float(v.get('elo', 1500.0))
            if v.get('last_date'):
                teams.last[name] = pd.Timestamp(v['last_date'])
    if os.path.exists(LEAGUE_STATE_PATH):
        with open(LEAGUE_STATE_PATH, 'r', encoding='utf-8') as f:
            ls = json.load(f)
        for cid, v in ls.items():
            leagues.n[cid] = int(v.get('n', 0))
            leagues.goals[cid] = float(v.get('goals', 0.0))
            leagues.home[cid] = float(v.get('home', 0.0))
    return elo, leagues, teams


def build_dataset(matches):
    elo, leagues, teams = _seed_trackers()
    rows = []
    prev_season = None

    for m in matches:
        hg, ag = m.get('home_goals'), m.get('away_goals')
        if hg is None or ag is None:
            continue
        ht, at = m['home_team'], m['away_team']
        lg = str(m.get('league_id') or m.get('league') or '').strip()
        dt = pd.to_datetime(m.get('match_date'), errors='coerce')
        season = m.get('season') or (dt.year if pd.notna(dt) else 2026)
        if prev_season is not None and season != prev_season:
            elo.season_regress(0.25)
        prev_season = season
        neutral = bool(m.get('neutral', False)) or is_neutral_match(lg)

        eh, ea = elo.rating(ht), elo.rating(at)
        lg_g, lg_h = leagues.get(lg)
        tier_val, _ = resolve_league_tier(lg)
        gfh, gah, rh = teams.get(ht, dt if pd.notna(dt) else None)
        gfa, gaa, ra = teams.get(at, dt if pd.notna(dt) else None)

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
                    match_id=m.get('id') or f"{m.get('match_date')}-{ht}-{at}",
                    date=str(m.get('match_date') or '')[:10],
                    season=int(season),
                )
                rows.append({**f_ab, **common, 'is_forward': 1, 'y3': y_ab, 'goals_a': float(hg), 'goals_b': float(ag)})
                rows.append({**f_ba, **common, 'is_forward': 0, 'y3': 2 - y_ab, 'goals_a': float(ag), 'goals_b': float(hg)})
            except Exception:
                pass

        # Always update Elo, league stats, and team rolling state even if lineup is missing
        elo.update(ht, at, hg, ag, neutral=neutral)
        leagues.update(lg, hg, ag)
        teams.update(ht, hg, ag, dt if pd.notna(dt) else None)
        teams.update(at, ag, hg, dt if pd.notna(dt) else None)

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

    live = _sb_req('finished_matches?select=id,home_team,away_team,home_goals,away_goals,match_date,league,raw_json&order=match_date.asc&limit=5000') or []
    live_df = build_dataset(live)
    history = pd.read_parquet(HISTORY_PATH)
    df = pd.concat([history, live_df], ignore_index=True) if live_df is not None else history
    df = df.drop_duplicates(['match_id', 'is_forward'], keep='last')

    current = joblib.load(BUNDLE_PATH) if os.path.exists(BUNDLE_PATH) else _wrap_legacy_models()
    return gated_retrain(df, FEATURE_COLS, current)


if __name__ == '__main__':
    print(json.dumps(retrain()))
