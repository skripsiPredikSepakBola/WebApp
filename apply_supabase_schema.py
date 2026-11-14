import json
import os
import re
import urllib.error
import urllib.request

from sync_matches import _load_dotenv, _sb_cfg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')


def _get_openapi_spec(url, key):
    req = urllib.request.Request(
        f'{url}/rest/v1/',
        headers={'apikey': key, 'Authorization': f'Bearer {key}', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _inspect_schema(url, key):
    spec = _get_openapi_spec(url, key)
    defs = spec.get('definitions') or {}
    paths = spec.get('paths') or {}
    players_props = list((defs.get('players') or {}).get('properties', {}).keys())
    snap_props = list((defs.get('player_snapshots') or {}).get('properties', {}).keys())
    return {
        'tables': sorted(defs.keys()),
        'players_has_report_date': 'report_date' in players_props,
        'players_columns': players_props,
        'has_player_snapshots': 'player_snapshots' in defs,
        'player_snapshots_columns': snap_props,
        'has_exec_sql_rpc': '/rpc/exec_sql' in paths,
    }


def _try_database_url(sql):
    db_url = os.environ.get('DATABASE_URL', '').strip()
    if not db_url:
        return False, 'DATABASE_URL not set'
    for mod_name in ('psycopg', 'psycopg2'):
        try:
            mod = __import__(mod_name)
        except ImportError:
            continue
        try:
            with mod.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                conn.commit()
            return True, f'Applied schema.sql via {mod_name}'
        except Exception as e:
            return False, f'{mod_name} failed: {e}'
    return False, 'DATABASE_URL set but neither psycopg nor psycopg2 is installed'


def _try_management_api(url, sql):
    token = os.environ.get('SUPABASE_ACCESS_TOKEN', '').strip()
    if not token:
        return False, 'SUPABASE_ACCESS_TOKEN not set'
    m = re.match(r'^https?://([a-z0-9-]+)\.supabase\.co', url)
    if not m:
        return False, 'Could not parse Supabase project ref from SUPABASE_URL'
    ref = m.group(1)
    req = urllib.request.Request(
        f'https://api.supabase.com/v1/projects/{ref}/database/query',
        data=json.dumps({'query': sql}).encode('utf-8'),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, f'Applied schema.sql via Supabase Management API (HTTP {resp.status})'
    except urllib.error.HTTPError as e:
        return False, f'Management API HTTP {e.code}: {e.read().decode("utf-8", errors="replace")}'
    except Exception as e:
        return False, f'Management API failed: {e}'


def _try_exec_sql_rpc(url, key, sql, has_rpc):
    if not has_rpc:
        return False, 'PostgREST /rpc/exec_sql not exposed'
    req = urllib.request.Request(
        f'{url}/rest/v1/rpc/exec_sql',
        data=json.dumps({'sql': sql}).encode('utf-8'),
        headers={
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, f'Applied schema.sql via /rpc/exec_sql (HTTP {resp.status})'
    except urllib.error.HTTPError as e:
        return False, f'/rpc/exec_sql HTTP {e.code}: {e.read().decode("utf-8", errors="replace")}'


def apply_schema():
    _load_dotenv()
    url, key = _sb_cfg()
    if not url or not key:
        print('Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing).')
        return {'configured': False}

    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        sql = f.read()

    before = _inspect_schema(url, key)
    print('Supabase OpenAPI tables:', before['tables'])
    print('players.report_date present:', before['players_has_report_date'])
    print('player_snapshots table present:', before['has_player_snapshots'])

    if before['players_has_report_date'] and before['has_player_snapshots']:
        print('Supabase schema is already up to date.')
        return {'configured': True, 'applied': True, 'schema': before}

    attempts = [
        _try_database_url(sql),
        _try_management_api(url, sql),
        _try_exec_sql_rpc(url, key, sql, before['has_exec_sql_rpc']),
    ]
    for ok, msg in attempts:
        if ok:
            print(msg)
            after = _inspect_schema(url, key)
            print('Post-migration players.report_date:', after['players_has_report_date'], 'player_snapshots:', after['has_player_snapshots'])
            return {'configured': True, 'applied': True, 'method': msg, 'schema': after}
        print('DDL channel skipped:', msg)

    print('\nAction required in Supabase Dashboard -> SQL Editor (DDL cannot execute via PostgREST service key alone):')
    print(
        "ALTER TABLE players ADD COLUMN IF NOT EXISTS report_date DATE DEFAULT '2026-11-01';\n"
        "CREATE TABLE IF NOT EXISTS player_snapshots (\n"
        "  player_id BIGINT NOT NULL,\n"
        "  report_date DATE NOT NULL,\n"
        "  club TEXT,\n"
        "  rating REAL,\n"
        "  val REAL,\n"
        "  age REAL,\n"
        "  goals_per_90 REAL,\n"
        "  total_goals INTEGER,\n"
        "  minutes_30d INTEGER,\n"
        "  goals_30d INTEGER,\n"
        "  assists_30d INTEGER,\n"
        "  PRIMARY KEY (player_id, report_date)\n"
        ");"
    )
    return {'configured': True, 'applied': False, 'schema': before}


if __name__ == '__main__':
    apply_schema()
