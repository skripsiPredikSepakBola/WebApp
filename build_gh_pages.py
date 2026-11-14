import json
import os
import shutil
import sys
from datetime import datetime, timezone

import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

SITE_DIR = os.path.join(BASE_DIR, '_site')
DATA_OUT = os.path.join(SITE_DIR, 'data')
LEAGUES_OUT = os.path.join(DATA_OUT, 'leagues')
SHARD_COUNT = 16


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))


def export_hgbt(model):
    """Export HistGradientBoosting tree predictors and baseline to exact JSON arrays."""
    trees = []
    for iter_trees in model._predictors:
        iter_list = []
        for t in iter_trees:
            nd = t.nodes
            iter_list.append({
                'th': [round(float(x), 8) for x in nd['num_threshold']],
                'f': [int(x) for x in nd['feature_idx']],
                'l': [int(x) for x in nd['left']],
                'r': [int(x) for x in nd['right']],
                'v': [round(float(x), 8) for x in nd['value']],
                'lf': [int(x) for x in nd['is_leaf']],
                'mg': [int(x) for x in nd['missing_go_to_left']],
            })
        trees.append(iter_list)
    base = np.asarray(model._baseline_prediction, dtype=float).reshape(-1).tolist()
    return {'base': [round(float(x), 8) for x in base], 'trees': trees}


def eval_hgbt_row(exp, x):
    """Evaluate exported HistGradientBoosting JSON model on a single feature vector."""
    raw = list(exp['base'])
    k = len(raw)
    for iter_trees in exp['trees']:
        for c in range(k):
            t = iter_trees[c]
            idx = 0
            while not t['lf'][idx]:
                f_idx = t['f'][idx]
                val = x[f_idx]
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    idx = t['l'][idx] if t['mg'][idx] else t['r'][idx]
                elif val <= t['th'][idx]:
                    idx = t['l'][idx]
                else:
                    idx = t['r'][idx]
            raw[c] += t['v'][idx]
    return raw


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if type(obj).__module__ == 'numpy':
        v = obj.item()
        return None if isinstance(v, float) and (np.isnan(v) or np.isinf(v)) else v
    return obj


def _shard_idx(key):
    try:
        return abs(int(key)) % SHARD_COUNT
    except (TypeError, ValueError):
        return sum(ord(ch) for ch in str(key)) % SHARD_COUNT


def _apply_live_supabase_updates(m):
    try:
        sb_url, _ = m._sb_cfg()
        if not sb_url:
            return 0
        rows = m._sb_req('players?select=id,club,pos,rating,age,val,goals_per_90,total_goals&order=updated_at.desc&limit=200') or []
        if not rows:
            return 0
        club_norm_to_id = m.explorer_bundle.get('club_norm_to_id') or {}
        applied = 0
        for r in rows:
            p = m.player_by_id.get(r.get('id'))
            if p is None:
                continue
            if r.get('club') and r['club'] != p.get('club'):
                p['club'] = r['club']
                cid = club_norm_to_id.get(m.normalize_text(r['club']))
                if cid is not None:
                    p['club_id'] = cid
            if r.get('pos'):
                p['pos'] = r['pos']
            if r.get('rating') is not None:
                p['rating'] = round(float(r['rating']), 1)
            if r.get('age') is not None:
                p['age'] = round(float(r['age']), 1)
            if r.get('val') is not None:
                p['val'] = float(r['val'])
            if r.get('goals_per_90') is not None:
                p['goals_per_90'] = round(float(r['goals_per_90']), 3)
            if r.get('total_goals') is not None:
                p['total_goals'] = int(r['total_goals'])
            applied += 1
        return applied
    except Exception as e:
        print(f'Warning: live Supabase delta check skipped: {e}')
        return 0


def build_site():
    import app as m

    m._ensure_models()
    m._ensure_hist()
    live_updated = _apply_live_supabase_updates(m)

    if os.path.exists(SITE_DIR):
        shutil.rmtree(SITE_DIR)
    os.makedirs(os.path.join(SITE_DIR, 'static', 'css'), exist_ok=True)
    os.makedirs(os.path.join(SITE_DIR, 'static', 'js'), exist_ok=True)
    os.makedirs(LEAGUES_OUT, exist_ok=True)

    with open(os.path.join(SITE_DIR, '.nojekyll'), 'w', encoding='utf-8') as f:
        f.write('')

    shutil.copy2(os.path.join(BASE_DIR, 'templates', 'index.html'), os.path.join(SITE_DIR, 'index.html'))
    shutil.copy2(os.path.join(BASE_DIR, 'static', 'css', 'style.css'), os.path.join(SITE_DIR, 'static', 'css', 'style.css'))
    shutil.copy2(os.path.join(BASE_DIR, 'static', 'js', 'app.js'), os.path.join(SITE_DIR, 'static', 'js', 'app.js'))
    shutil.copy2(os.path.join(BASE_DIR, 'static', 'js', 'gh-pages-engine.js'), os.path.join(SITE_DIR, 'static', 'js', 'gh-pages-engine.js'))

    # Core player, preset & model artifacts
    _write_json(os.path.join(DATA_OUT, 'boot_players.json'), _json_safe(m.boot_players))
    _write_json(os.path.join(DATA_OUT, 'players_full.json'), _json_safe(m.players_lite))
    _write_json(os.path.join(DATA_OUT, 'presets.json'), _json_safe(m.presets))
    _write_json(os.path.join(DATA_OUT, 'categories.json'), _json_safe(m.categories))
    _write_json(os.path.join(DATA_OUT, 'preset_meta.json'), _json_safe(m.preset_meta))
    _write_json(os.path.join(DATA_OUT, 'historical_presets.json'), _json_safe(m.historical_presets))

    thesis_path = os.path.join(BASE_DIR, 'academic_report_data.json')
    if os.path.exists(thesis_path):
        shutil.copy2(thesis_path, os.path.join(DATA_OUT, 'thesis_metrics.json'))

    models_payload = {
        'feature_cols': list(m.advanced_features),
        'model_3class': export_hgbt(m.model_advanced_3class),
        'model_xg': export_hgbt(m.model_advanced_xg),
    }
    _write_json(os.path.join(DATA_OUT, 'models.json'), models_payload)

    client = m.app.test_client()

    # Sync status & recent matches snapshot at build time
    sync_status = client.get('/api/sync/status').get_json() or {}
    build_iso = datetime.now(timezone.utc).isoformat()
    sync_status['deployment_mode'] = 'github_pages'
    if not sync_status.get('last_sync'):
        sync_status['last_sync'] = build_iso
    if not sync_status.get('last_run'):
        sync_status['last_run'] = build_iso
    if live_updated and not sync_status.get('players_updated'):
        sync_status['players_updated'] = live_updated
    _write_json(os.path.join(DATA_OUT, 'sync_status.json'), _json_safe(sync_status))

    recent_data = client.get('/api/matches/recent').get_json() or {'finished_matches': [], 'recent_predictions': []}
    _write_json(os.path.join(DATA_OUT, 'recent_matches.json'), _json_safe(recent_data))

    overview_data = client.get('/api/explore/overview').get_json() or {}
    _write_json(os.path.join(DATA_OUT, 'overview.json'), _json_safe(overview_data))

    leagues_data = client.get('/api/explore/leagues').get_json() or {'regions': [], 'leagues': []}
    leagues_data['leagues_meta'] = m.explorer_bundle.get('leagues_meta', {})
    _write_json(os.path.join(DATA_OUT, 'leagues.json'), _json_safe(leagues_data))

    # Per-league standings & stats JSON files
    leagues_list = m.explorer_bundle.get('leagues', [])
    for lg in leagues_list:
        cid = lg['comp_id']
        avail = lg.get('available_seasons') or [2026]
        seasons_map = {}
        for s in avail:
            res = client.get('/api/explore/league', query_string={'comp_id': cid, 'season': s}).get_json()
            if res and res.get('status') == 'success':
                seasons_map[str(s)] = {
                    'summary': res.get('summary', {}),
                    'standings': res.get('standings', []),
                    'top_scorers': res.get('top_scorers', []),
                    'top_assisters': res.get('top_assisters', []),
                    'top_rated': res.get('top_rated', []),
                    'recent_matches': res.get('recent_matches', []),
                }
        _write_json(os.path.join(LEAGUES_OUT, f'{cid}.json'), _json_safe({
            'league': lg,
            'available_seasons': avail,
            'seasons': seasons_map,
        }))

    # Countries
    countries = m.explorer_bundle.get('countries', [])
    _write_json(os.path.join(DATA_OUT, 'countries.json'), _json_safe(countries))

    # Clubs light + 16 extras shards
    clubs_light = m._exp_blob('blob_clubs_light') or {}
    _write_json(os.path.join(DATA_OUT, 'clubs_light.json'), _json_safe({
        'clubs': list(clubs_light.values()),
        'club_norm_to_id': m.explorer_bundle.get('club_norm_to_id', {}),
    }))

    club_extras = m._exp_blob('blob_club_extras') or {}
    club_shards = [{} for _ in range(SHARD_COUNT)]
    for cid_str, extra in club_extras.items():
        club_shards[_shard_idx(cid_str)][str(cid_str)] = extra
    for idx, shard in enumerate(club_shards):
        _write_json(os.path.join(DATA_OUT, f'clubs_extras_shard_{idx}.json'), _json_safe(shard))

    # Player details + seasons + recent snapshots in 16 shards
    p_details = m._exp_blob('blob_player_details') or {}
    p_seasons = m._exp_blob('blob_player_seasons') or {}
    p_shards = [{'details': {}, 'seasons': {}, 'snapshots': {}} for _ in range(SHARD_COUNT)]
    for pid_str, det in p_details.items():
        p_shards[_shard_idx(pid_str)]['details'][str(pid_str)] = det
    for pid_str, sea in p_seasons.items():
        p_shards[_shard_idx(pid_str)]['seasons'][str(pid_str)] = sea
    for pid, rows in (m.snap_rows or {}).items():
        p_shards[_shard_idx(pid)]['snapshots'][str(pid)] = rows[-36:]
    for idx, shard in enumerate(p_shards):
        _write_json(os.path.join(DATA_OUT, f'player_details_shard_{idx}.json'), _json_safe(shard))

    total_bytes = sum(
        os.path.getsize(os.path.join(dp, fn))
        for dp, _, fns in os.walk(SITE_DIR)
        for fn in fns
    )
    print(f'Built GitHub Pages _site/ successfully ({total_bytes / (1024 * 1024):.1f} MB, {len(leagues_list)} leagues, {SHARD_COUNT} shards).')


if __name__ == '__main__':
    build_site()
