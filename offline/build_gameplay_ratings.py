"""Compute player ratings from real Transfermarkt gameplay metrics (no market-value proxy).

Uses appearances.csv, games.csv, and competitions.csv to compute position-specific
gameplay scores from:
  - Goals per 90 (ATT/MID/DEF)
  - Assists per 90 (ATT/MID/DEF)
  - Goals conceded per 90 & clean-sheet rate (GK/DEF)
  - Match win contribution (points per appearance)
  - Minutes played weighted by competition strength tier
  - Discipline penalty (yellow & red cards per 90)

Bayesian shrinkage toward position priors prevents small-sample spikes (e.g., 1 goal
in 15 minutes). Also supports point-in-time (prior-season) ratings so chronological
model retraining has zero future leakage.
"""
import json
import os

import numpy as np
import pandas as pd

TM_DIR = 'Football Data from Transfermarkt'
APPEARANCES_CSV = os.path.join(TM_DIR, 'appearances.csv')
GAMES_CSV = os.path.join(TM_DIR, 'games.csv')
COMPETITIONS_CSV = os.path.join(TM_DIR, 'competitions.csv')
PLAYERS_LITE = os.path.join('web_app_new_v2', 'players_lite.json')

RATING_FLOOR = 52.0
RATING_CEIL = 97.0

# Competition strength multipliers (Tier 1 Big-5/UCL, Major Euro/Global, Developing/T2)
TOP_COMPS = {'GB1', 'ES1', 'L1', 'IT1', 'FR1', 'CL'}
MAJOR_COMPS = {
    'EL', 'ECL', 'NL1', 'PO1', 'TR1', 'BE1', 'RU1', 'SC1', 'UKR1', 'GR1',
    'DK1', 'SE1', 'NO1', 'PL1', 'C1', 'A1', 'S1', 'BRA1', 'AR1', 'MLS1',
    'FAC', 'CDR', 'DFB', 'CIT', 'FRC', 'WM22', 'EM24', 'UNLA', 'UNLB',
}
SEA_COMPS = {'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'}


def _comp_tier_weight(comp_id):
    c = str(comp_id or '').strip()
    if c in TOP_COMPS:
        return 1.00
    if c in MAJOR_COMPS:
        return 0.86
    if c in SEA_COMPS:
        return 0.74
    return 0.78


def load_enriched_appearances(max_date=None):
    """Load appearances joined with game goals/outcomes and competition tier weights."""
    games = pd.read_csv(
        GAMES_CSV,
        usecols=['game_id', 'competition_id', 'season', 'date', 'home_club_id', 'away_club_id', 'home_club_goals', 'away_club_goals'],
    )
    games = games.dropna(subset=['home_club_goals', 'away_club_goals']).drop_duplicates('game_id')
    if max_date:
        games = games[games['date'] <= max_date]
    games['tier_w'] = games['competition_id'].map(_comp_tier_weight)

    app = pd.read_csv(
        APPEARANCES_CSV,
        usecols=['game_id', 'player_id', 'player_club_id', 'date', 'goals', 'assists', 'yellow_cards', 'red_cards', 'minutes_played'],
    )
    app = app[app['minutes_played'] > 0].copy()
    if max_date:
        app = app[app['date'] <= max_date]

    df = app.merge(
        games[['game_id', 'season', 'home_club_id', 'away_club_id', 'home_club_goals', 'away_club_goals', 'tier_w']],
        on='game_id',
        how='inner',
    )
    is_home = df['player_club_id'] == df['home_club_id']
    gf = np.where(is_home, df['home_club_goals'], df['away_club_goals'])
    ga = np.where(is_home, df['away_club_goals'], df['home_club_goals'])

    df['team_gf'] = gf
    df['team_ga'] = ga
    df['win_pts'] = np.where(gf > ga, 1.0, np.where(gf == ga, 0.5, 0.0))
    df['clean_sheet'] = ((ga == 0) & (df['minutes_played'] >= 60)).astype(float)
    df['starter_app'] = (df['minutes_played'] >= 45).astype(float)
    df['weighted_mins'] = df['minutes_played'] * (df['tier_w'] ** 1.5)
    df['weighted_goals'] = df['goals'] * (df['tier_w'] ** 1.8)
    df['weighted_assists'] = df['assists'] * (df['tier_w'] ** 1.8)
    df['weighted_ga'] = df['team_ga'] * (df['minutes_played'] / 90.0) / (df['tier_w'] ** 0.8)
    df['weighted_cs'] = df['clean_sheet'] * (df['tier_w'] ** 1.4)
    df['weighted_win_pts'] = df['win_pts'] * (df['tier_w'] ** 1.3)
    df['cards_pts'] = df['yellow_cards'] + 3.0 * df['red_cards']
    return df


def _zscore(s):
    sd = float(s.std(ddof=0))
    if sd < 1e-9:
        return pd.Series(0.0, index=s.index)
    return (s - float(s.mean())) / sd


def score_from_aggregates(agg, pos_series, ref_ratings=None):
    """Compute position-specific gameplay ratings on [52.0, 97.0] from aggregated stats."""
    df = agg.copy()
    df['pos'] = pos_series.reindex(df.index).fillna('MID')

    # Bayesian shrinkage toward modest baseline priors (8 x 90-min equivalents)
    prior_90 = 8.0
    n90 = df['minutes_played'] / 90.0
    apps = df['apps'].clip(lower=1.0)

    df['g90'] = (df['weighted_goals'] + 0.6) / (n90 + prior_90)
    df['a90'] = (df['weighted_assists'] + 0.5) / (n90 + prior_90)
    df['ga90'] = (df['weighted_ga'] + 12.0) / (n90 + prior_90)
    df['cs_rate'] = (df['weighted_cs'] + 1.5) / (df['starter_app'] + 6.0)
    df['win_rate'] = (df['weighted_win_pts'] + 3.5) / (apps + 8.0)
    df['cards90'] = df['cards_pts'] / (n90 + prior_90)
    df['vol'] = np.log1p(df['weighted_mins'])

    out = pd.Series(62.0, index=df.index, dtype=float)

    for pos, grp in df.groupby('pos'):
        zg = _zscore(grp['g90'])
        za = _zscore(grp['a90'])
        zga = _zscore(-grp['ga90'])
        zcs = _zscore(grp['cs_rate'])
        zw = _zscore(grp['win_rate'])
        zvol = _zscore(grp['vol'])
        zc = _zscore(grp['cards90'])

        if pos == 'GK':
            comp = 0.36 * zga + 0.30 * zcs + 0.22 * zvol + 0.12 * zw - 0.03 * zc
        elif pos == 'DEF':
            comp = 0.28 * zga + 0.22 * zcs + 0.26 * zvol + 0.18 * zw + 0.06 * (zg + za) - 0.05 * zc
        elif pos == 'ATT':
            comp = 0.42 * zg + 0.22 * za + 0.22 * zvol + 0.14 * zw - 0.04 * zc
        else:  # MID
            comp = 0.26 * za + 0.22 * zg + 0.30 * zvol + 0.22 * zw - 0.05 * zc

        pct = comp.rank(pct=True, method='average').values
        if ref_ratings is not None:
            ref = ref_ratings.loc[ref_ratings.index.isin(grp.index)].dropna()
            if len(ref) >= 50:
                mapped = np.quantile(ref.values, np.clip(pct, 0.0, 1.0))
            else:
                mapped = RATING_FLOOR + pct * (RATING_CEIL - RATING_FLOOR)
        else:
            mapped = RATING_FLOOR + pct * (RATING_CEIL - RATING_FLOOR)

        # Low-minute players (< 450 career mins) smoothly pulled toward lower tier
        min_factor = np.clip(grp['minutes_played'].values / 450.0, 0.0, 1.0)
        adj = 56.0 + min_factor * (mapped - 56.0)
        out.loc[grp.index] = np.clip(adj, RATING_FLOOR, RATING_CEIL).round(1)

    return out


def compute_current_gameplay_ratings(players_list=None):
    """Return Series indexed by player_id with real gameplay-stats ratings [52.0, 97.0]."""
    if players_list is None:
        with open(PLAYERS_LITE, 'r', encoding='utf-8') as f:
            players_list = json.load(f)

    p_df = pd.DataFrame(players_list).set_index('id')
    app = load_enriched_appearances()

    is_former_map = p_df['is_former'].fillna(False) if 'is_former' in p_df.columns else pd.Series(False, index=p_df.index)
    app['is_former'] = app['player_id'].map(is_former_map).fillna(False)

    # Active players: exponential recency decay so 2024-2026 form dominates over 2022
    # Retired legends (is_former=True): full career weight (1.0)
    years_ago = np.clip(2025 - app['season'].astype(float), 0.0, 12.0)
    recency_w = np.where(app['is_former'], 1.0, 0.52 ** years_ago)

    app['rw_mins'] = app['weighted_mins'] * recency_w
    app['rw_raw_mins'] = app['minutes_played'] * recency_w
    app['rw_goals'] = app['weighted_goals'] * recency_w
    app['rw_assists'] = app['weighted_assists'] * recency_w
    app['rw_ga'] = app['weighted_ga'] * recency_w
    app['rw_cs'] = app['weighted_cs'] * recency_w
    app['rw_starter'] = app['starter_app'] * recency_w
    app['rw_win_pts'] = app['weighted_win_pts'] * recency_w
    app['rw_cards'] = app['cards_pts'] * recency_w
    app['rw_apps'] = recency_w

    agg = app.groupby('player_id').agg(
        apps=('rw_apps', 'sum'),
        minutes_played=('rw_raw_mins', 'sum'),
        weighted_mins=('rw_mins', 'sum'),
        weighted_goals=('rw_goals', 'sum'),
        weighted_assists=('rw_assists', 'sum'),
        weighted_ga=('rw_ga', 'sum'),
        weighted_cs=('rw_cs', 'sum'),
        starter_app=('rw_starter', 'sum'),
        weighted_win_pts=('rw_win_pts', 'sum'),
        cards_pts=('rw_cards', 'sum'),
    )

    ref_ratings = p_df['rating'] if 'rating' in p_df.columns else None
    rated = score_from_aggregates(agg, p_df['pos'], ref_ratings=ref_ratings)

    # Additional recent-activity dampening for active players with < 900 mins since 2024
    mins_24p = app[app['season'] >= 2024].groupby('player_id')['minutes_played'].sum()
    active_ids = p_df.index[~is_former_map.astype(bool)]
    for pid in rated.index.intersection(active_ids):
        m24 = float(mins_24p.get(pid, 0.0))
        if m24 < 900.0:
            act_factor = 0.35 + 0.65 * (m24 / 900.0)
            rated.loc[pid] = round(float(np.clip(62.0 + act_factor * (rated.loc[pid] - 62.0), RATING_FLOOR, RATING_CEIL)), 1)

    return rated


def main():
    with open(PLAYERS_LITE, 'r', encoding='utf-8') as f:
        players = json.load(f)

    rated = compute_current_gameplay_ratings(players)
    updated = 0
    for p in players:
        pid = p.get('id')
        if pid in rated.index:
            p['rating'] = float(rated.loc[pid])
            updated += 1
        elif p.get('rating') is None:
            p['rating'] = 58.0

    with open(PLAYERS_LITE, 'w', encoding='utf-8') as f:
        json.dump(players, f, ensure_ascii=False)

    top10 = sorted(players, key=lambda x: float(x.get('rating') or 0), reverse=True)[:10]
    print(f'Updated {updated:,} / {len(players):,} players with real gameplay-stats ratings.')
    print('Top 10 players by gameplay metrics:')
    for p in top10:
        print(f"  {p['name']:<26} pos={p['pos']:<3} rtg={p['rating']} g90={p.get('goals_per_90')} g={p.get('total_goals')} a={p.get('total_assists')} club={p.get('club')}")


if __name__ == '__main__':
    main()
