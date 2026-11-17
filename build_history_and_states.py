"""Build frozen history_features.parquet, team_state.json, league_state.json, and model_meta.json."""
import json
import os
import platform
import time

import numpy as np
import pandas as pd
import sklearn

from elo import EloTracker
from features import FEATURE_COLS, LeagueStats, TeamState, is_neutral_match
from league_tiers import LEAGUE_TIER_MAP, resolve_league_tier
from retrain_gate import CLF_PARAMS, FIXED_BLEND_W, REG_PARAMS

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(WEB_DIR, '..'))
TM_DIR = os.path.join(ROOT_DIR, 'Football Data from Transfermarkt')
GAMES_CSV = os.path.join(TM_DIR, 'games.csv')
CLUBS_CSV = os.path.join(TM_DIR, 'clubs.csv')
COMPS_CSV = os.path.join(TM_DIR, 'competitions.csv')
V2_PARQUET = os.path.join(ROOT_DIR, 'match_features_v2.parquet')


def main():
    os.makedirs(os.path.join(WEB_DIR, 'data'), exist_ok=True)
    os.makedirs(os.path.join(WEB_DIR, 'models'), exist_ok=True)

    # 1. Build team_state.json and league_state.json over EVERY finished match (with or without lineups)
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
    games = games.sort_values(['date', 'game_id'], kind='mergesort').reset_index(drop=True)

    club_names = {}
    if os.path.exists(CLUBS_CSV):
        cdf = pd.read_csv(CLUBS_CSV, usecols=['club_id', 'name'])
        for _, r in cdf.dropna().iterrows():
            club_names[int(r['club_id'])] = str(r['name']).strip()

    comp_conf = {}
    if os.path.exists(COMPS_CSV):
        comps = pd.read_csv(COMPS_CSV, usecols=['competition_id', 'confederation'])
        for _, r in comps.dropna().iterrows():
            comp_conf[str(r['competition_id']).strip()] = str(r['confederation']).strip()

    elo, leagues, teams = EloTracker(), LeagueStats(), TeamState()
    prev_season = None
    all_cids = set()

    for r in games.itertuples(index=False):
        if prev_season is not None and r.season != prev_season:
            elo.season_regress(0.25)
        prev_season = r.season

        hid, aid = int(r.home_club_id), int(r.away_club_id)
        if pd.notna(r.home_club_name) and hid not in club_names:
            club_names[hid] = str(r.home_club_name).strip()
        if pd.notna(r.away_club_name) and aid not in club_names:
            club_names[aid] = str(r.away_club_name).strip()

        cid = str(r.competition_id or '').strip()
        all_cids.add(cid)
        neutral = is_neutral_match(cid, r.round)
        elo.update(hid, aid, r.home_club_goals, r.away_club_goals, neutral=neutral)
        leagues.update(cid, r.home_club_goals, r.away_club_goals)
        teams.update(hid, r.home_club_goals, r.away_club_goals, r.date)
        teams.update(aid, r.away_club_goals, r.home_club_goals, r.date)

    ref_date = games['date'].max()
    by_id, by_name = {}, {}
    for tid, rating in elo.r.items():
        gf, ga, _ = teams.get(tid, ref_date)
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
            by_name[nm] = entry
            by_name[nm.lower()] = entry

    with open(os.path.join(WEB_DIR, 'models', 'team_state.json'), 'w', encoding='utf-8') as f:
        json.dump({'as_of': ref_date.strftime('%Y-%m-%d'), 'by_id': by_id, 'by_name': by_name}, f)

    lg_out = {}
    for cid in sorted(all_cids):
        avg_g, home_w = leagues.get(cid)
        tier_v, known = resolve_league_tier(cid, comp_conf.get(cid))
        lg_out[cid] = {
            'n': int(leagues.n[cid]),
            'goals': float(leagues.goals[cid]),
            'home': float(leagues.home[cid]),
            'avg_goals': round(float(avg_g), 4),
            'home_win': round(float(home_w), 4),
            'tier': tier_v,
            'tier_known': known,
        }
    with open(os.path.join(WEB_DIR, 'models', 'league_state.json'), 'w', encoding='utf-8') as f:
        json.dump(lg_out, f, indent=2)

    # 2. Save frozen history_features.parquet (25 FEATURE_COLS + keys)
    v2 = pd.read_parquet(V2_PARQUET)
    keep = ['match_id', 'date', 'season', 'competition_id', 'is_forward', 'y3', 'goals_a', 'goals_b'] + FEATURE_COLS
    hist = v2[keep].copy()
    hist['date'] = pd.to_datetime(hist['date']).dt.strftime('%Y-%m-%d')
    hist.to_parquet(os.path.join(WEB_DIR, 'data', 'history_features.parquet'), index=False)

    # 3. Write freeze record in models/model_meta.json
    meta = {
        'freeze_date': '2026-11-17',
        'feature_set': 'G6+tier',
        'features': list(FEATURE_COLS),
        'n_features': len(FEATURE_COLS),
        'clf_params': CLF_PARAMS,
        'reg_params': REG_PARAMS,
        'blend_w': FIXED_BLEND_W,
        'rho_procedure': 'grid_search(-0.25..0.10, 36 pts) on chronological tune slice',
        'tier_map_source': 'league_tiers.py (0.75-1.00 hand-set league-quality prior)',
        'known_limitations': [
            'UEFA continental competitions show ~-0.034 home_gap (higher ~49-51% actual home win rate vs 0.45 domestic prior; k=50+is_continental variant failed UEFA bootstrap p5=-0.00048).',
            'Test-fold selection caveat: G6+tier selected on 2023-2026 folds; prospective check must evaluate on matches played after freeze_date.',
        ],
        'sklearn_version': sklearn.__version__,
        'numpy_version': np.__version__,
        'python_version': platform.python_version(),
        'history_matches': int(hist['match_id'].nunique()),
        'team_state_count': len(by_id),
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    with open(os.path.join(WEB_DIR, 'models', 'model_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)

    print(f"Saved history_features.parquet ({len(hist)} rows, {hist['match_id'].nunique()} matches), "
          f"team_state.json ({len(by_id)} teams), league_state.json ({len(lg_out)} leagues), model_meta.json.")


if __name__ == '__main__':
    main()
