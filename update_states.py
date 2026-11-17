"""Daily state updater for models/team_state.json and models/league_state.json.

Updates Elo, rolling gf10/ga10, last_date, and league stats from new finished_matches
in Supabase (including matches without lineups) without touching any model files.
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


def update_states():
    url, _ = _sb_cfg()
    if not url:
        return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}

    with open(TEAM_STATE_PATH, 'r', encoding='utf-8') as f:
        ts = json.load(f)
    with open(LEAGUE_STATE_PATH, 'r', encoding='utf-8') as f:
        ls = json.load(f)

    as_of = ts.get('as_of') or '2026-11-01'
    matches = _sb_req(
        f'finished_matches?select=home_team,away_team,home_goals,away_goals,match_date,league'
        f'&match_date=gt.{as_of}&order=match_date.asc&limit=5000'
    ) or []
    if not matches:
        return {'status': 'noop', 'as_of': as_of, 'updated': 0}

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

    max_dt = as_of
    cnt = 0
    for m in matches:
        hg, ag = m.get('home_goals'), m.get('away_goals')
        if hg is None or ag is None:
            continue
        ht, at = str(m['home_team']).strip(), str(m['away_team']).strip()
        cid = str(m.get('league') or '').strip()
        dt_str = str(m.get('match_date') or '')[:10]
        dt = pd.to_datetime(dt_str, errors='coerce')
        neu = is_neutral_match(cid)

        elo.update(ht, at, int(hg), int(ag), neutral=neu)
        leagues.update(cid, int(hg), int(ag))
        teams.update(ht, int(hg), int(ag), dt if pd.notna(dt) else None)
        teams.update(at, int(ag), int(hg), dt if pd.notna(dt) else None)
        if dt_str > max_dt:
            max_dt = dt_str
        cnt += 1

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

    with open(TEAM_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump({'as_of': max_dt, 'by_id': by_id, 'by_name': by_name}, f)
    with open(LEAGUE_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(ls, f, indent=2)
    return {'status': 'updated', 'as_of': max_dt, 'matches_applied': cnt}


if __name__ == '__main__':
    print(json.dumps(update_states()))
