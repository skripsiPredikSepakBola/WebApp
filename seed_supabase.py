import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from sync_matches import _sb_cfg, _sb_req, upsert_finished_matches

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYER_COLS = ('id', 'name', 'full_name', 'tm_name', 'club', 'nat', 'pos', 'rating', 'age', 'height', 'val', 'goals_per_90', 'total_goals')
SNAP_INT_COLS = ('player_id', 'total_goals', 'minutes_30d', 'goals_30d', 'assists_30d')
SNAP_FLT_COLS = ('rating', 'val', 'age', 'goals_per_90')
_EU_SEED_COMPS = {'GB1', 'ES1', 'IT1', 'L1', 'FR1', 'CL'}
_SEA_SEED_COMPS = {'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'}


def _has_remote_col(table, col):
    try:
        _sb_req(f'{table}?select={col}&limit=1')
        return True
    except RuntimeError as e:
        msg = str(e)
        if 'HTTP 400' in msg or 'HTTP 404' in msg or '42703' in msg or 'PGRST' in msg:
            return False
        raise


def _parse_num(val, cast):
    if val is None or val == '' or str(val).lower() in ('nan', 'none', 'null'):
        return None
    return cast(float(val)) if cast is int else cast(val)


def _seed_snapshots(data_dir):
    snap_path = os.path.join(data_dir, 'player_monthly_snapshots.csv')
    if not os.path.exists(snap_path):
        print('Note: player_monthly_snapshots.csv not found; skipping player_snapshots upload.')
        return 0
    if not _has_remote_col('player_snapshots', 'player_id'):
        print('Note: remote player_snapshots table not found (apply schema.sql); skipping snapshot upload.')
        return 0

    total, batch = 0, []
    with open(snap_path, 'r', encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            pid = _parse_num(row.get('player_id'), int)
            rdate = row.get('report_date')
            if pid is None or not rdate:
                continue
            item = {'player_id': pid, 'report_date': rdate, 'club': row.get('club') or None}
            for c in SNAP_INT_COLS[1:]:
                item[c] = _parse_num(row.get(c), int)
            for c in SNAP_FLT_COLS:
                item[c] = _parse_num(row.get(c), float)
            batch.append(item)
            if len(batch) >= 1000:
                _sb_req('player_snapshots?on_conflict=player_id,report_date', method='POST', body=batch, prefer='resolution=merge-duplicates,return=minimal')
                total += len(batch)
                batch = []
                if total % 25000 == 0:
                    print(f'Uploaded player_snapshots {total}...')
    if batch:
        _sb_req('player_snapshots?on_conflict=player_id,report_date', method='POST', body=batch, prefer='resolution=merge-duplicates,return=minimal')
        total += len(batch)
    print(f'Uploaded {total} player_snapshots rows')
    return total


def seed_all(data_dir=BASE_DIR):
    url, _ = _sb_cfg()
    if not url:
        raise RuntimeError('Set SUPABASE_URL and SUPABASE_KEY in .env first')

    with open(os.path.join(data_dir, 'players_lite.json'), 'r', encoding='utf-8') as f:
        raw_players = json.load(f)

    has_rdate = _has_remote_col('players', 'report_date')
    if not has_rdate:
        print('Note: remote players.report_date column missing (run schema.sql ALTER TABLE); seeding players without report_date.')

    cols = PLAYER_COLS + (('report_date',) if has_rdate else ())

    def _clean_player(p, use_cols):
        row = {}
        for k in use_cols:
            v = p.get(k)
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                v = None
            row[k] = v
        if row.get('id') is not None:
            row['id'] = int(row['id'])
        if row.get('total_goals') is not None:
            row['total_goals'] = int(row['total_goals'])
        if 'report_date' in use_cols and not row.get('report_date'):
            row['report_date'] = '2026-11-01'
        return row

    players = [_clean_player(p, cols) for p in raw_players]

    for i in range(0, len(players), 500):
        batch = players[i:i + 500]
        try:
            _sb_req('players?on_conflict=id', method='POST', body=batch, prefer='resolution=merge-duplicates,return=minimal')
        except RuntimeError as e:
            if i == 0 and has_rdate and 'report_date' in str(e):
                print('Note: remote players rejected report_date; falling back without report_date.')
                has_rdate = False
                players = [_clean_player(p, PLAYER_COLS) for p in raw_players]
                batch = players[i:i + 500]
                _sb_req('players?on_conflict=id', method='POST', body=batch, prefer='resolution=merge-duplicates,return=minimal')
            else:
                raise
        print(f'Uploaded players {i + len(batch)}/{len(players)}')

    with open(os.path.join(data_dir, 'preset_lineups.json'), 'r', encoding='utf-8') as f:
        lineups = json.load(f)
    with open(os.path.join(data_dir, 'preset_categories.json'), 'r', encoding='utf-8') as f:
        cats = json.load(f)

    cat_by_team = {team: cat for cat, teams in cats.items() for team in teams}
    preset_rows = [{
        'name': name,
        'category': cat_by_team.get(name, 'Other'),
        'formation': sq.get('formation', '4-3-3'),
        'starters': sq.get('starters', []),
        'subs': sq.get('subs', []),
    } for name, sq in lineups.items()]
    for i in range(0, len(preset_rows), 250):
        _sb_req('presets?on_conflict=name', method='POST', body=preset_rows[i:i + 250], prefer='resolution=merge-duplicates,return=minimal')
    print(f'Uploaded {len(preset_rows)} presets')

    _seed_snapshots(data_dir)
    _seed_finished_matches(data_dir)


def _seed_finished_matches(data_dir=BASE_DIR, limit_eu=100, limit_sea=100):
    tm_dir = None
    for cand in (
        os.path.join(os.path.dirname(os.path.abspath(data_dir)), 'Football Data from Transfermarkt'),
        os.path.join(os.path.abspath(data_dir), 'Football Data from Transfermarkt'),
    ):
        if os.path.exists(os.path.join(cand, 'games.csv')):
            tm_dir = cand
            break
    if not tm_dir:
        print('Note: Football Data from Transfermarkt/games.csv not found; skipping finished_matches CSV seed.')
        return 0

    comp_names = {
        'GB1': 'Premier League', 'ES1': 'LaLiga', 'IT1': 'Serie A', 'L1': 'Bundesliga',
        'FR1': 'Ligue 1', 'CL': 'UEFA Champions League',
        'IN1L': 'Indonesia Super League', 'MYS1': 'Malaysia Super League',
        'THA1': 'Thai League 1', 'VIE1': 'V.League 1', 'SIN1': 'Singapore Premier League',
    }
    club_names = {}
    clubs_p = os.path.join(tm_dir, 'clubs.csv')
    if os.path.exists(clubs_p):
        with open(clubs_p, 'r', encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('club_id') and r.get('name'):
                    club_names[str(r['club_id'])] = r['name']

    eu_rows, sea_rows = [], []
    target_comps = _EU_SEED_COMPS | _SEA_SEED_COMPS
    with open(os.path.join(tm_dir, 'games.csv'), 'r', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            cid = r.get('competition_id', '')
            if cid not in target_comps or str(r.get('season', '')).split('.')[0] != '2026':
                continue
            hg = _parse_num(r.get('home_club_goals'), int)
            ag = _parse_num(r.get('away_club_goals'), int)
            if hg is None or ag is None or not r.get('game_id') or not r.get('date'):
                continue
            target = eu_rows if cid in _EU_SEED_COMPS else sea_rows
            target.append(r)

    eu_rows.sort(key=lambda r: (r['date'], int(float(r['game_id']))), reverse=True)
    sea_rows.sort(key=lambda r: (r['date'], int(float(r['game_id']))), reverse=True)
    picked = sorted(eu_rows[:limit_eu] + sea_rows[:limit_sea], key=lambda r: (r['date'], int(float(r['game_id']))), reverse=True)

    existing = _sb_req('finished_matches?select=match_id,source&limit=1000') or []
    preserve_ids = {x['match_id'] for x in existing if x.get('source') == 'tmapi-alpha'}

    now_iso = datetime.now(timezone.utc).isoformat()
    out_rows = []
    for r in picked:
        gid = int(float(r['game_id']))
        mid = f'tmapi:{gid}'
        if mid in preserve_ids:
            continue
        cid = r['competition_id']
        ht = (r.get('home_club_name') or '').strip() or club_names.get(str(r.get('home_club_id', '')), '')
        at = (r.get('away_club_name') or '').strip() or club_names.get(str(r.get('away_club_id', '')), '')
        if not ht or not at:
            continue
        dt = r['date'][:10]
        out_rows.append({
            'match_id': mid,
            'source': 'transfermarkt-csv',
            'league': comp_names.get(cid, cid),
            'match_date': f'{dt}T00:00:00+00:00',
            'home_team': ht,
            'away_team': at,
            'home_goals': int(float(r['home_club_goals'])),
            'away_goals': int(float(r['away_club_goals'])),
            'status': 'FT',
            'raw_json': {'game_id': gid, 'competition_id': cid, 'season': 2026, 'round': r.get('round') or ''},
            'synced_at': now_iso,
        })
    cnt = upsert_finished_matches(out_rows)
    print(f'Uploaded {cnt} finished_matches (2026 EU+SEA CSV seed, preserved {len(preserve_ids)} tmapi-alpha lineup rows)')
    return cnt


if __name__ == '__main__':
    seed_all(sys.argv[1] if len(sys.argv) > 1 else BASE_DIR)
