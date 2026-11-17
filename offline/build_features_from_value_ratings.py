"""Rebuild the 16 model features using point-in-time market-value player ratings.

Computes all 16 features directly from Transfermarkt CSVs + players_lite.json
for every finished match in games.csv (including SEA 2020-2026 leagues and
post-July-2026 global matches) without relying on match_features_advanced.csv.

Point-in-time & zero-leakage guarantees:
- Player market value and value-derived rating at match date T come strictly
  from the last valuation dated <= T via pd.merge_asof(..., direction='backward').
- Player age at match date T is computed from date_of_birth and match date T.
- 5-match rolling form (points/game, goal diff/game) is strictly shifted by 1
  match per club so a match's own outcome never enters its own features.
- Cohesion (club continuity) counts prior starting appearances for that club
  strictly before the current match.
"""
import json
import os

import numpy as np
import pandas as pd

import build_value_ratings as bvr

GAMES = 'Football Data from Transfermarkt/games.csv'
LINEUPS = 'Football Data from Transfermarkt/game_lineups.csv'
VALUATIONS = 'Football Data from Transfermarkt/player_valuations.csv'
PLAYERS_CSV = 'Football Data from Transfermarkt/players.csv'
COMPETITIONS_CSV = 'Football Data from Transfermarkt/competitions.csv'
OUT = 'match_features_value.csv'

# Transfermarkt's detailed positions collapse to the four lines the features use.
POSITION_LINE = {
    'Goalkeeper': 'GK',
    'Centre-Back': 'DEF', 'Left-Back': 'DEF', 'Right-Back': 'DEF', 'Defender': 'DEF',
    'Defensive Midfield': 'MID', 'Central Midfield': 'MID', 'Attacking Midfield': 'MID',
    'Left Midfield': 'MID', 'Right Midfield': 'MID', 'Midfield': 'MID',
    'Centre-Forward': 'ATT', 'Left Winger': 'ATT', 'Right Winger': 'ATT',
    'Second Striker': 'ATT', 'Attack': 'ATT',
}

MODEL_FEATURES = [
    'diff_overall_mean', 'diff_overall_max', 'diff_overall_min',
    'diff_attack_vs_defense', 'diff_defense_vs_attack', 'diff_midfield',
    'diff_sub_mean', 'diff_depth_gap', 'diff_market_val_log',
    'diff_form_pts_5', 'diff_form_gd_5', 'diff_aerial_att_vs_def',
    'diff_aerial_def_vs_att', 'diff_prime_score', 'diff_cohesion',
    'league_tier_factor',
]

PRIME_AGE = 27.0

# Competition tier strength map:
# Top 5 EU + UCL = 1.00, other EU / top Americas / major Int = 0.85..0.95,
# SEA / Asian domestic leagues = 0.75..0.80.
LEAGUE_TIER_MAP = {
    # Top 5 European leagues + UEFA Champions League
    'GB1': 1.00, 'ES1': 1.00, 'L1': 1.00, 'IT1': 1.00, 'FR1': 1.00, 'CL': 1.00,
    # Major international tournaments & strong European/Americas tiers
    'FIWC': 0.95, 'EURO': 0.95, 'COPA': 0.92, 'EL': 0.92, 'USC': 0.92,
    'PO1': 0.90, 'NL1': 0.90, 'BRA1': 0.90,
    'FAC': 0.90, 'CDR': 0.90, 'DFB': 0.90, 'CIT': 0.90,
    'GBCS': 0.90, 'SUC': 0.90, 'DFL': 0.90, 'FRCH': 0.90, 'SCI': 0.90,
    'UCOL': 0.88, 'ARG1': 0.88, 'BE1': 0.87, 'TR1': 0.87,
    'SC1': 0.85, 'MEX1': 0.85, 'MLS1': 0.85, 'COL1': 0.85,
    'RU1': 0.85, 'UKR1': 0.85, 'DK1': 0.85, 'A1': 0.85, 'C1': 0.85,
    'GR1': 0.85, 'NO1': 0.85, 'SE1': 0.85, 'PL1': 0.85, 'TS1': 0.85,
    'KR1': 0.85, 'RO1': 0.85, 'SER1': 0.85, 'AFAC': 0.85, 'AFCN': 0.85,
    'CLQ': 0.85, 'ELQ': 0.85, 'ECLQ': 0.85, 'KLUB': 0.85,
    'NLP': 0.85, 'RUP': 0.85, 'DKP': 0.85, 'GRP': 0.85, 'SFA': 0.85,
    'POCP': 0.85, 'UKRP': 0.85, 'BESC': 0.85, 'NLSC': 0.85, 'POSU': 0.85,
    'RUSS': 0.85, 'UKRS': 0.85, 'BPO4': 0.85, 'EJPL': 0.85, 'POBE': 0.85,
    'CGB': 0.85,
    # Asian & Southeast Asian (SEA) leagues
    'SA1': 0.80, 'JAP1': 0.80, 'RSK1': 0.80, 'AUS1': 0.78,
    'THA1': 0.78, 'MYS1': 0.77, 'IN1L': 0.76, 'VIE1': 0.76, 'SIN1': 0.75,
}


def load_reference_and_players():
    """Load unique-player value-rating reference CDFs and combined player metadata."""
    pl = pd.DataFrame(json.load(open(bvr.PLAYERS_LITE, encoding='utf-8')))
    pl = pl.rename(columns={'rating': 'ref_rating'})
    vals = bvr.latest_valuations()
    ref_df = pl.merge(vals[['id', 'val_latest']], on='id', how='left')
    ref_df['val_latest'] = ref_df['val_latest'].fillna(ref_df['val']).fillna(0.0)

    interp_ref = {}
    for pos, grp in ref_df.groupby('pos'):
        lv = np.sort(np.log1p(grp['val_latest'].clip(lower=0).values))
        fr = np.sort(grp['ref_rating'].dropna().values)
        if len(lv) > 0 and len(fr) >= 50:
            interp_ref[pos] = (lv, fr)

    if 'MID' not in interp_ref:
        lv = np.sort(np.log1p(ref_df['val_latest'].clip(lower=0).values))
        fr = np.sort(ref_df['ref_rating'].dropna().values)
        interp_ref['MID'] = (lv, fr)

    pcsv = pd.read_csv(
        PLAYERS_CSV,
        usecols=['player_id', 'date_of_birth', 'height_in_cm', 'position', 'sub_position'],
    ).drop_duplicates(subset=['player_id'], keep='last')
    pcsv['dob'] = pd.to_datetime(pcsv['date_of_birth'], errors='coerce')
    pos_map = {'Goalkeeper': 'GK', 'Defender': 'DEF', 'Midfield': 'MID', 'Attack': 'ATT'}
    pcsv['pos_csv'] = pcsv['position'].map(pos_map)
    pcsv['pos_sub'] = pcsv['sub_position'].map(POSITION_LINE)
    pcsv['pos_csv'] = pcsv['pos_csv'].fillna(pcsv['pos_sub'])

    pl_sub = pl[['id', 'pos', 'height', 'age']].rename(columns={'id': 'player_id'})
    pm = pcsv.merge(pl_sub, on='player_id', how='outer')
    pm['pos'] = pm['pos_csv'].fillna(pm['pos'])
    pm['height'] = pd.to_numeric(pm['height_in_cm'], errors='coerce').fillna(
        pd.to_numeric(pm['height'], errors='coerce')
    )
    pos_h_med = pm.groupby('pos')['height'].transform('median')
    pm['height'] = pm['height'].fillna(pos_h_med).fillna(182.0)
    pm['age'] = pd.to_numeric(pm['age'], errors='coerce')
    pm['player_id'] = pd.to_numeric(pm['player_id'], errors='coerce')
    pm = pm.dropna(subset=['player_id']).copy()
    pm['player_id'] = pm['player_id'].astype(np.int64)

    return interp_ref, pm[['player_id', 'pos', 'height', 'dob', 'age']]


def _pit_value_ratings(lu, interp_ref):
    """Map point-in-time market values and ages to the 52-97 FIFA rating scale."""
    ratings = np.empty(len(lu), dtype=float)
    pos_series = lu['pos'].fillna('MID')
    for pos, idx in lu.groupby(pos_series).groups.items():
        lv_ref, fr_ref = interp_ref.get(pos, interp_ref['MID'])
        lv = np.log1p(lu.loc[idx, 'pit_val'].clip(lower=0).values)
        left = np.searchsorted(lv_ref, lv, side='left')
        right = np.searchsorted(lv_ref, lv, side='right')
        pct = np.clip(0.5 * (left + right) / len(lv_ref), 0.0, 1.0)
        target = np.quantile(fr_ref, pct)
        ratings[idx] = target + bvr.age_correction(lu.loc[idx, 'pit_age'].values)
    return np.clip(ratings, bvr.RATING_FLOOR, bvr.RATING_CEIL).round(1)


def pit_lineups(players, games, interp_ref):
    """Build lineup rows with point-in-time valuations, ratings, and prior club starts."""
    lu = pd.read_csv(LINEUPS, usecols=['game_id', 'club_id', 'player_id', 'type', 'position'])
    for col in ('game_id', 'club_id', 'player_id'):
        lu[col] = pd.to_numeric(lu[col], errors='coerce')
    lu = lu.dropna(subset=['game_id', 'club_id', 'player_id']).copy()
    for col in ('game_id', 'club_id', 'player_id'):
        lu[col] = lu[col].astype(np.int64)

    lu = lu.drop_duplicates(subset=['game_id', 'club_id', 'player_id', 'type'])
    lu['line'] = lu['position'].map(POSITION_LINE)

    lu = lu.merge(games[['game_id', 'date']], on='game_id', how='inner')
    lu = lu.sort_values(['date', 'game_id'], kind='mergesort').reset_index(drop=True)

    # Continuity cohesion: number of prior starting appearances for this club
    # strictly before the current match.
    st_mask = lu['type'] == 'starting_lineup'
    st_ord = lu.loc[st_mask, ['club_id', 'player_id', 'date', 'game_id']].sort_values(
        ['club_id', 'player_id', 'date', 'game_id'], kind='mergesort'
    )
    lu['prior_starts'] = 0.0
    lu.loc[st_ord.index, 'prior_starts'] = st_ord.groupby(
        ['club_id', 'player_id'], sort=False
    ).cumcount().astype(float)

    v = pd.read_csv(VALUATIONS, usecols=['player_id', 'date', 'market_value_in_eur'])
    v['player_id'] = pd.to_numeric(v['player_id'], errors='coerce')
    v['market_value_in_eur'] = pd.to_numeric(v['market_value_in_eur'], errors='coerce')
    v['date'] = pd.to_datetime(v['date'], errors='coerce')
    v = v.dropna(subset=['player_id', 'date', 'market_value_in_eur']).copy()
    v['player_id'] = v['player_id'].astype(np.int64)
    v = v.sort_values(['date', 'player_id'], kind='mergesort')

    # Backward merge: only valuations dated on or before match date are visible.
    lu = pd.merge_asof(lu, v, on='date', by='player_id', direction='backward')
    lu = lu.merge(players, on='player_id', how='inner')

    lu['pit_val'] = lu['market_value_in_eur'].fillna(0.0).clip(lower=0.0)
    lu['pos'] = lu['pos'].fillna(lu['line']).fillna('MID')
    lu['line'] = lu['line'].fillna(lu['pos'])
    pit_age = (lu['date'] - lu['dob']).dt.days / 365.25
    lu['pit_age'] = pit_age.fillna(lu['age']).fillna(26.0).clip(15.0, 45.0)
    lu['value_rating'] = _pit_value_ratings(lu, interp_ref)
    return lu


def _compute_pit_pair_chemistry(st_df):
    """Compute strictly pre-match pairwise shared-starts chemistry in [0, 1] per (game_id, club_id)."""
    from collections import defaultdict
    import math

    ordered = st_df[['game_id', 'club_id', 'date', 'player_id']].sort_values(
        ['date', 'game_id', 'club_id', 'player_id'], kind='mergesort'
    )
    gids = ordered['game_id'].to_numpy()
    cids = ordered['club_id'].to_numpy()
    pids = ordered['player_id'].to_numpy()

    pair_counts = defaultdict(int)
    denom = math.log1p(50.0)
    log1p = math.log1p
    res_g, res_c, res_v = [], [], []

    n = len(gids)
    i = 0
    while i < n:
        g, c = gids[i], cids[i]
        j = i + 1
        while j < n and gids[j] == g and cids[j] == c:
            j += 1
        team_pids = pids[i:j]
        m = len(team_pids)
        if m >= 2:
            total = 0.0
            pairs = 0
            keys = []
            for a in range(m):
                pa = int(team_pids[a])
                for b in range(a + 1, m):
                    pb = int(team_pids[b])
                    key = (pa << 32) | pb if pa < pb else (pb << 32) | pa
                    keys.append(key)
                    cnt = pair_counts.get(key, 0)
                    if cnt > 0:
                        s = log1p(cnt) / denom
                        total += 1.0 if s > 1.0 else s
                    pairs += 1
            res_g.append(g)
            res_c.append(c)
            res_v.append(total / pairs if pairs else 0.0)
            for key in keys:
                pair_counts[key] += 1
        else:
            res_g.append(g)
            res_c.append(c)
            res_v.append(0.0)
        i = j

    return pd.DataFrame({'game_id': res_g, 'club_id': res_c, 'cohesion_mean': res_v})


def club_game_stats(lu):
    """Collapse lineup rows into one row per club per game."""
    st = lu[lu['type'] == 'starting_lineup'].dropna(subset=['value_rating'])
    sb = lu[lu['type'] == 'substitutes'].dropna(subset=['value_rating'])

    g = st.groupby(['game_id', 'club_id'])
    stats = g.agg(
        starter_count=('value_rating', 'size'),
        overall_mean=('value_rating', 'mean'),
        overall_max=('value_rating', 'max'),
        overall_min=('value_rating', 'min'),
        val_sum=('pit_val', 'sum'),
        age_mean=('pit_age', 'mean'),
        height_mean=('height', 'mean'),
    ).reset_index()

    chem = _compute_pit_pair_chemistry(st)
    stats = stats.merge(chem, on=['game_id', 'club_id'], how='left')

    for line in ('GK', 'DEF', 'MID', 'ATT'):
        sel = st[st['line'] == line]
        r = sel.groupby(['game_id', 'club_id'])['value_rating'].mean().rename(f'rating_{line}')
        h = sel.groupby(['game_id', 'club_id'])['height'].mean().rename(f'height_{line}')
        stats = stats.merge(r, on=['game_id', 'club_id'], how='left')
        stats = stats.merge(h, on=['game_id', 'club_id'], how='left')
        stats[f'rating_{line}'] = stats[f'rating_{line}'].fillna(stats['overall_mean'])
        stats[f'height_{line}'] = stats[f'height_{line}'].fillna(stats['height_mean'])

    sub = sb.groupby(['game_id', 'club_id'])['value_rating'].mean().rename('sub_mean')
    stats = stats.merge(sub, on=['game_id', 'club_id'], how='left')
    stats['sub_mean'] = stats['sub_mean'].fillna(stats['overall_mean'] - 5.0)
    stats['depth_gap'] = stats['overall_mean'] - stats['sub_mean']
    stats['cohesion_mean'] = stats['cohesion_mean'].fillna(0.0)
    stats['prime_mean'] = (1.0 - 0.018 * (stats['age_mean'] - PRIME_AGE).abs() ** 1.25).clip(0.6, 1.0)

    return stats[stats['starter_count'] >= 8]


def compute_pre_kickoff_form(games):
    """Strictly shifted 5-match rolling points and goal-difference per club."""
    home = pd.DataFrame({
        'game_id': games['game_id'], 'date': games['date'],
        'club_id': games['home_club_id'], 'side': 'home',
        'gf': games['home_club_goals'], 'ga': games['away_club_goals'],
    })
    away = pd.DataFrame({
        'game_id': games['game_id'], 'date': games['date'],
        'club_id': games['away_club_id'], 'side': 'away',
        'gf': games['away_club_goals'], 'ga': games['home_club_goals'],
    })
    long = pd.concat([home, away], ignore_index=True)
    long['pts'] = np.select([long['gf'] > long['ga'], long['gf'] == long['ga']], [3.0, 1.0], default=0.0)
    long['gd'] = (long['gf'] - long['ga']).astype(float)
    long = long.sort_values(['club_id', 'date', 'game_id'], kind='mergesort').reset_index(drop=True)

    shifted = long.groupby('club_id', sort=False)[['pts', 'gd']].shift(1)
    long['form_pts_5'] = (
        shifted.groupby(long['club_id'], sort=False)['pts']
        .rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
        .fillna(1.5)
    )
    long['form_gd_5'] = (
        shifted.groupby(long['club_id'], sort=False)['gd']
        .rolling(5, min_periods=1).mean()
        .reset_index(level=0, drop=True)
        .fillna(0.0)
    )

    wide = long.pivot(index='game_id', columns='side', values=['form_pts_5', 'form_gd_5'])
    wide.columns = [f'{side}_{stat}' for stat, side in wide.columns]
    return pd.DataFrame({
        'game_id': wide.index,
        'diff_form_pts_5': (wide['home_form_pts_5'] - wide['away_form_pts_5']).fillna(0.0).values,
        'diff_form_gd_5': (wide['home_form_gd_5'] - wide['away_form_gd_5']).fillna(0.0).values,
    })


def resolve_league_tiers(comp_series):
    """Map competition_id to tier factor, falling back to competitions.csv confederation."""
    tier_map = dict(LEAGUE_TIER_MAP)
    if os.path.exists(COMPETITIONS_CSV):
        comps = pd.read_csv(COMPETITIONS_CSV, usecols=['competition_id', 'confederation', 'sub_type'])
        for _, row in comps.iterrows():
            cid = row['competition_id']
            if cid in tier_map:
                continue
            conf = str(row.get('confederation', '')).lower()
            if conf == 'asien':
                tier_map[cid] = 0.78
            elif conf in ('europa', 'amerika', 'fifa'):
                tier_map[cid] = 0.85
            else:
                tier_map[cid] = 0.80
    return comp_series.map(tier_map).fillna(0.80).astype(float)


def main():
    games = pd.read_csv(
        GAMES,
        usecols=[
            'game_id', 'season', 'competition_id', 'date',
            'home_club_id', 'away_club_id',
            'home_club_goals', 'away_club_goals',
        ],
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

    interp_ref, players = load_reference_and_players()
    lu = pit_lineups(players, games, interp_ref)
    stats = club_game_stats(lu)
    form_df = compute_pre_kickoff_form(games)

    m = games.merge(
        stats, left_on=['game_id', 'home_club_id'],
        right_on=['game_id', 'club_id'], how='inner',
    )
    m = m.merge(
        stats, left_on=['game_id', 'away_club_id'],
        right_on=['game_id', 'club_id'], how='inner', suffixes=('_h', '_a'),
    )
    m = m.merge(form_df, on='game_id', how='left')
    for col in ('diff_form_pts_5', 'diff_form_gd_5'):
        m[col] = m[col].fillna(0.0)

    out = pd.DataFrame({
        'game_id': m['game_id'].values,
        'season': m['season'].values,
        'competition_id': m['competition_id'].values,
        'date': m['date'].dt.strftime('%Y-%m-%d').values,
    })
    out['diff_overall_mean'] = (m['overall_mean_h'] - m['overall_mean_a']).values
    out['diff_overall_max'] = (m['overall_max_h'] - m['overall_max_a']).values
    out['diff_overall_min'] = (m['overall_min_h'] - m['overall_min_a']).values
    out['diff_attack_vs_defense'] = (m['rating_ATT_h'] - m['rating_DEF_a']).values
    out['diff_defense_vs_attack'] = (m['rating_DEF_h'] - m['rating_ATT_a']).values
    out['diff_midfield'] = (m['rating_MID_h'] - m['rating_MID_a']).values
    out['diff_sub_mean'] = (m['sub_mean_h'] - m['sub_mean_a']).values
    out['diff_depth_gap'] = (m['depth_gap_h'] - m['depth_gap_a']).values
    out['diff_market_val_log'] = (np.log1p(m['val_sum_h']) - np.log1p(m['val_sum_a'])).values
    out['diff_form_pts_5'] = m['diff_form_pts_5'].values
    out['diff_form_gd_5'] = m['diff_form_gd_5'].values
    out['diff_aerial_att_vs_def'] = (m['height_ATT_h'] - m['height_DEF_a']).values
    out['diff_aerial_def_vs_att'] = (m['height_DEF_h'] - m['height_ATT_a']).values
    out['diff_prime_score'] = (m['prime_mean_h'] - m['prime_mean_a']).values
    out['diff_cohesion'] = (m['cohesion_mean_h'] - m['cohesion_mean_a']).fillna(0.0).values
    out['league_tier_factor'] = resolve_league_tiers(m['competition_id']).values

    out['target_outcome'] = np.select(
        [m['home_club_goals'] > m['away_club_goals'],
         m['home_club_goals'] == m['away_club_goals']],
        [2, 1], default=0,
    )
    out['home_goals'] = m['home_club_goals'].values
    out['away_goals'] = m['away_club_goals'].values

    # Sanity checks: zero NaN or non-finite values in any model feature.
    nan_cols = [c for c in MODEL_FEATURES if out[c].isna().any()]
    assert not nan_cols, f'NaN detected in MODEL_FEATURES: {nan_cols}'
    assert np.isfinite(out[MODEL_FEATURES].values).all(), 'Non-finite values in MODEL_FEATURES'

    out = out.sort_values(['date', 'game_id'], kind='mergesort').reset_index(drop=True)
    out.to_csv(OUT, index=False)

    sea_mask = out['competition_id'].isin({'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'})
    print(f'wrote {OUT}: {len(out):,} matches (SEA: {int(sea_mask.sum()):,}, post-2026-07-06: {int((out["date"] > "2026-07-06").sum()):,})')
    print(out.groupby('season').size().tail(8).to_string())
    print(out[MODEL_FEATURES].describe().round(3).to_string())


if __name__ == '__main__':
    main()
