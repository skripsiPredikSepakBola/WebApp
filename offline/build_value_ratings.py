"""Derive player ratings from Transfermarkt market value instead of FIFA.

Why: fifa_players.csv covers 17,954 players against 50,149 in players_lite.json,
and it is a frozen snapshot - EA no longer ships the data, so it cannot be
refreshed. player_valuations.csv covers every player, updates weekly, and is
already point-in-time via merge_asof. Deriving the rating from value removes a
stale dependency, removes the fuzzy name-match step from notebook 01, and makes
the web app agree with the "Transfermarkt-only" claim in the thesis.

The mapping is calibrated so a value rating lands on the same 52-97 scale as the
FIFA rating it replaces: rank players by log market value within their position,
then map that percentile through the observed FIFA rating distribution. That
keeps every downstream threshold (rating badges, the 35.0 OOP floor, the /78.0
divisors in the xG scaling) working unchanged.

Age is folded in because market value already prices in remaining career length:
a 33-year-old and a 23-year-old on the same value are not equal players now, and
the age curve pulls them apart.
"""
import json

import numpy as np
import pandas as pd

PLAYERS_LITE = 'players_lite.json'
VALUATIONS = 'Football Data from Transfermarkt/player_valuations.csv'
OUT_JSON = 'players_lite_value.json'

# Anchors of the FIFA rating scale we are reproducing, so downstream code that
# hardcodes rating thresholds keeps behaving the same way.
RATING_FLOOR = 52.0
RATING_CEIL = 97.0

# Peak age for the value-to-rating adjustment. Market value peaks earlier than
# playing ability because it prices in resale years, so a player past this age
# is worth less than he plays; the correction adds rating back.
PEAK_AGE = 27.0


def latest_valuations():
    """Most recent valuation per player, as the 'current' market value."""
    v = pd.read_csv(VALUATIONS, usecols=['player_id', 'date', 'market_value_in_eur'])
    v = v.dropna(subset=['market_value_in_eur'])
    v = v.sort_values('date').groupby('player_id', as_index=False).last()
    return v.rename(columns={'player_id': 'id', 'market_value_in_eur': 'val_latest'})


def age_correction(age):
    """Rating points to add back for players whose value is depressed by age.

    Value falls off a cliff after ~30 while ability declines gently, so without
    this an in-form 33-year-old scores far below his real level. Young players
    get a small negative correction: their value is inflated by potential they
    have not delivered yet.
    """
    age = np.asarray(age, dtype=float)
    past_peak = np.clip(age - PEAK_AGE, 0, None)
    pre_peak = np.clip(PEAK_AGE - age, 0, None)
    return 0.45 * past_peak - 0.25 * pre_peak


def value_to_rating(df):
    """Map log market value to the FIFA rating scale, within position.

    Percentile-matching rather than a fitted regression: it reproduces the shape
    of the rating distribution exactly, so the output is directly comparable to
    the FIFA ratings it replaces instead of being a differently-shaped score.
    """
    out = pd.Series(np.nan, index=df.index, dtype=float)

    for pos, grp in df.groupby('pos'):
        logv = np.log1p(grp['val_latest'].clip(lower=0))
        # Percentile within position; ties share a percentile.
        pct = logv.rank(pct=True, method='average')

        # Target distribution: the FIFA ratings actually observed for this
        # position, so goalkeepers are not mapped onto a striker's spread.
        ref = grp['fifa_rating'].dropna()
        if len(ref) >= 50:
            target = np.quantile(ref, np.clip(pct.values, 0, 1))
        else:
            # Too few FIFA ratings to define a shape; fall back to the global
            # scale rather than inventing a position-specific one.
            target = RATING_FLOOR + pct.values * (RATING_CEIL - RATING_FLOOR)

        out.loc[grp.index] = target + age_correction(grp['age'])

    return out.clip(RATING_FLOOR, RATING_CEIL).round(1)


def main():
    players = pd.DataFrame(json.load(open(PLAYERS_LITE, encoding='utf-8')))
    players = players.rename(columns={'rating': 'fifa_rating'})

    vals = latest_valuations()
    df = players.merge(vals[['id', 'val_latest']], on='id', how='left')
    # Players with no valuation history fall back to the value already carried
    # in players_lite.json rather than dropping out of the pool.
    df['val_latest'] = df['val_latest'].fillna(df['val'])

    df['value_rating'] = value_to_rating(df)

    have_fifa = df['fifa_rating'].notna().sum()
    have_value = df['value_rating'].notna().sum()
    print(f'players:            {len(df):,}')
    print(f'with FIFA rating:   {have_fifa:,} ({have_fifa / len(df) * 100:.1f}%)')
    print(f'with value rating:  {have_value:,} ({have_value / len(df) * 100:.1f}%)')

    both = df.dropna(subset=['fifa_rating', 'value_rating'])
    r = np.corrcoef(both['fifa_rating'], both['value_rating'])[0, 1]
    mae = (both['fifa_rating'] - both['value_rating']).abs().mean()
    print(f'\nagreement where both exist (n={len(both):,}): r={r:.4f}  MAE={mae:.2f} rating points')

    print('\nvalue_rating distribution vs fifa_rating:')
    print(df[['fifa_rating', 'value_rating']].describe().round(2).to_string())

    # Emit a players_lite drop-in with the derived rating in the `rating` slot,
    # keeping fifa_rating alongside so the two can be compared downstream.
    out = df.copy()
    out['rating'] = out['value_rating']
    records = out.drop(columns=['val_latest']).where(pd.notna(out), None).to_dict('records')
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False)
    print(f'\nwrote {OUT_JSON}')

    print('\nsanity - top 10 by value rating:')
    top = df.nlargest(10, 'value_rating')[['name', 'pos', 'age', 'val_latest',
                                           'fifa_rating', 'value_rating']]
    print(top.to_string(index=False))


if __name__ == '__main__':
    main()
