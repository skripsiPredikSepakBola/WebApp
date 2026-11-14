import http.client
import json
import os
import time
import urllib.parse
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

TMAPI_BASE = 'https://tmapi-alpha.transfermarkt.technology'
TMAPI_HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
_PLAYER_SELECT_BASE = 'id,name,full_name,tm_name,club,nat,pos,rating,age,height,val,goals_per_90,total_goals'
_TM_POS_MAP = {
    'GOALKEEPER': 'GK', 'GK': 'GK',
    'DEFENDER': 'DEF', 'DEFENCE': 'DEF',
    'MIDFIELDER': 'MID', 'MIDFIELD': 'MID',
    'STRIKER': 'ATT', 'ATTACK': 'ATT', 'ATTACKER': 'ATT', 'FORWARD': 'ATT',
}
_SUB_POS_TO_ROLE = {
    'Goalkeeper': 'GK',
    'Centre-Back': 'CB',
    'Left-Back': 'LB',
    'Right-Back': 'RB',
    'Defensive Midfield': 'CDM',
    'Central Midfield': 'CM',
    'Attacking Midfield': 'CAM',
    'Left Midfield': 'LM',
    'Right Midfield': 'RM',
    'Left Winger': 'LW',
    'Right Winger': 'RW',
    'Second Striker': 'CF',
    'Centre-Forward': 'ST',
}
_SHORT_POS_TO_ROLE = {
    'GK': 'GK', 'CB': 'CB', 'LB': 'LB', 'RB': 'RB',
    'DM': 'CDM', 'CDM': 'CDM', 'CM': 'CM', 'AM': 'CAM', 'CAM': 'CAM',
    'LM': 'LM', 'RM': 'RM', 'LW': 'LW', 'RW': 'RW',
    'SS': 'CF', 'CF': 'CF', 'ST': 'ST',
}
_POS_FALLBACK = {'GK': 'GK', 'DEF': 'CB', 'MID': 'CM', 'ATT': 'ST'}

_LOCAL_SYNC_STATE = {
    'finished_matches': [],
    'player_deltas': {},
    'last_sync': None,
    'last_result': None,
}


def get_local_sync_state():
    return _LOCAL_SYNC_STATE


def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

def _fetch_json(url, headers, method='GET', body=None):
    hdrs = {'User-Agent': 'PitchPulseAI/1.0', 'Accept': 'application/json', **headers}
    data = json.dumps(body).encode('utf-8') if body is not None else None
    idempotent = (method == 'GET') or ('on_conflict=' in url)
    max_attempts = 4 if idempotent else 1
    for attempt in range(max_attempts):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='replace')
            if idempotent and e.code in (429, 502, 503, 504) and attempt < max_attempts - 1:
                time.sleep(0.5 * (2 ** attempt))
                continue
            raise RuntimeError(f'HTTP {e.code} on {url}: {detail}') from e
        except (TimeoutError, urllib.error.URLError, OSError, http.client.HTTPException):
            if not idempotent or attempt == max_attempts - 1:
                raise
            time.sleep(0.5 * (2 ** attempt))


def _sb_cfg():
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_KEY', '').strip()
    if not url or not key:
        return None, None
    return url, key


def _sb_req(path, method='GET', body=None, prefer=None, extra_headers=None):
    url, key = _sb_cfg()
    if not url:
        raise RuntimeError('Set SUPABASE_URL and SUPABASE_KEY env vars')
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }
    if prefer:
        headers['Prefer'] = prefer
    if extra_headers:
        headers.update(extra_headers)
    return _fetch_json(f'{url}/rest/v1/{path}', headers, method=method, body=body)


def load_all_players():
    url, _ = _sb_cfg()
    if not url:
        return []
    cols = f'{_PLAYER_SELECT_BASE},report_date'
    out, offset, step = [], 0, 1000
    while True:
        try:
            batch = _sb_req(
                f'players?select={cols}&order=id.asc',
                extra_headers={'Range': f'{offset}-{offset + step - 1}'}
            ) or []
        except RuntimeError as e:
            if offset == 0 and 'HTTP 400' in str(e) and 'report_date' in str(e):
                cols = _PLAYER_SELECT_BASE
                continue
            raise
        out.extend(batch)
        if len(batch) < step:
            break
        offset += step
    return out


def load_all_presets():
    url, _ = _sb_cfg()
    if not url:
        return {}, {}
    rows, offset, step = [], 0, 1000
    while True:
        batch = _sb_req(
            'presets?select=name,category,formation,starters,subs&order=name.asc',
            extra_headers={'Range': f'{offset}-{offset + step - 1}'}
        ) or []
        rows.extend(batch)
        if len(batch) < step:
            break
        offset += step
    presets, cats = {}, {}
    for r in rows:
        presets[r['name']] = {'formation': r.get('formation', '4-3-3'), 'starters': r.get('starters', []), 'subs': r.get('subs', [])}
        cats.setdefault(r.get('category', 'Other'), []).append(r['name'])
    return presets, cats


def upsert_finished_matches(rows):
    if not rows:
        return 0
    for i in range(0, len(rows), 50):
        _sb_req('finished_matches?on_conflict=match_id', method='POST', body=rows[i:i + 50], prefer='resolution=merge-duplicates,return=minimal')
    return len(rows)


def log_prediction(home_team, away_team, p_home, p_draw, p_away, xg_home, xg_away, predicted_score, verdict):
    url, _ = _sb_cfg()
    if not url:
        return
    _sb_req('predictions', method='POST', body=[{
        'home_team': home_team,
        'away_team': away_team,
        'p_home': p_home,
        'p_draw': p_draw,
        'p_away': p_away,
        'xg_home': xg_home,
        'xg_away': xg_away,
        'predicted_score': predicted_score,
        'verdict': verdict,
    }], prefer='return=minimal')


def get_recent_data():
    url, _ = _sb_cfg()
    if not url:
        return {
            'finished_matches': list(_LOCAL_SYNC_STATE.get('finished_matches') or [])[:20],
            'recent_predictions': [],
            'configured': False,
        }
    finished = _sb_req('finished_matches?select=match_id,source,league,match_date,home_team,away_team,home_goals,away_goals,status&order=match_date.desc&limit=20') or []
    preds = _sb_req('predictions?select=id,created_at,home_team,away_team,p_home,p_draw,p_away,predicted_score,verdict&order=id.desc&limit=10') or []
    return {'finished_matches': finished, 'recent_predictions': preds, 'configured': True}


def get_player_overrides():
    url, _ = _sb_cfg()
    if not url:
        return list((_LOCAL_SYNC_STATE.get('player_deltas') or {}).values())
    rows = _sb_req('players?select=id,club,pos,rating,age,goals_per_90,total_goals&limit=5000') or []
    deltas = _LOCAL_SYNC_STATE.get('player_deltas') or {}
    if deltas:
        for r in rows:
            d = deltas.get(r.get('id'))
            if d:
                if d.get('role'):
                    r['role'] = d['role']
                if d.get('sub_pos'):
                    r['sub_pos'] = d['sub_pos']
    return rows


def upsert_players(rows):
    if not rows:
        return 0
    for i in range(0, len(rows), 500):
        _sb_req('players?on_conflict=id', method='POST', body=rows[i:i + 500], prefer='resolution=merge-duplicates,return=minimal')
    return len(rows)


def _tmapi_get(path):
    try:
        return _fetch_json(f'{TMAPI_BASE}/{path.lstrip("/")}', TMAPI_HEADERS) or {}
    except Exception:
        return {}


def _tmapi_batches(endpoint, ids, chunk_size=30):
    clean_ids = [str(i) for i in ids if i is not None and str(i) != '']
    if not clean_ids:
        return []
    chunks = [clean_ids[i:i + chunk_size] for i in range(0, len(clean_ids), chunk_size)]

    def _fetch_chunk(chunk):
        time.sleep(0.05)
        qs = '&'.join(f'ids[]={urllib.parse.quote(x)}' for x in chunk)
        return _tmapi_get(f'{endpoint}?{qs}').get('data') or []

    out = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for items in pool.map(_fetch_chunk, chunks):
            out.extend(items)
    return out


def _parse_utc(dt_str):
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _map_tmapi_pos(attrs):
    raw_pos = attrs.get('positionGroup') or (attrs.get('position') or {}).get('category') or ''
    return _TM_POS_MAP.get(str(raw_pos).strip().upper())


def _map_tmapi_role(attrs, fallback_pos=None):
    pos_obj = attrs.get('position') or {}
    sub_name = str(
        pos_obj.get('name')
        or attrs.get('subPosition')
        or attrs.get('mainPosition')
        or ''
    ).strip()
    if sub_name in _SUB_POS_TO_ROLE:
        return sub_name, _SUB_POS_TO_ROLE[sub_name]
    short_name = str(pos_obj.get('shortName') or '').strip().upper()
    if short_name in _SHORT_POS_TO_ROLE:
        role = _SHORT_POS_TO_ROLE[short_name]
        return (sub_name or role), role
    p4 = _map_tmapi_pos(attrs) or fallback_pos or 'MID'
    return sub_name, _POS_FALLBACK.get(p4, 'CM')


def sync_tmapi_recent(
    competitions=('GB1', 'ES1', 'L1', 'IT1', 'FR1', 'CL', 'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'),
    days_back=7,
    allow_local=False,
):
    """Sync recent finished matches (with lineups) and squad club/valuation/role updates via Transfermarkt JSON API."""
    has_sb = bool(_sb_cfg()[0])
    if not has_sb and not allow_local:
        return {'matches': 0, 'players_updated': 0, 'roles_mapped': 0}

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    season = now_utc.year if now_utc.month >= 7 else now_utc.year - 1
    cutoff = now_utc - timedelta(days=days_back)

    recent_game_ids, table_club_ids = [], []
    seen_games, seen_clubs = set(), set()

    for code in competitions:
        fx = _tmapi_get(f'competition/{code}/fixtures?season={season}')
        for grp in (fx.get('data') or {}).get('fixtures') or []:
            for g in grp.get('games') or []:
                if not g.get('isFinished'):
                    continue
                dt = _parse_utc(((g.get('baseDetails') or {}).get('date') or {}).get('dateTimeUTC'))
                gid = g.get('id')
                if gid and dt and dt >= cutoff and str(gid) not in seen_games:
                    seen_games.add(str(gid))
                    recent_game_ids.append(str(gid))

        tbl = _tmapi_get(f'competition/{code}/table?season={season}')
        for t in (tbl.get('data') or {}).get('tables') or []:
            for c in t.get('clubs') or []:
                cid = c.get('clubId')
                if cid and str(cid) not in seen_clubs:
                    seen_clubs.add(str(cid))
                    table_club_ids.append(str(cid))

    games = _tmapi_batches('games', recent_game_ids)
    all_club_ids = list(dict.fromkeys(
        table_club_ids
        + [str((g.get('homeClub') or {}).get('clubId') or '') for g in games]
        + [str((g.get('awayClub') or {}).get('clubId') or '') for g in games]
    ))
    club_names = {
        str(c['id']): c.get('name', '')
        for c in _tmapi_batches('clubs', all_club_ids)
        if c.get('id') and c.get('name')
    }

    match_rows = []
    for g in games:
        gid = g.get('id')
        if not gid:
            continue
        base = g.get('baseDetails') or {}
        score = g.get('score') or {}
        hc_id = str((g.get('homeClub') or {}).get('clubId') or '')
        ac_id = str((g.get('awayClub') or {}).get('clubId') or '')
        match_rows.append({
            'match_id': f'tmapi:{gid}',
            'source': 'tmapi-alpha',
            'league': (base.get('competition') or {}).get('name') or base.get('competitionId') or '',
            'match_date': (base.get('date') or {}).get('dateTimeUTC') or None,
            'home_team': club_names.get(hc_id, hc_id),
            'away_team': club_names.get(ac_id, ac_id),
            'home_goals': score.get('home'),
            'away_goals': score.get('away'),
            'status': 'FT',
            'raw_json': g,
            'synced_at': now_iso,
        })
    _LOCAL_SYNC_STATE['finished_matches'] = match_rows[:50]
    matches_synced = upsert_finished_matches(match_rows) if has_sb else len(match_rows)

    player_club = {}
    def _fetch_squad(cid):
        time.sleep(0.05)
        sq = _tmapi_get(f'club/{cid}/squad?season={season}')
        return cid, (sq.get('data') or {}).get('squad') or []

    with ThreadPoolExecutor(max_workers=2) as pool:
        for cid, squad in pool.map(_fetch_squad, table_club_ids):
            cname = club_names.get(cid, '')
            if not cname:
                continue
            for sp in squad:
                pid = sp.get('playerId')
                if pid is not None and str(pid).isdigit():
                    player_club[int(pid)] = cname

    players_updated = 0
    roles_mapped = 0
    if player_club:
        all_p = load_all_players() if has_sb else []
        by_id = {p['id']: p for p in all_p}
        tm_players = _tmapi_batches('players', list(player_club.keys()))
        updates = {}
        for pl in tm_players:
            pid_raw = pl.get('id')
            if pid_raw is None or not str(pid_raw).isdigit():
                continue
            pid = int(pid_raw)
            base = by_id.get(pid) or {'id': pid, 'name': pl.get('name') or str(pid)}
            attrs = pl.get('attributes') or {}
            mv = ((pl.get('marketValueDetails') or {}).get('current') or {}).get('value')
            age = (pl.get('lifeDates') or {}).get('age')
            h_m = attrs.get('height')
            new_club = player_club.get(pid) or base.get('club')
            new_val = float(mv) if mv is not None else base.get('val')
            new_pos = _map_tmapi_pos(attrs) or base.get('pos')
            new_sub_pos, new_role = _map_tmapi_role(attrs, new_pos)
            if new_role:
                roles_mapped += 1
            new_age = float(age) if age is not None else base.get('age')
            new_height = round(float(h_m) * 100) if h_m else base.get('height')
            _LOCAL_SYNC_STATE['player_deltas'][pid] = {
                'id': pid,
                'club': new_club,
                'pos': new_pos,
                'sub_pos': new_sub_pos,
                'role': new_role,
                'age': new_age,
                'height': new_height,
                'val': new_val,
                'is_former': False,
                'last_season': season,
            }
            if not has_sb or pid not in by_id:
                continue
            if (
                new_club == base.get('club')
                and float(new_val or 0) == float(base.get('val') or 0)
                and new_pos == base.get('pos')
            ):
                continue
            updates[pid] = {
                'id': pid,
                'name': base['name'],
                'full_name': base.get('full_name'),
                'tm_name': base.get('tm_name'),
                'club': new_club,
                'nat': base.get('nat'),
                'pos': new_pos,
                'rating': base.get('rating'),
                'age': new_age,
                'height': new_height,
                'val': new_val,
                'goals_per_90': base.get('goals_per_90'),
                'total_goals': base.get('total_goals'),
                'updated_at': now_iso,
            }
        players_updated = upsert_players(list(updates.values())) if has_sb else len(_LOCAL_SYNC_STATE['player_deltas'])

    return {'matches': matches_synced, 'players_updated': players_updated, 'roles_mapped': roles_mapped}


def sync_squad_players_fd(api_key, competitions=('PL', 'PD', 'BL1', 'SA', 'FL1', 'CL')):
    # ponytail: football-data.org free tier gives full squads + clubs for top competitions
    all_p = load_all_players()
    if not all_p:
        return 0
    by_name = {p['name'].lower(): p for p in all_p if p.get('name')}
    now = datetime.now(timezone.utc).isoformat()
    updates = {}
    pos_map = {'Goalkeeper': 'GK', 'Defence': 'DEF', 'Midfield': 'MID', 'Offence': 'ATT'}
    for code in competitions:
        try:
            data = _fetch_json(f'https://api.football-data.org/v4/competitions/{code}/teams', {'X-Auth-Token': api_key})
        except Exception:
            continue
        for team in data.get('teams', []):
            club = team.get('shortName') or team.get('name', '')
            for pl in team.get('squad', []):
                pname = (pl.get('name') or '').lower()
                base = by_name.get(pname)
                if not base:
                    continue
                updates[base['id']] = {
                    'id': base['id'],
                    'name': base['name'],
                    'full_name': base.get('full_name'),
                    'club': club or base.get('club'),
                    'nat': base.get('nat'),
                    'pos': pos_map.get(pl.get('position'), base.get('pos')),
                    'rating': base.get('rating'),
                    'age': base.get('age'),
                    'height': base.get('height'),
                    'val': base.get('val'),
                    'goals_per_90': base.get('goals_per_90'),
                    'total_goals': base.get('total_goals'),
                    'updated_at': now,
                }
    return upsert_players(list(updates.values()))

def sync_api_football(api_key, date_str=None):
    date_str = date_str or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    data = _fetch_json(f'https://v3.football.api-sports.io/fixtures?date={date_str}&status=FT', {'x-apisports-key': api_key})
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for idx, m in enumerate(data.get('response', [])):
        fx_id = m.get('fixture', {}).get('id')
        # ponytail: cap lineup calls to 20/run so 100 req/day free tier lasts
        if fx_id and idx < 20:
            try:
                lu = _fetch_json(f'https://v3.football.api-sports.io/fixtures/lineups?fixture={fx_id}', {'x-apisports-key': api_key})
                m['lineups'] = lu.get('response', [])
            except Exception:
                pass
        rows.append({
            'match_id': f"apifootball:{fx_id}",
            'source': 'api-football',
            'league': m.get('league', {}).get('name', ''),
            'match_date': m.get('fixture', {}).get('date') or None,
            'home_team': m.get('teams', {}).get('home', {}).get('name', ''),
            'away_team': m.get('teams', {}).get('away', {}).get('name', ''),
            'home_goals': m.get('goals', {}).get('home'),
            'away_goals': m.get('goals', {}).get('away'),
            'status': m.get('fixture', {}).get('status', {}).get('short', 'FT'),
            'raw_json': m,
            'synced_at': now,
        })
    return upsert_finished_matches(rows)


def sync_football_data(api_key, days_back=1):
    today = datetime.now(timezone.utc).date()
    d_from, d_to = (today - timedelta(days=days_back)).isoformat(), today.isoformat()
    data = _fetch_json(f'https://api.football-data.org/v4/matches?status=FINISHED&dateFrom={d_from}&dateTo={d_to}', {'X-Auth-Token': api_key})
    now = datetime.now(timezone.utc).isoformat()
    rows = [{
        'match_id': f"fdorg:{m.get('id')}",
        'source': 'football-data.org',
        'league': m.get('competition', {}).get('name', ''),
        'match_date': m.get('utcDate') or None,
        'home_team': m.get('homeTeam', {}).get('name', ''),
        'away_team': m.get('awayTeam', {}).get('name', ''),
        'home_goals': m.get('score', {}).get('fullTime', {}).get('home'),
        'away_goals': m.get('score', {}).get('fullTime', {}).get('away'),
        'status': m.get('status', 'FINISHED'),
        'raw_json': m,
        'synced_at': now,
    } for m in data.get('matches', [])]
    return upsert_finished_matches(rows)


def sync_all(allow_local=False):
    url, _ = _sb_cfg()
    if not url and not allow_local:
        return {'error': 'Set SUPABASE_URL and SUPABASE_KEY env vars', 'configured': False}
    synced = {'configured': bool(url)}
    try:
        tm = sync_tmapi_recent(allow_local=allow_local)
        synced['tmapi_matches'] = tm.get('matches', 0)
        synced['tmapi_players_updated'] = tm.get('players_updated', 0)
        synced['tmapi_roles_mapped'] = tm.get('roles_mapped', 0)
    except Exception as e:
        synced['tmapi_error'] = str(e)
    af_key = os.environ.get('API_FOOTBALL_KEY', '').strip()
    fd_key = os.environ.get('FOOTBALL_DATA_KEY', '').strip()
    if url and af_key:
        try:
            synced['api_football'] = sync_api_football(af_key)
        except Exception as e:
            synced['api_football_error'] = str(e)
    if url and fd_key:
        try:
            synced['football_data'] = sync_football_data(fd_key)
            synced['players_updated'] = sync_squad_players_fd(fd_key)
        except Exception as e:
            synced['football_data_error'] = str(e)
    _LOCAL_SYNC_STATE['last_sync'] = datetime.now(timezone.utc).isoformat()
    _LOCAL_SYNC_STATE['last_result'] = synced
    return synced



def backfill_football_data(api_key, start_date='2026-08-17', end_date=None):
    from datetime import date
    cur = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date) if end_date else datetime.now(timezone.utc).date()
    total = 0
    while cur <= end:
        nxt = min(cur + timedelta(days=9), end)
        data = _fetch_json(
            f'https://api.football-data.org/v4/matches?status=FINISHED&dateFrom={cur.isoformat()}&dateTo={nxt.isoformat()}',
            {'X-Auth-Token': api_key}
        )
        now = datetime.now(timezone.utc).isoformat()
        rows = [{
            'match_id': f"fdorg:{m.get('id')}",
            'source': 'football-data.org',
            'league': m.get('competition', {}).get('name', ''),
            'match_date': m.get('utcDate') or None,
            'home_team': m.get('homeTeam', {}).get('name', ''),
            'away_team': m.get('awayTeam', {}).get('name', ''),
            'home_goals': m.get('score', {}).get('fullTime', {}).get('home'),
            'away_goals': m.get('score', {}).get('fullTime', {}).get('away'),
            'status': m.get('status', 'FINISHED'),
            'raw_json': m,
            'synced_at': now,
        } for m in data.get('matches', [])]
        total += upsert_finished_matches(rows)
        cur = nxt + timedelta(days=1)
    return total


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'backfill':
        fd_key = os.environ.get('FOOTBALL_DATA_KEY', '').strip()
        if not fd_key:
            raise SystemExit('Set FOOTBALL_DATA_KEY in .env first')
        start = sys.argv[2] if len(sys.argv) > 2 else '2026-08-17'
        end = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps({'backfilled_matches': backfill_football_data(fd_key, start, end), 'players_updated': sync_squad_players_fd(fd_key)}))
    else:
        print(json.dumps(sync_all()))
