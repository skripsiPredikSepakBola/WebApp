"""Idempotent daily state updater for models/team_state.json and models/league_state.json.

Updates Elo, rolling gf10/ga10, last_date, and league stats from new finished_matches
in Supabase (including matches without lineups) without touching any model files.
Uses a watermark (last_match_date + processed_ids) so reprocessing never double-counts.
"""
import json
import os
import pandas as pd

from elo import EloTracker
from features import LeagueStats, TeamState, is_neutral_match
from league_tiers import resolve_league_tier
from sync_matches import _sb_cfg, _sb_req

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAM_STATE_PATH = os.path.join(BASE_DIR, 'models', 'team_state.json')
LEAGUE_STATE_PATH = os.path.join(BASE_DIR, 'models', 'league_state.json')


def apply_matches_idempotent(ts, ls, matches):
    """Apply matches in (match_date, match_id) order without double-counting watermarked IDs."""
    as_of = ts.get('as_of') or '2026-11-01'
    wm = ts.get('watermark') or {'date': as_of, 'ids': []}
    wm_date = str(wm.get('date') or as_of)[:10]
    seen_ids = set(str(x) for x in (wm.get('ids') or []))

    # Normalize, deduplicate by match_id, and sort strictly by (match_date, match_id)
    dedup = {}
    for m in (matches or []):
        mid = m.get('match_id') or m.get('id')
        dt_str = str(m.get('match_date') or '')[:10]
        if not mid or not dt_str or m.get('home_goals') is None or m.get('away_goals') is None:
            continue
        mid_s = str(mid)
        if dt_str < wm_date or (dt_str == wm_date and mid_s in seen_ids):
            continue
        dedup[mid_s] = (dt_str, mid_s, m)

    ordered = sorted(dedup.values(), key=lambda x: (x[0], x[1]))
    if not ordered:
        return ts, ls, 0

    elo, leagues, teams = EloTracker(), LeagueStats(), TeamState()
    by_id = ts.get('by_id') or {}
    by_name = ts.get('by_name') or {}
    for name, v in by_name.items():
        elo.r[name] = float(v.get('elo', 1500.0))
        if v.get('last_date'):
            teams.last[name] = pd.Timestamp(v['last_date'])
    for cid, v in ls.items():
        leagues.n[cid] = int(v.get('n', 0))
        leagues.goals[cid] = float(v.get('goals', 0.0))
        leagues.home[cid] = float(v.get('home', 0.0))

    max_dt = wm_date
    wm_ids_on_max = set(seen_ids)
    applied = 0
    for dt_str, mid_s, m in ordered:
        ht, at = str(m['home_team']).strip(), str(m['away_team']).strip()
        hg, ag = int(m['home_goals']), int(m['away_goals'])
        cid = str(m.get('league') or '').strip()
        dt = pd.to_datetime(dt_str, errors='coerce')
        neu = is_neutral_match(cid)

        elo.update(ht, at, hg, ag, neutral=neu)
        leagues.update(cid, hg, ag)
        teams.update(ht, hg, ag, dt if pd.notna(dt) else None)
        teams.update(at, ag, hg, dt if pd.notna(dt) else None)

        if dt_str > max_dt:
            max_dt = dt_str
            wm_ids_on_max = {mid_s}
        else:
            wm_ids_on_max.add(mid_s)
        applied += 1

    ref_dt = pd.Timestamp(max_dt)
    for name in set(elo.r.keys()):
        if name in by_name or name in teams.last:
            gf, ga, _ = teams.get(name, ref_dt)
            last_dt = teams.last.get(name)
            entry = {
                'elo': round(float(elo.r[name]), 2),
                'gf10': round(float(gf), 4),
                'ga10': round(float(ga), 4),
                'last_date': last_dt.strftime('%Y-%m-%d') if last_dt is not None else None,
            }
            by_name[name] = entry
            by_name[name.lower()] = entry

    for cid in set(leagues.n.keys()):
        avg_g, home_w = leagues.get(cid)
        tier_v, known = resolve_league_tier(cid)
        ls[cid] = {
            'n': int(leagues.n[cid]),
            'goals': float(leagues.goals[cid]),
            'home': float(leagues.home[cid]),
            'avg_goals': round(float(avg_g), 4),
            'home_win': round(float(home_w), 4),
            'tier': tier_v,
            'tier_known': known,
        }

    new_ts = {
        'as_of': max_dt,
        'watermark': {'date': max_dt, 'ids': sorted(wm_ids_on_max)},
        'by_id': by_id,
        'by_name': by_name,
    }
    return new_ts, ls, applied


def update_states():
    url, _ = _sb_cfg()
    if not url:
        return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}

    with open(TEAM_STATE_PATH, 'r', encoding='utf-8') as f:
        ts = json.load(f)
    with open(LEAGUE_STATE_PATH, 'r', encoding='utf-8') as f:
        ls = json.load(f)

    wm_date = (ts.get('watermark') or {}).get('date') or ts.get('as_of') or '2026-11-01'
    matches = _sb_req(
        f'finished_matches?select=match_id,home_team,away_team,home_goals,away_goals,match_date,league'
        f'&match_date=gte.{wm_date}&order=match_date.asc&limit=5000'
    ) or []

    new_ts, new_ls, applied = apply_matches_idempotent(ts, ls, matches)
    if applied == 0:
        return {'status': 'noop', 'as_of': new_ts['as_of'], 'updated': 0}

    with open(TEAM_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_ts, f)
    with open(LEAGUE_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(new_ls, f, indent=2)
    return {'status': 'updated', 'as_of': new_ts['as_of'], 'matches_applied': applied}


if __name__ == '__main__':
    print(json.dumps(update_states()))
