import os
import sys
import json
import math
import gc
import pickle
import threading
import time
import unicodedata
import re
import zlib
from bisect import bisect_right
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify
from collections import Counter
from sync_matches import _sb_cfg, _sb_req, get_local_sync_state, get_recent_data, load_all_players, load_all_presets, log_prediction, sync_all

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_BOOT_T0 = time.perf_counter()
app = Flask(__name__, static_folder='static', template_folder='templates')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, '.'))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
STARTUP_CACHE_PATH = os.path.join(DATA_DIR, 'startup_cache.joblib')
VALID_FORMATIONS = ('4-3-3', '4-2-3-1', '4-4-2', '3-5-2', '3-4-3', '5-3-2', '5-4-1', '4-1-4-1')

SUB_POS_TO_ROLE = {
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
POS_FALLBACK = {'GK': 'GK', 'DEF': 'CB', 'MID': 'CM', 'ATT': 'ST'}
ROLE_TO_GROUP = {
    'GK': 'GK',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF',
    'CDM': 'MID', 'CM': 'MID', 'CAM': 'MID', 'LM': 'MID', 'RM': 'MID',
    'LW': 'ATT', 'RW': 'ATT', 'CF': 'ATT', 'ST': 'ATT',
}
FORMATION_ROLES = {
    '4-3-3':   ['GK', 'LB', 'CB', 'CB', 'RB', 'CM', 'CDM', 'CM', 'LW', 'ST', 'RW'],
    '4-2-3-1': ['GK', 'LB', 'CB', 'CB', 'RB', 'CDM', 'CDM', 'LW', 'CAM', 'RW', 'ST'],
    '4-4-2':   ['GK', 'LB', 'CB', 'CB', 'RB', 'LM', 'CM', 'CM', 'RM', 'ST', 'CF'],
    '3-5-2':   ['GK', 'CB', 'CB', 'CB', 'LM', 'CDM', 'CAM', 'CM', 'RM', 'ST', 'CF'],
    '3-4-3':   ['GK', 'CB', 'CB', 'CB', 'LM', 'CM', 'CM', 'RM', 'LW', 'ST', 'RW'],
    '5-3-2':   ['GK', 'LB', 'CB', 'CB', 'CB', 'RB', 'CM', 'CDM', 'CM', 'ST', 'CF'],
    '5-4-1':   ['GK', 'LB', 'CB', 'CB', 'CB', 'RB', 'LM', 'CM', 'CM', 'RM', 'ST'],
    '4-1-4-1': ['GK', 'LB', 'CB', 'CB', 'RB', 'CDM', 'LM', 'CM', 'CM', 'RM', 'ST'],
}
GRANULAR_OOP_PENALTY = {
    ('ST', 'CF'): 1, ('CF', 'ST'): 1,
    ('LW', 'RW'): 2, ('RW', 'LW'): 2,
    ('LW', 'LM'): 2, ('LM', 'LW'): 2, ('LW', 'RM'): 2, ('RM', 'LW'): 2,
    ('RW', 'LM'): 2, ('LM', 'RW'): 2, ('RW', 'RM'): 2, ('RM', 'RW'): 2,
    ('CAM', 'CM'): 2, ('CM', 'CAM'): 2,
    ('CM', 'CDM'): 2, ('CDM', 'CM'): 2,
    ('CM', 'LM'): 2, ('LM', 'CM'): 2, ('CM', 'RM'): 2, ('RM', 'CM'): 2,
    ('LM', 'RM'): 2, ('RM', 'LM'): 2,
    ('CAM', 'LW'): 3, ('LW', 'CAM'): 3, ('CAM', 'RW'): 3, ('RW', 'CAM'): 3,
    ('CAM', 'CF'): 3, ('CF', 'CAM'): 3, ('CAM', 'ST'): 4, ('ST', 'CAM'): 4,
    ('CAM', 'LM'): 3, ('LM', 'CAM'): 3, ('CAM', 'RM'): 3, ('RM', 'CAM'): 3,
    ('LB', 'RB'): 3, ('RB', 'LB'): 3,
    ('LB', 'LM'): 3, ('LM', 'LB'): 3, ('RB', 'RM'): 3, ('RM', 'RB'): 3,
    ('LB', 'RM'): 3, ('RM', 'LB'): 3, ('RB', 'LM'): 3, ('LM', 'RB'): 3,
    ('LW', 'ST'): 4, ('RW', 'ST'): 4, ('LW', 'CF'): 4, ('RW', 'CF'): 4,
    ('LB', 'CB'): 4, ('RB', 'CB'): 4,
    ('CDM', 'CB'): 4,
    ('ST', 'LW'): 5, ('ST', 'RW'): 5, ('CF', 'LW'): 5, ('CF', 'RW'): 5,
    ('CB', 'LB'): 5, ('CB', 'RB'): 5,
    ('CB', 'CDM'): 5,
    ('CAM', 'CDM'): 5, ('CDM', 'CAM'): 5,
    ('CDM', 'LM'): 5, ('LM', 'CDM'): 5, ('CDM', 'RM'): 5, ('RM', 'CDM'): 5,
}
GRANULAR_SCORER_WEIGHTS = {
    'ST': 1.05, 'CF': 0.95, 'LW': 0.82, 'RW': 0.82,
    'CAM': 0.58, 'LM': 0.45, 'RM': 0.45, 'CM': 0.35, 'CDM': 0.18,
    'LB': 0.10, 'RB': 0.10, 'CB': 0.07, 'GK': 0.001,
    'ATT': 1.0, 'MID': 0.40, 'DEF': 0.08,
}

# 1. Load Player Database, Presets, Categories, and Historical Snapshots
players_lite, boot_players, player_by_id, player_by_name, presets, categories, preset_meta = [], [], {}, {}, {}, {}, {}
player_search_blobs = []
_blob_snapshots, _blob_historical, _snap_count = None, None, 0
_data_lock = threading.Lock()
_hist_lock = threading.Lock()
_hist_ready = threading.Event()
_models_lock = threading.Lock()
_models_ready = threading.Event()
_pd_mod = None
_np_mod = None
_sync_lock = threading.Lock()
_sync_state = {
    'enabled': os.environ.get('AUTO_SYNC_ENABLED', '1').strip() not in ('0', 'false', 'no'),
    'interval_sec': int(os.environ.get('AUTO_SYNC_INTERVAL_SEC', '21600') or 21600),
    'running': False,
    'last_sync': None,
    'last_error': None,
    'matches_synced': 0,
    'players_updated': 0,
    'last_result': None,
}


def _unpickle_blob(blob):
    if isinstance(blob, (bytes, bytearray)) and len(blob) >= 2 and blob[0] == 0x78:
        blob = zlib.decompress(blob)
    return pickle.loads(blob)


def _fast_load_joblib(path):
    """Load uncompressed joblib files with C pickle for sub-second boot; fall back to joblib.load."""
    with open(path, 'rb') as f:
        magic = f.read(2)
    if len(magic) == 2 and magic[0] == 0x80 and 2 <= magic[1] <= 5:
        gc_was_enabled = gc.isenabled()
        gc.disable()
        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
        finally:
            if gc_was_enabled:
                gc.enable()
    import joblib
    return joblib.load(path)


def _ensure_hist():
    if _hist_ready.is_set():
        return
    with _hist_lock:
        if _hist_ready.is_set():
            return
        if _blob_snapshots is not None:
            gc_was_enabled = gc.isenabled()
            gc.disable()
            try:
                s_dates, s_rows = _unpickle_blob(_blob_snapshots)
            finally:
                if gc_was_enabled:
                    gc.enable()
            globals()['snap_dates'] = s_dates
            globals()['snap_rows'] = s_rows
        elif 'snap_dates' not in globals():
            globals()['snap_dates'] = {}
            globals()['snap_rows'] = {}
        if _blob_historical is not None:
            hp, hp_norm = _unpickle_blob(_blob_historical)
            globals()['historical_presets'] = hp
            globals()['hist_presets_norm'] = hp_norm
        elif 'historical_presets' not in globals():
            globals()['historical_presets'] = {}
            globals()['hist_presets_norm'] = {}
        _hist_ready.set()


def _ensure_models():
    global _pd_mod, _np_mod
    if _models_ready.is_set():
        return
    with _models_lock:
        if _models_ready.is_set():
            return
        import numpy as np_lib
        import pandas as pd_lib
        import joblib
        _np_mod = np_lib
        _pd_mod = pd_lib
        globals()['model_advanced_3class'] = joblib.load(os.path.join(DATA_DIR, 'model_advanced_3class.joblib'))
        globals()['model_advanced_xg'] = joblib.load(os.path.join(DATA_DIR, 'model_advanced_xg.joblib'))
        globals()['advanced_features'] = joblib.load(os.path.join(DATA_DIR, 'advanced_feature_cols.joblib'))
        _models_ready.set()


def __getattr__(name):
    if name in ('model_advanced_3class', 'model_advanced_xg', 'advanced_features'):
        _ensure_models()
        return globals()[name]
    if name in ('snap_dates', 'snap_rows', 'historical_presets', 'hist_presets_norm'):
        _ensure_hist()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def normalize_text(text):
    if not text: return ''
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()
    return ' '.join(text.split())


def _load_local_json(filename, default):
    for d in (DATA_DIR, ROOT_DIR):
        p = os.path.join(d, filename)
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: failed loading {p}: {e}")
    return default


def load_historical_data():
    import pandas as pd
    if not _hist_ready.is_set() and (_blob_snapshots is not None or _blob_historical is not None):
        _ensure_hist()
    s_dates, s_rows = {}, {}
    snap_path = os.path.join(DATA_DIR, 'player_monthly_snapshots.csv')
    if not os.path.exists(snap_path):
        snap_path = os.path.join(ROOT_DIR, 'player_monthly_snapshots.csv')
    if os.path.exists(snap_path):
        try:
            wanted = {'player_id', 'report_date', 'club', 'rating', 'form_delta', 'val', 'age', 'goals_per_90', 'total_goals'}
            df = pd.read_csv(snap_path, usecols=lambda c: c in wanted, dtype={'report_date': 'str', 'club': 'str'}, low_memory=False)
            if not df.empty and 'player_id' in df.columns and 'report_date' in df.columns:
                df = df.dropna(subset=['player_id', 'report_date'])
                df['player_id'] = pd.to_numeric(df['player_id'], errors='coerce')
                df = df.dropna(subset=['player_id'])
                df['player_id'] = df['player_id'].astype(int)
                df['report_date'] = df['report_date'].astype(str).str.slice(0, 10)
                df = df.sort_values(['player_id', 'report_date'], kind='mergesort')
                n = len(df)
                pids = df['player_id'].tolist()
                rds = df['report_date'].tolist()
                clubs = ['' if pd.isna(x) else str(x) for x in df['club']] if 'club' in df else [''] * n
                ratings = [None if pd.isna(x) else round(float(x), 1) for x in pd.to_numeric(df['rating'], errors='coerce')] if 'rating' in df else [None] * n
                fdeltas = [0.0 if pd.isna(x) else round(float(x), 2) for x in pd.to_numeric(df['form_delta'], errors='coerce')] if 'form_delta' in df else [0.0] * n
                vals = [None if pd.isna(x) else float(x) for x in pd.to_numeric(df['val'], errors='coerce')] if 'val' in df else [None] * n
                ages = [None if pd.isna(x) else round(float(x), 1) for x in pd.to_numeric(df['age'], errors='coerce')] if 'age' in df else [None] * n
                g90s = [None if pd.isna(x) else round(float(x), 3) for x in pd.to_numeric(df['goals_per_90'], errors='coerce')] if 'goals_per_90' in df else [None] * n
                tgs = [None if pd.isna(x) else int(x) for x in pd.to_numeric(df['total_goals'], errors='coerce')] if 'total_goals' in df else [None] * n
                for pid, rd, cl, rt, fd, vl, ag, g9, tg in zip(pids, rds, clubs, ratings, fdeltas, vals, ages, g90s, tgs):
                    if pid not in s_dates:
                        s_dates[pid] = []
                        s_rows[pid] = []
                    s_dates[pid].append(rd)
                    s_rows[pid].append((rd, cl, rt, fd, vl, ag, g9, tg))
        except Exception as e:
            print(f"Warning: failed loading player_monthly_snapshots.csv: {e}")

    hp = {}
    hp_path = os.path.join(DATA_DIR, 'historical_presets.json')
    if not os.path.exists(hp_path):
        hp_path = os.path.join(ROOT_DIR, 'historical_presets.json')
    if os.path.exists(hp_path):
        try:
            with open(hp_path, 'r', encoding='utf-8') as f:
                hp = json.load(f) or {}
        except Exception as e:
            print(f"Warning: failed loading historical_presets.json: {e}")
    with _hist_lock:
        if s_dates or 'snap_dates' not in globals():
            globals()['snap_dates'] = s_dates
            globals()['snap_rows'] = s_rows
            globals()['_snap_count'] = sum(len(v) for v in s_rows.values())
            globals()['_blob_snapshots'] = None
        if hp or 'historical_presets' not in globals():
            globals()['historical_presets'] = hp
            globals()['hist_presets_norm'] = {normalize_text(k): k for k in hp}
            globals()['_blob_historical'] = None
        _hist_ready.set()
    print(f"Loaded historical snapshots for {len(globals().get('snap_dates', {}))} players and {len(globals().get('historical_presets', {}))} historical presets.")


def _compute_boot_players(merged_players, p_by_id, p_by_name, s_blobs, cur_presets):
    preset_pids = set()
    for sq in (cur_presets or {}).values():
        for item in (sq.get('starters') or []) + (sq.get('subs') or []):
            pid = None
            if isinstance(item, dict):
                raw_id = item.get('id')
                if raw_id is not None and raw_id in p_by_id:
                    pid = raw_id
                else:
                    s = item.get('name', '')
                    hit = p_by_name.get(str(s).lower()) or p_by_name.get(normalize_text(s))
                    pid = hit.get('id') if hit else None
            elif isinstance(item, int) and item in p_by_id:
                pid = item
            else:
                s = str(item or '')
                hit = p_by_name.get(s.lower()) or p_by_name.get(normalize_text(s))
                if hit is None:
                    nrm = normalize_text(s)
                    if nrm:
                        for pc, blob in s_blobs:
                            if nrm in blob:
                                hit = pc
                                break
                pid = hit.get('id') if hit else None
            if pid is not None:
                preset_pids.add(pid)
    top_2500 = {p['id'] for p in merged_players[:2500] if p.get('id') is not None}
    boot_ids = preset_pids | top_2500
    return [p for p in merged_players if p.get('id') in boot_ids]


def _build_fallback_preset_meta(cur_presets):
    meta = {}
    club_norm_to_id = explorer_bundle.get('club_norm_to_id') or {}
    for pname in (cur_presets or {}):
        if pname.endswith(' (National Team)'):
            base = pname[:-len(' (National Team)')]
            cobj = _find_country_obj(base)
            crest = (cobj or {}).get('team_image_url') or ''
            entry = {'crest_url': crest, 'club_id': None, 'is_national': True}
            meta[pname] = entry
            meta[normalize_text(pname)] = entry
            meta.setdefault(base, entry)
            meta.setdefault(normalize_text(base), entry)
        elif pname.endswith(' Legends') or pname.endswith(' Icons'):
            base = pname[:-len(' Legends')] if pname.endswith(' Legends') else ''
            cid = club_norm_to_id.get(normalize_text(base)) if base else None
            crest = f'https://tmssl.akamaized.net/images/wappen/head/{cid}.png' if cid else ''
            entry = {'crest_url': crest, 'club_id': cid, 'is_national': False, 'is_legend': True}
            meta[pname] = entry
            meta[normalize_text(pname)] = entry
        else:
            cid = club_norm_to_id.get(normalize_text(pname))
            crest = f'https://tmssl.akamaized.net/images/wappen/head/{cid}.png' if cid else ''
            entry = {'crest_url': crest, 'club_id': cid, 'is_national': False}
            meta[pname] = entry
            meta[normalize_text(pname)] = entry
    return meta


def reload_supabase_data():
    global players_lite, boot_players, player_by_id, player_by_name, player_search_blobs, presets, categories, preset_meta
    sb_players, sb_presets, sb_cats = [], {}, {}
    try:
        sb_players = load_all_players() or []
    except Exception as e:
        print(f"Warning: Supabase load_all_players failed, falling back to local JSON: {e}")
    try:
        sb_presets, sb_cats = load_all_presets()
        sb_presets = sb_presets or {}
        sb_cats = sb_cats or {}
    except Exception as e:
        print(f"Warning: Supabase load_all_presets failed, falling back to local JSON: {e}")

    local_players = _load_local_json('players_lite.json', [])
    prev_extra = {
        pid: (
            p.get('image_url', ''),
            p.get('club_id'),
            p.get('role'),
            p.get('is_former'),
            p.get('last_season'),
            p.get('former_club'),
        )
        for pid, p in player_by_id.items()
    }
    if sb_players:
        by_id = {}
        for p in sb_players:
            if p.get('id') is not None:
                by_id[p['id']] = dict(p)
        for lp in local_players:
            lid = lp.get('id')
            if lid is None:
                continue
            if lid not in by_id:
                by_id[lid] = dict(lp)
            else:
                cur = by_id[lid]
                for k in (
                    'sub_pos', 'role', 'is_former', 'last_season', 'former_club',
                    'potential', 'report_date', 'total_assists', 'image_url', 'club_id'
                ):
                    if k not in cur and lp.get(k) is not None:
                        cur[k] = lp.get(k)
        merged_players = list(by_id.values())
    else:
        merged_players = [dict(p) for p in local_players]

    local_deltas = (get_local_sync_state() or {}).get('player_deltas') or {}
    club_norm_to_id = explorer_bundle.get('club_norm_to_id') or {}
    for p in merged_players:
        pid = p.get('id')
        if pid in local_deltas:
            d = local_deltas[pid]
            for dk in ('club', 'pos', 'sub_pos', 'role', 'age', 'height', 'val'):
                if d.get(dk) is not None:
                    p[dk] = d[dk]
        prev_img, prev_cid, prev_role, prev_former, prev_ls, prev_fclub = prev_extra.get(
            pid, ('', None, None, None, None, None)
        )
        if not p.get('role'):
            p['role'] = prev_role or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
        if 'is_former' not in p or p['is_former'] is None:
            p['is_former'] = bool(prev_former) if prev_former is not None else False
        if 'last_season' not in p:
            p['last_season'] = prev_ls
        if 'former_club' not in p or p['former_club'] is None:
            p['former_club'] = prev_fclub or ''
        if not p.get('image_url'):
            p['image_url'] = prev_img or (_player_img(pid) if explorer_bundle else '')
        if p.get('club_id') is None:
            c_lookup = p.get('former_club') if p.get('is_former') and p.get('former_club') else p.get('club')
            p['club_id'] = prev_cid if prev_cid is not None else club_norm_to_id.get(normalize_text(c_lookup))

    merged_players.sort(key=lambda p: (-float(p.get('rating') or 0), int(p.get('id') or 0)))
    new_by_id = {p['id']: p for p in merged_players if p.get('id') is not None}
    new_by_name = {}
    new_blobs = []
    ordered_for_lookup = [p for p in merged_players if not p.get('is_former')] + [
        p for p in merged_players if p.get('is_former')
    ]
    for p in ordered_for_lookup:
        norms = []
        for k in ('name', 'full_name', 'tm_name'):
            raw_v = p.get(k) or ''
            low = raw_v.lower()
            nrm = normalize_text(raw_v)
            if low and low not in new_by_name:
                new_by_name[low] = p
            if nrm and nrm not in new_by_name:
                new_by_name[nrm] = p
            if nrm:
                norms.append(nrm)
        new_blobs.append((p, ' | '.join(norms)))

    local_presets = _load_local_json('preset_lineups.json', {})
    local_cats = _load_local_json('preset_categories.json', {})
    if sb_presets:
        merged_presets = dict(sb_presets)
        for k, v in local_presets.items():
            if k not in merged_presets:
                merged_presets[k] = v
        merged_cats = {}
        for cat, names in local_cats.items():
            merged_cats[cat] = list(names)
        for cat, names in sb_cats.items():
            if cat not in merged_cats:
                merged_cats[cat] = list(names)
            else:
                seen = set(merged_cats[cat])
                for n in names:
                    if n not in seen:
                        merged_cats[cat].append(n)
                        seen.add(n)
        new_presets, new_cats = merged_presets, merged_cats
    else:
        new_presets, new_cats = local_presets, local_cats

    new_boot = _compute_boot_players(merged_players, new_by_id, new_by_name, new_blobs, new_presets)
    with _data_lock:
        players_lite = merged_players
        boot_players = new_boot
        player_by_id = new_by_id
        player_by_name = new_by_name
        player_search_blobs = new_blobs
        presets, categories = new_presets, new_cats
        if not preset_meta and explorer_bundle:
            preset_meta = _build_fallback_preset_meta(new_presets)

    src = "Supabase+local" if sb_players else "local JSON fallback"
    print(f"Loaded {len(players_lite)} players and {len(presets)} presets ({src}).")
    load_historical_data()


def load_startup_cache():
    global players_lite, boot_players, player_by_id, player_by_name, player_search_blobs
    global presets, categories, preset_meta, _blob_snapshots, _blob_historical, _snap_count
    if os.path.exists(STARTUP_CACHE_PATH):
        try:
            cache = _fast_load_joblib(STARTUP_CACHE_PATH)
            with _data_lock:
                players_lite = cache['players_lite']
                boot_players = cache['boot_players']
                player_by_id = cache['player_by_id']
                if 'blob_lookup' in cache:
                    player_by_name, player_search_blobs = _unpickle_blob(cache['blob_lookup'])
                else:
                    player_by_name = cache['player_by_name']
                    player_search_blobs = cache['player_search_blobs']
                presets = cache['presets']
                categories = cache['categories']
                preset_meta = cache['preset_meta']
                _snap_count = int(cache.get('snap_count') or 0)
                if 'blob_snapshots' in cache and 'blob_historical' in cache:
                    _blob_snapshots = cache['blob_snapshots']
                    _blob_historical = cache['blob_historical']
                else:
                    globals()['snap_dates'] = cache.get('snap_dates', {})
                    globals()['snap_rows'] = cache.get('snap_rows', {})
                    globals()['historical_presets'] = cache.get('historical_presets', {})
                    globals()['hist_presets_norm'] = cache.get('hist_presets_norm', {})
                    _snap_count = _snap_count or sum(len(v) for v in globals()['snap_rows'].values())
                    _hist_ready.set()
            print(f"Loaded startup cache ({len(players_lite)} players, {len(boot_players)} boot, {len(presets)} presets).")
            return True
        except Exception as e:
            print(f"Warning: failed loading startup_cache.joblib, falling back: {e}")
    reload_supabase_data()
    return False


# 2b. Load Precomputed Explorer & Standings Bundle
EXPLORER_PATH = os.path.join(DATA_DIR, 'explorer_bundle.joblib')
explorer_bundle = {}
_explorer_decoded = {}


def load_explorer_bundle():
    global explorer_bundle, _explorer_decoded
    _explorer_decoded = {}
    if os.path.exists(EXPLORER_PATH):
        try:
            explorer_bundle = _fast_load_joblib(EXPLORER_PATH) or {}
            print(f"Loaded explorer bundle ({len(explorer_bundle.get('leagues', []))} leagues, {len(explorer_bundle.get('countries', []))} countries).")
        except Exception as e:
            print(f"Warning: failed loading explorer_bundle.joblib: {e}")
            explorer_bundle = {}
    else:
        explorer_bundle = {}
    if not preset_meta and presets:
        preset_meta.update(_build_fallback_preset_meta(presets))


def _exp_blob(name, default=None):
    if name in _explorer_decoded:
        return _explorer_decoded[name]
    raw = explorer_bundle.get(name)
    if not raw:
        val = {} if default is None else default
    elif isinstance(raw, (bytes, bytearray)):
        if len(raw) >= 2 and raw[0] == 0x78:
            raw = zlib.decompress(raw)
        val = json.loads(raw.decode('utf-8'))
    else:
        val = raw
    _explorer_decoded[name] = val
    return val


def _bg_supabase_delta_sync():
    """Fetch only the 200 most recently updated players from Supabase without blocking boot."""
    try:
        remaining = 2.0 - (time.perf_counter() - _BOOT_T0)
        if remaining > 0:
            time.sleep(remaining)
        url, _ = _sb_cfg()
        if not url:
            return
        rows = _sb_req('players?select=id,club,pos,rating,age,val,goals_per_90,total_goals&order=updated_at.desc&limit=200') or []
        if not rows:
            return
        club_norm_to_id = explorer_bundle.get('club_norm_to_id') or {}
        with _data_lock:
            for r in rows:
                p = player_by_id.get(r.get('id'))
                if p is None:
                    continue
                if r.get('club') and r['club'] != p.get('club'):
                    p['club'] = r['club']
                    cid = club_norm_to_id.get(normalize_text(r['club']))
                    if cid is not None:
                        p['club_id'] = cid
                if r.get('pos'):
                    p['pos'] = r['pos']
                if r.get('rating') is not None and abs(float(r['rating']) - float(p.get('rating') or 0)) > 0.05:
                    p['rating'] = round(float(r['rating']), 1)
                if r.get('age') is not None and abs(float(r['age']) - float(p.get('age') or 0)) > 0.05:
                    p['age'] = round(float(r['age']), 1)
                if r.get('val') is not None and abs(float(r['val']) - float(p.get('val') or 0)) > 1.0:
                    p['val'] = float(r['val'])
                if r.get('goals_per_90') is not None and abs(float(r['goals_per_90']) - float(p.get('goals_per_90') or 0)) > 0.001:
                    p['goals_per_90'] = round(float(r['goals_per_90']), 3)
                if r.get('total_goals') is not None:
                    p['total_goals'] = int(r['total_goals'])
    except Exception:
        pass


def _run_sync_once():
    if not _sync_lock.acquire(blocking=False):
        return {'status': 'busy', 'message': 'Sync already running'}
    _sync_state['running'] = True
    try:
        res = sync_all()
        now_iso = datetime.now(timezone.utc).isoformat()
        if 'error' in res or not res:
            msg = res.get('error') or 'Set SUPABASE_URL and SUPABASE_KEY env vars to sync live finished matches.'
            _sync_state['last_error'] = msg
            return {'status': 'skipped', 'message': msg, 'synced': {}}
        _sync_state['last_sync'] = now_iso
        _sync_state['last_error'] = res.get('tmapi_error') or res.get('api_football_error') or res.get('football_data_error')
        _sync_state['matches_synced'] = int(res.get('tmapi_matches') or 0) + int(res.get('api_football') or 0) + int(res.get('football_data') or 0)
        _sync_state['players_updated'] = int(res.get('tmapi_players_updated') or 0) + int(res.get('players_updated') or 0)
        _sync_state['last_result'] = res
        reload_supabase_data()
        return {'status': 'success', 'synced': res}
    except Exception as e:
        _sync_state['last_error'] = str(e)
        return {'status': 'error', 'message': str(e)}
    finally:
        _sync_state['running'] = False
        _sync_lock.release()


def _auto_sync_loop():
    """Background daemon loop that periodically syncs recent matches and squads when configured."""
    time.sleep(15.0)
    interval = max(300, int(_sync_state.get('interval_sec') or 21600))
    while True:
        try:
            if _sync_state.get('enabled') and _sb_cfg()[0]:
                _run_sync_once()
        except Exception as e:
            _sync_state['last_error'] = str(e)
        time.sleep(interval)


def _bg_warmup():
    time.sleep(0.05)
    _ensure_hist()
    _ensure_models()
    _bg_supabase_delta_sync()


load_startup_cache()
load_explorer_bundle()

# Out-of-Position (OOP) Penalty Matrix
OOP_PENALTY_MATRIX = {
    'GK':  {'GK': 0,  'DEF': 40, 'MID': 45, 'ATT': 45},
    'DEF': {'GK': 45, 'DEF': 0,  'MID': 4,  'ATT': 18},
    'MID': {'GK': 45, 'DEF': 6,  'MID': 0,  'ATT': 4},
    'ATT': {'GK': 45, 'DEF': 18, 'MID': 5,  'ATT': 0},
}


def _normalize_date(report_date):
    if not report_date:
        return None, None, None
    s = str(report_date).strip()
    m = re.match(r'^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?', s)
    if not m:
        return None, None, None
    ym = f"{m.group(1)}-{m.group(2).zfill(2)}"
    day = m.group(3)
    if day:
        d = f"{ym}-{day.zfill(2)}"
        return d, d, ym
    return f"{ym}-01", f"{ym}-31", ym


def _apply_snapshot(p, report_date):
    norm_date, asof_date, _ = _normalize_date(report_date)
    if not norm_date or norm_date >= '2026-11-01':
        p.setdefault('report_date', '2026-11-01')
        p.setdefault('form_delta', 0.0)
        return p
    _ensure_hist()
    pid = p.get('id')
    if pid is None or pid not in snap_dates:
        p.setdefault('report_date', '2026-11-01')
        p.setdefault('form_delta', 0.0)
        return p
    dates = snap_dates[pid]
    idx = bisect_right(dates, asof_date) - 1
    if idx < 0:
        p.setdefault('report_date', '2026-11-01')
        p.setdefault('form_delta', 0.0)
        return p
    s_date, s_club, s_rating, s_fdelta, s_val, s_age, s_g90, s_tg = snap_rows[pid][idx]
    if s_rating is not None:
        p['rating'] = s_rating
    if s_val is not None:
        p['val'] = s_val
    if s_age is not None:
        p['age'] = s_age
    if s_club:
        p['club'] = s_club
        cid = (explorer_bundle.get('club_norm_to_id') or {}).get(normalize_text(s_club))
        if cid is not None:
            p['club_id'] = cid
    if s_g90 is not None:
        p['goals_per_90'] = s_g90
    if s_tg is not None:
        p['total_goals'] = s_tg
    p['report_date'] = s_date
    p['form_delta'] = 0.0 if s_fdelta is None else s_fdelta
    return p


def resolve_player(item, report_date=None):
    if item is None:
        return None
    slot_pos = None
    p_found = None
    if isinstance(item, dict):
        slot_pos = item.get('slot_pos')
        pid = item.get('id')
        if pid is not None and pid in player_by_id:
            p_found = player_by_id[pid]
        else:
            item_str = item.get('name', '')
    elif isinstance(item, int) and item in player_by_id:
        p_found = player_by_id[item]
        item_str = ''
    else:
        item_str = str(item)

    if p_found is None:
        item_clean = normalize_text(item_str)
        if item_clean:
            p_found = player_by_name.get(item_clean)
            if p_found is None:
                for p, blob in player_search_blobs:
                    if item_clean in blob:
                        p_found = p
                        break

    if p_found is not None:
        res = dict(p_found)
        if not res.get('image_url'):
            res['image_url'] = _player_img(res.get('id'))
        res.setdefault('club_id', None)
        if slot_pos is not None:
            res['slot_pos'] = slot_pos
        else:
            res['slot_pos'] = None
        return _apply_snapshot(res, report_date)
    return None

def calculate_player_effective_rating(p, slot_pos):
    native_group = p.get('pos') or ROLE_TO_GROUP.get(p.get('role'), 'MID')
    base_rating = float(p.get('rating', 75))
    if not slot_pos or slot_pos == 'SUB':
        return base_rating, 0
    slot_pos = str(slot_pos).strip().upper()
    if slot_pos in ('GK', 'DEF', 'MID', 'ATT'):
        penalty = OOP_PENALTY_MATRIX.get(native_group, {}).get(slot_pos, 0)
    else:
        native_role = (
            p.get('role')
            or SUB_POS_TO_ROLE.get(p.get('sub_pos', ''))
            or POS_FALLBACK.get(native_group, 'CM')
        ).upper()
        if native_role == slot_pos:
            penalty = 0
        elif (native_role, slot_pos) in GRANULAR_OOP_PENALTY:
            penalty = GRANULAR_OOP_PENALTY[(native_role, slot_pos)]
        else:
            slot_group = ROLE_TO_GROUP.get(slot_pos, slot_pos)
            penalty = OOP_PENALTY_MATRIX.get(native_group, {}).get(slot_group, 0)
    eff_rating = max(35.0, base_rating - penalty)
    return eff_rating, penalty


def cohesion_proxy(players):
    # ponytail: club-overlap proxy for shared chemistry, replace with historical lineup-pair minutes when DB populated
    clubs = [p.get('club', '') for p in players if p.get('club')]
    if not clubs:
        return 0.0
    n = len(players) or 1
    return sum((c / n) ** 2 for c in Counter(clubs).values())


def aggregate_team_advanced(starters_input, subs_input, team_name="Team", report_date=None):
    _ensure_models()
    pd = _pd_mod
    starters = [resolve_player(p, report_date=report_date) for p in starters_input]
    starters = [p for p in starters if p is not None]

    subs = [resolve_player(p, report_date=report_date) for p in subs_input]
    subs = [p for p in subs if p is not None]

    if not starters:
        raise ValueError(f"No valid starting players resolved for {team_name}")

    df_st = pd.DataFrame(starters)
    df_sb = pd.DataFrame(subs) if subs else pd.DataFrame()

    for col, default in (('height', 182.0), ('age', 26.0), ('rating', 75.0), ('val', 0.0), ('goals_per_90', 0.0)):
        if col not in df_st:
            df_st[col] = default
        else:
            df_st[col] = pd.to_numeric(df_st[col], errors='coerce').fillna(default)

    # Calculate Out-of-Position (OOP) Effective Ratings
    effective_ratings = []
    oop_penalties = []
    slot_groups = []
    has_outfield_in_gk = False

    for _, row in df_st.iterrows():
        p_obj = row.to_dict()
        slot_p = str(p_obj.get('slot_pos') or p_obj.get('role') or p_obj.get('pos', 'MID')).strip().upper()
        slot_grp = ROLE_TO_GROUP.get(slot_p, slot_p)
        eff_r, pen = calculate_player_effective_rating(p_obj, slot_p)
        effective_ratings.append(eff_r)
        oop_penalties.append(pen)
        slot_groups.append(slot_grp)
        if (slot_p == 'GK' or slot_grp == 'GK') and p_obj.get('pos') != 'GK' and p_obj.get('role') != 'GK':
            has_outfield_in_gk = True

    df_st['effective_rating'] = effective_ratings
    df_st['oop_penalty'] = oop_penalties
    df_st['slot_group'] = slot_groups

    stats = {}
    stats['starter_count'] = len(df_st)
    stats['starter_overall_mean'] = float(df_st['effective_rating'].mean())
    stats['starter_overall_max'] = float(df_st['effective_rating'].max())
    stats['starter_overall_min'] = float(df_st['effective_rating'].min())
    stats['starter_market_val_sum'] = float(df_st['val'].sum())
    stats['starter_height_mean'] = float(df_st['height'].mean())
    stats['starter_age_mean'] = float(df_st['age'].mean())
    stats['has_outfield_in_gk'] = has_outfield_in_gk

    prime_scores = (1.0 - 0.018 * (df_st['age'] - 27.0).abs()**1.25).clip(0.6, 1.0)
    stats['starter_prime_mean'] = float(prime_scores.mean())

    def line_metric(slot_label, col, fallback):
        sub = df_st[df_st['slot_group'] == slot_label]
        if len(sub) == 0:
            sub = df_st[df_st['pos'] == slot_label]
        return float(sub[col].mean()) if len(sub) > 0 else fallback

    stats['overall_mean_GK'] = line_metric('GK', 'effective_rating', stats['starter_overall_mean'])
    stats['overall_mean_DEF'] = line_metric('DEF', 'effective_rating', stats['starter_overall_mean'])
    stats['overall_mean_MID'] = line_metric('MID', 'effective_rating', stats['starter_overall_mean'])
    stats['overall_mean_ATT'] = line_metric('ATT', 'effective_rating', stats['starter_overall_mean'])

    stats['height_mean_DEF'] = line_metric('DEF', 'height', stats['starter_height_mean'])
    stats['height_mean_ATT'] = line_metric('ATT', 'height', stats['starter_height_mean'])

    if len(df_sb) > 0:
        sb_ratings = pd.to_numeric(df_sb.get('rating', 75.0), errors='coerce').fillna(75.0)
        stats['sub_count'] = len(df_sb)
        stats['sub_overall_mean'] = float(sb_ratings.mean())
        stats['sub_overall_max'] = float(sb_ratings.max())
    else:
        stats['sub_count'] = 0
        stats['sub_overall_mean'] = stats['starter_overall_mean'] - 5.0
        stats['sub_overall_max'] = stats['starter_overall_mean']

    stats['depth_gap'] = stats['starter_overall_mean'] - stats['sub_overall_mean']
    return stats, starters, subs


def compute_player_scorers(players, team_xg):
    scored_list = []

    weights = []
    for p in players:
        p_role = p.get('role') or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
        slot_p = str(p.get('slot_pos') or p_role or p.get('pos', 'MID')).strip().upper()
        if slot_p == 'GK':
            pos_mult = 0.001
        else:
            pos_mult = GRANULAR_SCORER_WEIGHTS.get(slot_p) or GRANULAR_SCORER_WEIGHTS.get(p_role) or GRANULAR_SCORER_WEIGHTS.get(p.get('pos', 'MID'), 0.4)

        raw_g90 = p.get('goals_per_90')
        g90 = 0.2 if raw_g90 is None or (isinstance(raw_g90, float) and math.isnan(raw_g90)) else float(raw_g90)
        eff_r, _ = calculate_player_effective_rating(p, slot_p)
        w = pos_mult * (0.3 * (eff_r / 80.0) + 0.7 * max(0.05, g90))
        weights.append(w)

    total_w = sum(weights) or 1.0
    for p, w in zip(players, weights):
        share = w / total_w
        indiv_xg = team_xg * share
        anytime_prob = 1.0 - math.exp(-indiv_xg)
        p_role = p.get('role') or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
        slot_p = p.get('slot_pos') or p_role or p.get('pos', 'MID')
        eff_r, pen = calculate_player_effective_rating(p, slot_p)
        raw_g90 = p.get('goals_per_90')
        g90_val = 0.0 if raw_g90 is None or (isinstance(raw_g90, float) and math.isnan(raw_g90)) else float(raw_g90)
        scored_list.append({
            'id': p.get('id'),
            'name': p['name'],
            'pos': p.get('pos', 'MID'),
            'role': p_role,
            'pos_role': p_role,
            'slot_pos': slot_p,
            'rating': p.get('rating', 75),
            'effective_rating': round(eff_r, 1),
            'oop_penalty': pen,
            'height': p.get('height') or 182,
            'age': p.get('age') or 26,
            'club': p.get('club', ''),
            'club_id': p.get('club_id'),
            'is_former': bool(p.get('is_former')),
            'last_season': p.get('last_season'),
            'former_club': p.get('former_club') or '',
            'image_url': p.get('image_url') or _player_img(p.get('id')),
            'career_goals': p.get('total_goals') or 0,
            'goals_per_90': g90_val,
            'anytime_prob': round(anytime_prob * 100, 1),
            'expected_goals': round(indiv_xg, 2)
        })
    return sorted(scored_list, key=lambda x: x['anytime_prob'], reverse=True)


KEYS = ('id', 'name', 'club', 'club_id', 'pos', 'sub_pos', 'slot_pos', 'rating', 'age', 'height', 'val', 'goals_per_90', 'total_goals', 'report_date', 'image_url', 'is_former', 'last_season', 'former_club')


def starter_rows(players):
    rows = []
    for p in players:
        eff, pen = calculate_player_effective_rating(p, p.get('slot_pos'))
        p_role = p.get('role') or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
        rows.append({
            **{k: p.get(k) for k in KEYS},
            'image_url': p.get('image_url') or '',
            'role': 'Starter',
            'pos_role': p_role,
            'is_former': bool(p.get('is_former')),
            'former_club': p.get('former_club') or '',
            'effective_rating': eff,
            'oop_penalty': pen,
        })
    return rows


def sub_rows(players):
    rows = []
    for p in players:
        p_role = p.get('role') or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
        rows.append({
            **{k: p.get(k) for k in KEYS},
            'image_url': p.get('image_url') or '',
            'role': 'Sub',
            'pos_role': p_role,
            'is_former': bool(p.get('is_former')),
            'former_club': p.get('former_club') or '',
            'slot_pos': 'SUB',
            'effective_rating': p.get('rating'),
            'oop_penalty': 0,
        })
    return rows


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/players')
def get_players():
    if request.args.get('mode') == 'boot':
        return jsonify(boot_players)
    return jsonify(players_lite)

@app.route('/api/presets')
def get_presets():
    return jsonify(presets)

@app.route('/api/categories')
def get_categories():
    return jsonify(categories)

@app.route('/api/preset-meta')
def get_preset_meta():
    return jsonify(preset_meta)


def _normalize_formation(f):
    if not f:
        return '4-3-3'
    s = str(f).strip()
    if s in VALID_FORMATIONS:
        return s
    nums = re.findall(r'\d+', s)
    cand = '-'.join(nums)
    if cand in VALID_FORMATIONS:
        return cand
    remap = {
        '4-3-2-1': '4-2-3-1', '4-1-2-1-2': '4-4-2', '4-3-1-2': '4-4-2',
        '4-2-2-2': '4-4-2', '4-4-1-1': '4-4-2', '4-5-1': '4-1-4-1',
        '3-4-2-1': '3-4-3', '3-4-1-2': '3-5-2', '3-1-4-2': '3-5-2',
        '5-2-3': '3-4-3', '5-2-2-1': '5-4-1', '5-3-1-1': '5-3-2',
    }
    if cand in remap:
        return remap[cand]
    if len(nums) >= 3 and sum(int(x) for x in nums) == 10:
        d = int(nums[0])
        if d >= 5:
            return '5-3-2' if int(nums[-1]) >= 2 else '5-4-1'
        if d == 3:
            return '3-4-3' if int(nums[-1]) >= 3 else '3-5-2'
        if len(nums) == 4:
            return '4-2-3-1' if int(nums[1]) <= 2 else '4-1-4-1'
        return '4-4-2' if int(nums[-1]) == 2 else '4-3-3'
    return '4-3-3'


def _formation_roles(f):
    norm_f = _normalize_formation(f)
    return list(FORMATION_ROLES.get(norm_f, FORMATION_ROLES['4-3-3']))


def _align_to_formation(resolved, formation):
    roles = _formation_roles(formation)
    pool = [dict(p) for p in resolved if p is not None]
    if not pool:
        return [None] * 11
    slots = [None] * 11
    used = set()
    # Pass 1: exact granular role match
    for idx, slot_role in enumerate(roles):
        for j, p in enumerate(pool):
            p_role = p.get('role') or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
            if j not in used and p_role == slot_role:
                p_copy = dict(p)
                p_copy['slot_pos'] = slot_role
                slots[idx] = p_copy
                used.add(j)
                break
    # Pass 2: same 4-tier group match
    for idx, slot_role in enumerate(roles):
        if slots[idx] is not None:
            continue
        target_group = ROLE_TO_GROUP.get(slot_role, slot_role)
        for j, p in enumerate(pool):
            p_group = p.get('pos') or ROLE_TO_GROUP.get(p.get('role'), 'MID')
            if j not in used and p_group == target_group:
                p_copy = dict(p)
                p_copy['slot_pos'] = slot_role
                slots[idx] = p_copy
                used.add(j)
                break
    # Pass 3: remaining players
    rem = [p for j, p in enumerate(pool) if j not in used]
    for idx, slot_role in enumerate(roles):
        if slots[idx] is None and rem:
            p_copy = dict(rem.pop(0))
            p_copy['slot_pos'] = slot_role
            slots[idx] = p_copy
    return slots


def _get_hist_entry(team_name, ym):
    if not team_name or not ym:
        return None
    _ensure_hist()
    th = historical_presets.get(team_name)
    if not th:
        th = historical_presets.get(f"{team_name} (National Team)")
    if not th:
        k = hist_presets_norm.get(normalize_text(team_name))
        if k:
            th = historical_presets.get(k)
    if not isinstance(th, dict):
        return None
    keys = [k for k in th if k <= ym]
    return th[max(keys)] if keys else None


def _get_current_preset(team_name):
    if not team_name:
        return None
    return presets.get(team_name) or presets.get(f"{team_name} (National Team)")


def _find_team_players_at_date(team_name, date_str, formation):
    if not team_name:
        return [], []
    _ensure_hist()
    _, asof_date, _ = _normalize_date(date_str)
    is_nat = team_name.endswith(' (National Team)')
    target = normalize_text(team_name.replace(' (National Team)', ''))
    if not target:
        return [], []

    snap_matches, curr_matches = [], []
    for p in players_lite:
        pid = p.get('id')
        has_snap, snap_club = False, ''
        if asof_date and pid in snap_dates:
            idx = bisect_right(snap_dates[pid], asof_date) - 1
            if idx >= 0:
                has_snap = True
                snap_club = snap_rows[pid][idx][1]
        if is_nat:
            if normalize_text(p.get('nat')) == target:
                (snap_matches if has_snap else curr_matches).append(_apply_snapshot(dict(p), date_str))
        else:
            if has_snap and snap_club:
                if normalize_text(snap_club) == target:
                    snap_matches.append(_apply_snapshot(dict(p), date_str))
            elif normalize_text(p.get('club')) == target:
                curr_matches.append(_apply_snapshot(dict(p), date_str))

    candidates = snap_matches if len(snap_matches) >= 11 else (snap_matches + curr_matches)
    if not candidates and not is_nat:
        for p in players_lite:
            if normalize_text(p.get('nat')) == target:
                candidates.append(_apply_snapshot(dict(p), date_str))

    seen, uniq = set(), []
    for p in sorted(candidates, key=lambda x: (-float(x.get('rating') or 0), int(x.get('id') or 0))):
        pid = p.get('id')
        if pid not in seen:
            seen.add(pid)
            uniq.append(p)
    if not uniq:
        return [], []

    roles = _formation_roles(formation)
    slots, used_ids = [None] * 11, set()
    # Pass 1: exact granular role
    for idx, slot_role in enumerate(roles):
        for p in uniq:
            p_role = p.get('role') or SUB_POS_TO_ROLE.get(p.get('sub_pos', '')) or POS_FALLBACK.get(p.get('pos', 'MID'), 'CM')
            if p['id'] not in used_ids and p_role == slot_role:
                p_copy = dict(p)
                p_copy['slot_pos'] = slot_role
                slots[idx] = p_copy
                used_ids.add(p['id'])
                break
    # Pass 2: 4-tier group
    for idx, slot_role in enumerate(roles):
        if slots[idx] is not None:
            continue
        target_group = ROLE_TO_GROUP.get(slot_role, slot_role)
        for p in uniq:
            p_group = p.get('pos') or ROLE_TO_GROUP.get(p.get('role'), 'MID')
            if p['id'] not in used_ids and p_group == target_group:
                p_copy = dict(p)
                p_copy['slot_pos'] = slot_role
                slots[idx] = p_copy
                used_ids.add(p['id'])
                break
    # Pass 3: remaining
    for idx, slot_role in enumerate(roles):
        if slots[idx] is None:
            for p in uniq:
                if p['id'] not in used_ids:
                    p_copy = dict(p)
                    p_copy['slot_pos'] = slot_role
                    slots[idx] = p_copy
                    used_ids.add(p['id'])
                    break
    subs = [p for p in uniq if p['id'] not in used_ids][:7]
    return slots, subs


def _json_safe_player(p):
    if p is None:
        return None
    out = {}
    for k, v in p.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            out[k] = None
        elif type(v).__module__ == 'numpy':
            val = v.item()
            out[k] = None if isinstance(val, float) and (math.isnan(val) or math.isinf(val)) else val
        else:
            out[k] = v
    return out


def _resolve_snapshot_team(team_name, date_str, auto_lineup, formation, passed_starters, passed_subs):
    norm_date, _, ym = _normalize_date(date_str)
    curr_preset = _get_current_preset(team_name)
    base_form = _normalize_formation(formation or (curr_preset or {}).get('formation') or '4-3-3')

    if not auto_lineup:
        raw_st = passed_starters if passed_starters else (curr_preset or {}).get('starters', [])
        raw_sb = passed_subs if passed_subs is not None else (curr_preset or {}).get('subs', [])
        slots = [_json_safe_player(resolve_player(x, report_date=date_str)) for x in list(raw_st)[:11]]
        slots.extend([None] * (11 - len(slots)))
        subs = [_json_safe_player(p) for p in (resolve_player(x, report_date=date_str) for x in raw_sb) if p is not None]
        return base_form, slots, subs

    if not ym or norm_date >= '2026-11-01':
        if curr_preset:
            use_form = _normalize_formation(curr_preset.get('formation') or base_form)
            slots = [_json_safe_player(resolve_player(x, report_date=date_str)) for x in curr_preset.get('starters', [])[:11]]
            slots = _align_to_formation(slots, use_form)
            subs = [_json_safe_player(p) for p in (resolve_player(x, report_date=date_str) for x in curr_preset.get('subs', [])) if p is not None]
            return use_form, slots, subs
        if passed_starters:
            slots = [_json_safe_player(resolve_player(x, report_date=date_str)) for x in list(passed_starters)[:11]]
            slots.extend([None] * (11 - len(slots)))
            subs = [_json_safe_player(p) for p in (resolve_player(x, report_date=date_str) for x in (passed_subs or [])) if p is not None]
            return base_form, slots, subs

    hist = _get_hist_entry(team_name, ym)
    if hist and hist.get('starters'):
        use_form = _normalize_formation(hist.get('formation') or base_form)
        resolved_st = [resolve_player(x, report_date=date_str) for x in hist.get('starters', [])[:11]]
        slots = [_json_safe_player(p) for p in _align_to_formation(resolved_st, use_form)]
        subs = [_json_safe_player(p) for p in (resolve_player(x, report_date=date_str) for x in hist.get('subs', [])) if p is not None]
        if sum(1 for s in slots if s is not None) >= 7:
            return use_form, slots, subs

    fb_slots, fb_subs = _find_team_players_at_date(team_name, date_str, base_form)
    if sum(1 for s in fb_slots if s is not None) >= 7:
        return base_form, [_json_safe_player(p) for p in fb_slots], [_json_safe_player(p) for p in fb_subs]

    raw_st = passed_starters if passed_starters else (curr_preset or {}).get('starters', [])
    raw_sb = passed_subs if passed_subs else (curr_preset or {}).get('subs', [])
    use_form = _normalize_formation((curr_preset or {}).get('formation') or base_form)
    slots = [_json_safe_player(resolve_player(x, report_date=date_str)) for x in list(raw_st)[:11]]
    slots.extend([None] * (11 - len(slots)))
    subs = [_json_safe_player(p) for p in (resolve_player(x, report_date=date_str) for x in raw_sb) if p is not None]
    return use_form, slots, subs


@app.route('/api/snapshot', methods=['GET', 'POST'])
def api_snapshot():
    data = (request.get_json(silent=True) or {}) if request.method == 'POST' else request.args.to_dict()
    date_str = data.get('date') or data.get('report_date') or '2026-11'
    norm_date, _, _ = _normalize_date(date_str)
    eff_date = norm_date or '2026-11-01'
    raw_auto = data.get('auto_lineup', True)
    auto_lineup = raw_auto.lower() not in ('0', 'false', 'no') if isinstance(raw_auto, str) else bool(raw_auto)

    home_name = data.get('home_name', '')
    away_name = data.get('away_name', '')
    hf, hs, hsb = _resolve_snapshot_team(
        home_name, date_str, auto_lineup,
        data.get('home_formation'), data.get('home_starters'), data.get('home_subs')
    )
    af, as_, asb = _resolve_snapshot_team(
        away_name, date_str, auto_lineup,
        data.get('away_formation'), data.get('away_starters'), data.get('away_subs')
    )
    return jsonify({
        'status': 'success',
        'report_date': eff_date,
        'home_formation': hf,
        'away_formation': af,
        'home_slots': hs,
        'home_subs': hsb,
        'away_slots': as_,
        'away_subs': asb,
    })


def _get_team_crest(team_name):
    if not team_name:
        return ''
    nrm = normalize_text(team_name)
    for key in (
        team_name,
        f"{team_name} (National Team)",
        nrm,
        normalize_text(f"{team_name} (National Team)"),
    ):
        meta = preset_meta.get(key)
        if meta and meta.get('crest_url'):
            return meta['crest_url']
    cid = (explorer_bundle.get('club_norm_to_id') or {}).get(nrm)
    if cid:
        return f'https://tmssl.akamaized.net/images/wappen/head/{cid}.png'
    cobj = _find_country_obj(team_name)
    if cobj and cobj.get('team_image_url'):
        return cobj['team_image_url']
    return ''


@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        _ensure_models()
        pd, np = _pd_mod, _np_mod
        data = request.get_json() or {}
        team_a_name = data.get('home_name', 'Squad 1')
        team_b_name = data.get('away_name', 'Squad 2')
        report_date = data.get('report_date')
        norm_date, _, _ = _normalize_date(report_date)
        eff_report_date = norm_date or '2026-11-01'
        if norm_date and norm_date < '2026-11-01':
            _ensure_hist()

        starters_a = data.get('home_starters', [])
        subs_a = data.get('home_subs', [])
        starters_b = data.get('away_starters', [])
        subs_b = data.get('away_subs', [])

        form_pts_a = float(data.get('home_form_pts', 1.8))
        form_pts_b = float(data.get('away_form_pts', 1.8))
        form_gd_a = float(data.get('home_form_gd', 0.5))
        form_gd_b = float(data.get('away_form_gd', 0.5))

        stats_a, st_a, sb_a = aggregate_team_advanced(starters_a, subs_a, team_a_name, report_date=report_date)
        stats_b, st_b, sb_b = aggregate_team_advanced(starters_b, subs_b, team_b_name, report_date=report_date)
        
        features_ab = {
            'diff_overall_mean': stats_a['starter_overall_mean'] - stats_b['starter_overall_mean'],
            'diff_overall_max': stats_a['starter_overall_max'] - stats_b['starter_overall_max'],
            'diff_overall_min': stats_a['starter_overall_min'] - stats_b['starter_overall_min'],
            'diff_attack_vs_defense': stats_a['overall_mean_ATT'] - stats_b['overall_mean_DEF'],
            'diff_defense_vs_attack': stats_a['overall_mean_DEF'] - stats_b['overall_mean_ATT'],
            'diff_midfield': stats_a['overall_mean_MID'] - stats_b['overall_mean_MID'],
            'diff_sub_mean': stats_a['sub_overall_mean'] - stats_b['sub_overall_mean'],
            'diff_depth_gap': stats_a['depth_gap'] - stats_b['depth_gap'],
            'diff_market_val_log': np.log1p(stats_a['starter_market_val_sum']) - np.log1p(stats_b['starter_market_val_sum']),
            'diff_form_pts_5': form_pts_a - form_pts_b,
            'diff_form_gd_5': form_gd_a - form_gd_b,
            'diff_aerial_att_vs_def': stats_a['height_mean_ATT'] - stats_b['height_mean_DEF'],
            'diff_aerial_def_vs_att': stats_a['height_mean_DEF'] - stats_b['height_mean_ATT'],
            'diff_prime_score': stats_a['starter_prime_mean'] - stats_b['starter_prime_mean'],
            'diff_cohesion': cohesion_proxy(st_a) - cohesion_proxy(st_b),
            'league_tier_factor': float(data.get('league_tier_factor', 0.95))
        }
        
        X_ab = pd.DataFrame([features_ab])[advanced_features]
        
        features_ba = {
            'diff_overall_mean': -features_ab['diff_overall_mean'],
            'diff_overall_max': -features_ab['diff_overall_max'],
            'diff_overall_min': -features_ab['diff_overall_min'],
            'diff_attack_vs_defense': -features_ab['diff_defense_vs_attack'],
            'diff_defense_vs_attack': -features_ab['diff_attack_vs_defense'],
            'diff_midfield': -features_ab['diff_midfield'],
            'diff_sub_mean': -features_ab['diff_sub_mean'],
            'diff_depth_gap': -features_ab['diff_depth_gap'],
            'diff_market_val_log': -features_ab['diff_market_val_log'],
            'diff_form_pts_5': -features_ab['diff_form_pts_5'],
            'diff_form_gd_5': -features_ab['diff_form_gd_5'],
            'diff_aerial_att_vs_def': -features_ab['diff_aerial_def_vs_att'],
            'diff_aerial_def_vs_att': -features_ab['diff_aerial_att_vs_def'],
            'diff_prime_score': -features_ab['diff_prime_score'],
            'diff_cohesion': -features_ab['diff_cohesion'],
            'league_tier_factor': features_ab['league_tier_factor']
        }
        X_ba = pd.DataFrame([features_ba])[advanced_features]
        
        # 1. 3-Class Probabilities
        prob_ab = model_advanced_3class.predict_proba(X_ab)[0]
        prob_ba = model_advanced_3class.predict_proba(X_ba)[0]
        
        p_a_win = float((prob_ab[2] + prob_ba[0]) / 2.0)
        p_b_win = float((prob_ab[0] + prob_ba[2]) / 2.0)
        p_draw = float((prob_ab[1] + prob_ba[1]) / 2.0)
        
        # 2. Expected Goals (xG) with Absolute Offensive Firepower Scaling
        xg_base_a = max(0.4, float(model_advanced_xg.predict(X_ab)[0]))
        xg_base_b = max(0.4, float(model_advanced_xg.predict(X_ba)[0]))
        
        # Absolute offensive scaling & defensive resistance
        att_g90_a = float(pd.to_numeric(pd.DataFrame(st_a).get('goals_per_90', pd.Series([0.0])), errors='coerce').fillna(0.0).nlargest(3).sum()) if st_a else 0.8
        att_g90_b = float(pd.to_numeric(pd.DataFrame(st_b).get('goals_per_90', pd.Series([0.0])), errors='coerce').fillna(0.0).nlargest(3).sum()) if st_b else 0.8
        
        att_mult_a = ((stats_a['overall_mean_ATT'] / 78.0) ** 1.25) * (1.0 + (att_g90_a - 0.7) / 3.2)
        att_mult_b = ((stats_b['overall_mean_ATT'] / 78.0) ** 1.25) * (1.0 + (att_g90_b - 0.7) / 3.2)
        
        def_supp_a = (stats_a['overall_mean_DEF'] / 78.0) ** 0.5
        def_supp_b = (stats_b['overall_mean_DEF'] / 78.0) ** 0.5
        
        form_boost_a = 0.88 + 0.12 * (form_pts_a / 2.0)
        form_boost_b = 0.88 + 0.12 * (form_pts_b / 2.0)
        
        xg_a = max(0.3, xg_base_a * (att_mult_a / def_supp_b) * form_boost_a)
        xg_b = max(0.3, xg_base_b * (att_mult_b / def_supp_a) * form_boost_b)
        
        # If Squad A has an outfield player in goal (e.g. Messi as GK), Opponent xG doubles!
        if stats_a['has_outfield_in_gk']:
            xg_b = xg_b * 2.2 + 1.2
            p_b_win = min(0.92, p_b_win * 1.8 + 0.35)
            p_a_win = max(0.04, p_a_win * 0.25)
            p_draw = max(0.04, 1.0 - p_a_win - p_b_win)
            
        if stats_b['has_outfield_in_gk']:
            xg_a = xg_a * 2.2 + 1.2
            p_a_win = min(0.92, p_a_win * 1.8 + 0.35)
            p_b_win = max(0.04, p_b_win * 0.25)
            p_draw = max(0.04, 1.0 - p_a_win - p_b_win)
            
        # Generate Bivariate Poisson Exact Score Matrix
        score_matrix = []
        for ga in range(6):
            for gb in range(6):
                p_ga = (math.pow(xg_a, ga) * math.exp(-xg_a)) / math.factorial(ga)
                p_gb = (math.pow(xg_b, gb) * math.exp(-xg_b)) / math.factorial(gb)
                prob = p_ga * p_gb
                score_matrix.append({
                    'score': f"{ga} - {gb}",
                    'team_a_goals': ga,
                    'team_b_goals': gb,
                    'prob': round(prob * 100, 1)
                })
                
        score_matrix.sort(key=lambda x: x['prob'], reverse=True)
        top_score = score_matrix[0]
        score_grid = [[0.0] * 6 for _ in range(6)]
        for sc in score_matrix: score_grid[sc['team_a_goals']][sc['team_b_goals']] = sc['prob']
        

        scorers_a = compute_player_scorers(st_a, xg_a)
        scorers_b = compute_player_scorers(st_b, xg_b)
        over25 = round(sum(s['prob'] for s in score_matrix if s['team_a_goals'] + s['team_b_goals'] > 2), 1)

        metrics = [(l, x, y) for l, x, y in [
            ('Starting XI quality (effective)', stats_a['starter_overall_mean'], stats_b['starter_overall_mean']),
            ('Goalkeeper', stats_a['overall_mean_GK'], stats_b['overall_mean_GK']),
            ('Attack line', stats_a['overall_mean_ATT'], stats_b['overall_mean_ATT']),
            ('Midfield', stats_a['overall_mean_MID'], stats_b['overall_mean_MID']),
            ('Defence line', stats_a['overall_mean_DEF'], stats_b['overall_mean_DEF']),
            ('Aerial: attack height vs opp. defence (cm)', stats_a['height_mean_ATT'], stats_b['height_mean_DEF']),
            ('Age-prime factor', stats_a['starter_prime_mean'] * 100, stats_b['starter_prime_mean'] * 100),
            ('Bench depth', stats_a['sub_overall_mean'], stats_b['sub_overall_mean'])]]
        tactical = [{'label': l, 'home': round(x, 1), 'away': round(y, 1)} for l, x, y in metrics]

        # Knockout: drawn after 90' -> shootout. Shootouts ~coin flip; only GK gap tilts it (capped 42-58%).
        # ponytail: heuristic, not trained on shootout data. Replace with historical shootout model if data exists.
        ko = None
        if data.get('knockout'):
            pen_a = min(0.58, max(0.42, 0.5 + 0.004 * (stats_a['overall_mean_GK'] - stats_b['overall_mean_GK'])))
            adv_a = p_a_win + p_draw * pen_a
            ko = {'shootout_prob': round(p_draw * 100, 1), 'shootout_home': round(pen_a * 100, 1),
                  'advance_home': round(adv_a * 100, 1), 'advance_away': round((1 - adv_a) * 100, 1)}

        pa, pdr, pb = round(p_a_win * 100, 1), round(p_draw * 100, 1), round(p_b_win * 100, 1)
        margin = abs(p_a_win - p_b_win)
        confidence = 'High' if margin >= 0.25 else ('Medium' if margin >= 0.10 else 'Low')

        # 1. Argmax Formulation
        if pdr >= pa and pdr >= pb:
            verdict_argmax = 'draw'
            headline_argmax = f"Even contest: draw most likely ({pdr}%)"
        elif pa > pb:
            verdict_argmax = 'home'
            headline_argmax = f"{team_a_name} favoured to win ({pa}%)"
        else:
            verdict_argmax = 'away'
            headline_argmax = f"{team_b_name} favoured to win ({pb}%)"

        # 2. Tuned Threshold Formulation (tau_draw = 0.27)
        if pdr >= 27.0:
            verdict_tuned = 'draw'
            headline_tuned = f"Balanced model: draw identified ({pdr}% >= 27% threshold)"
        elif pa > pb:
            verdict_tuned = 'home'
            headline_tuned = f"{team_a_name} favoured to win ({pa}%)"
        else:
            verdict_tuned = 'away'
            headline_tuned = f"{team_b_name} favoured to win ({pb}%)"

        active_mode = data.get('threshold_mode', 'tuned')
        active_verdict = verdict_tuned if active_mode == 'tuned' else verdict_argmax
        active_headline = headline_tuned if active_mode == 'tuned' else headline_argmax

        if ko:
            fav = team_a_name if ko['advance_home'] >= 50 else team_b_name
            headline = f"{fav} favoured to advance ({max(ko['advance_home'], ko['advance_away'])}%)"
        else:
            headline = active_headline

        big = max(tactical, key=lambda m: abs(m['home'] - m['away']) / max(m['home'], m['away'], 1))
        points = [
            f"Win probability: {team_a_name} {pa}% | Draw {pdr}% | {team_b_name} {pb}%.",
            f"Most likely score {top_score['score']} (xG {xg_a:.2f} - {xg_b:.2f}); over 2.5 goals {over25}%.",
            f"Biggest edge: {big['label']} favours {team_a_name if big['home'] > big['away'] else team_b_name} ({big['home']} vs {big['away']}).",
            f"Top scoring threats: {scorers_a[0]['name']} ({team_a_name}, {scorers_a[0]['anytime_prob']}%), {scorers_b[0]['name']} ({team_b_name}, {scorers_b[0]['anytime_prob']}%)."]
        if ko:
            points.append(f"If level after 90 min ({ko['shootout_prob']}%), shootout is near coin-flip: {team_a_name} {ko['shootout_home']}%. Advance: {team_a_name} {ko['advance_home']}%, {team_b_name} {ko['advance_away']}%.")
        oop = [p for p in starter_rows(st_a) + starter_rows(st_b) if p['oop_penalty']]
        if oop:
            points.append(f"Caution: {len(oop)} starter(s) out of position (rating reduced).")
        if stats_a['has_outfield_in_gk'] or stats_b['has_outfield_in_gk']:
            points.append("Caution: an outfield player is in goal; result is dominated by this.")

        try:
            log_prediction(team_a_name, team_b_name, pa, pdr, pb, round(xg_a, 2), round(xg_b, 2), top_score['score'], active_verdict)
        except Exception:
            pass

        return jsonify({
            'status': 'success', 'home_name': team_a_name, 'away_name': team_b_name,
            'home_crest': _get_team_crest(team_a_name),
            'away_crest': _get_team_crest(team_b_name),
            'winner_key': active_verdict,
            'verdict_argmax': verdict_argmax,
            'verdict_tuned': verdict_tuned,
            'headline_argmax': headline_argmax,
            'headline_tuned': headline_tuned,
            'threshold_tau': 0.27,
            'summary': {'headline': headline, 'confidence': confidence, 'points': points},
            'probabilities': {'home': pa, 'draw': pdr, 'away': pb},
            'knockout': ko,
            'score_prediction': {'projected_home_xg': round(xg_a, 2), 'projected_away_xg': round(xg_b, 2),
                                 'most_likely_score': top_score['score'], 'top_scores': score_matrix[:6], 'score_grid': score_grid, 'over_2_5_prob': over25},
            'goalscorers': {'home': scorers_a[:6], 'away': scorers_b[:6]},
            'tactical_metrics': tactical,
            'lineups': {'home': starter_rows(st_a) + sub_rows(sb_a), 'away': starter_rows(st_b) + sub_rows(sb_b)},
            'home_stats': stats_a, 'away_stats': stats_b,
            'inputs': {'home_form_pts': form_pts_a, 'away_form_pts': form_pts_b, 'knockout': bool(data.get('knockout')), 'threshold_mode': active_mode, 'report_date': eff_report_date}
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/export', methods=['POST'])
def export_xlsx():
    import io
    from datetime import datetime
    from flask import send_file
    from openpyxl import Workbook
    from openpyxl.formatting.rule import DataBarRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter as L

    NAVY, AMBER, GREY, PAPER, INK, MUTE = '1B2A4A', 'F4B400', 'A9B6B1', 'EEF2F0', '13201C', '5A6A65'
    nm = lambda t: str(t).replace(' (National Team)', '')
    d = request.get_json() or {}
    h, a, sm, pr, sp = nm(d['home_name']), nm(d['away_name']), d['summary'], d['probabilities'], d['score_prediction']
    ko = d.get('knockout')
    F = lambda **k: Font(name='Arial', **k)
    fill = lambda c: PatternFill('solid', start_color=c, end_color=c)
    line = lambda c='C5D0CC', w='thin': Border(bottom=Side(style=w, color=c))

    wb = Workbook()
    ws = wb.active
    ws.title = 'Summary'
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = AMBER
    for col, w in zip('ABCDEFGH', (2, 40, 14, 14, 14, 14, 14, 14)): ws.column_dimensions[col].width = w
    r = 1

    def put(row, col, v, font=None, fmt=None, al=None, bg=None, merge_to=None):
        c = ws.cell(row, col, v)
        c.font = font or F(size=11, color=INK)
        if fmt: c.number_format = fmt
        c.alignment = al or Alignment(vertical='center')
        if bg: c.fill = fill(bg)
        if merge_to: ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=merge_to)
        return c

    def section(title):
        nonlocal r
        r += 1
        for col in range(2, 9): ws.cell(r, col).border = line(NAVY, 'medium')
        put(r, 2, title, F(size=13, bold=True, color=NAVY)); ws.row_dimensions[r].height = 24
        r += 1

    def bar(row, value, color, c0=4):
        put(row, c0, value, F(size=1, color='FFFFFF'), ';;;', merge_to=8)
        ws.conditional_formatting.add(f'{L(c0)}{row}', DataBarRule(start_type='num', start_value=0, end_type='num', end_value=1, color=color, showValue=False))

    # banner
    rep_dt = (d.get('inputs') or {}).get('report_date') or '2026-11-01'
    for row in (1, 2, 3):
        for col in range(1, 9): ws.cell(row, col).fill = fill(NAVY)
    put(1, 2, 'Match prediction report', F(size=11, color='C9D3E0'), bg=NAVY)
    put(2, 2, f'{h}  v  {a}', F(size=24, bold=True, color='FFFFFF'), bg=NAVY, merge_to=8)
    put(3, 2, f"Prepared {datetime.now().strftime('%d %B %Y')}  |  As-of Date: {rep_dt}  |  Format: {'Knockout (penalties if level)' if ko else 'Single match, 90 minutes'}", F(size=10, color='C9D3E0'), bg=NAVY, merge_to=8)
    ws.row_dimensions[2].height = 40; ws.row_dimensions[1].height = 20; ws.row_dimensions[3].height = 22

    # headline
    r = 5
    put(r, 2, nm(sm['headline']), F(size=20, bold=True, color=INK), merge_to=8, al=Alignment(wrap_text=True, vertical='center')); ws.row_dimensions[r].height = 34
    r += 1
    conf_note = {'High': 'One side is clearly stronger.', 'Medium': 'One side has an edge, but upsets are common.', 'Low': 'The sides are close. Read this as a lean, not a call.'}
    put(r, 2, f"{sm['confidence']} confidence", F(size=11, bold=True, color=INK), bg=AMBER, al=Alignment(horizontal='center', vertical='center'))
    put(r, 3, conf_note.get(sm['confidence'], ''), F(size=11, color=MUTE), merge_to=8, al=Alignment(indent=1, vertical='center')); ws.row_dimensions[r].height = 22

    # probabilities
    section('Chance of each result after 90 minutes')
    for label, v, col in ((f'{h} win', pr['home'], AMBER), ('Draw', pr['draw'], GREY), (f'{a} win', pr['away'], NAVY)):
        put(r, 2, label, F(size=11, bold=True)); put(r, 3, v / 100, F(size=12, bold=True), '0.0%', Alignment(horizontal='right', vertical='center'))
        bar(r, v / 100, col); ws.row_dimensions[r].height = 24; r += 1
    if ko:
        r += 1
        put(r, 2, 'Chance to go through (includes penalties)', F(size=11, bold=True, color=MUTE), merge_to=8); r += 1
        for label, v, col in ((h, ko['advance_home'], AMBER), (a, ko['advance_away'], NAVY)):
            put(r, 2, label, F(size=11, bold=True)); put(r, 3, v / 100, F(size=12, bold=True), '0.0%', Alignment(horizontal='right', vertical='center'))
            bar(r, v / 100, col); ws.row_dimensions[r].height = 24; r += 1
        put(r, 2, f"Chance the match goes to a shootout: {ko['shootout_prob']}%. Shootout odds are an estimate, not trained on shootout data.", F(size=9, italic=True, color=MUTE), merge_to=8); r += 1

    # predicted score
    section('Most likely score')
    ga, gb = sp['most_likely_score'].split(' - ')
    put(r, 2, f'{h}   {ga}  -  {gb}   {a}', F(size=26, bold=True, color=NAVY), merge_to=8, al=Alignment(horizontal='center', vertical='center')); ws.row_dimensions[r].height = 46; r += 1
    put(r, 2, f"Expected goals: {h} {sp['projected_home_xg']}, {a} {sp['projected_away_xg']}   |   More than 2.5 total goals: {sp['over_2_5_prob']}%", F(size=10, color=MUTE), merge_to=8, al=Alignment(horizontal='center')); r += 1

    # key points
    section('Key points')
    for p in sm['points']:
        t = nm(p)
        put(r, 2, f'-  {t}', F(size=11), merge_to=8, al=Alignment(wrap_text=True, vertical='top', indent=1))
        ws.row_dimensions[r].height = 18 * (-(-len(t) // 100)) + 4; r += 1

    # scorers
    section('Most likely goalscorers (chance to score at any time)')
    for i, t in enumerate(('Player', 'Team', 'Chance')):
        put(r, 2 + i, t, F(size=10, bold=True, color='FFFFFF'), bg=NAVY, al=Alignment(horizontal='left' if i < 2 else 'right', vertical='center'))
    for col in range(5, 9): ws.cell(r, col).fill = fill(NAVY)
    r += 1
    for side, nme, col in (('home', h, AMBER), ('away', a, NAVY)):
        for p in d['goalscorers'][side][:4]:
            put(r, 2, p['name']); put(r, 3, nme, F(size=10, color=MUTE)); put(r, 4, p['anytime_prob'] / 100, F(size=11, bold=True), '0.0%', Alignment(horizontal='right'))
            put(r, 5, p['anytime_prob'] / 100, F(size=1, color='FFFFFF'), ';;;', merge_to=8)
            ws.conditional_formatting.add(f'E{r}', DataBarRule(start_type='num', start_value=0, end_type='num', end_value=1, color=col, showValue=False))
            for c in range(2, 9): ws.cell(r, c).border = line(); 
            r += 1

    # comparison
    section('Team comparison')
    for i, t in enumerate(('Area', h, a, 'Advantage')):
        put(r, 2 + i, t, F(size=10, bold=True, color='FFFFFF'), bg=NAVY, al=Alignment(horizontal='left' if i in (0, 3) else 'right', vertical='center', indent=1 if i == 3 else 0))
    for col in range(6, 9): ws.cell(r, col).fill = fill(NAVY)
    r += 1
    for m in d['tactical_metrics']:
        win = h if m['home'] > m['away'] else a if m['away'] > m['home'] else 'Even'
        put(r, 2, nm(m['label'])); put(r, 3, m['home'], F(size=11, bold=m['home'] > m['away']), '0.0', Alignment(horizontal='right'))
        put(r, 4, m['away'], F(size=11, bold=m['away'] > m['home']), '0.0', Alignment(horizontal='right'))
        put(r, 5, win, F(size=11, bold=True, color=NAVY), al=Alignment(indent=1))
        for c in range(2, 9): ws.cell(r, c).border = line()
        r += 1

    # notes
    section('How to read this')
    acc_note = 'Figures are model probabilities, not certainties.'
    rpt_path = os.path.join(DATA_DIR, 'academic_report_data.json')
    if os.path.exists(rpt_path):
        try:
            with open(rpt_path, 'r', encoding='utf-8') as f:
                rpt = json.load(f)
            acc = rpt.get('model_3class_metrics', {}).get('accuracy')
            tp = rpt.get('methodology', {}).get('test_period')
            if acc is not None and tp:
                acc_note = f'Figures are model probabilities, not certainties. Reference accuracy on unseen matches ({tp}): {acc}% for win/draw/loss.'
        except Exception:
            pass
    for t in (acc_note,
              'Inputs: starting lineups and bench, player ratings from Transfermarkt data, recent form, and formation. Players outside their natural position are rated lower.',
              'Full lineups, team statistics and every scoreline are on the Raw Data sheet.'):
        put(r, 2, t, F(size=9, color=MUTE), merge_to=8, al=Alignment(wrap_text=True, vertical='top')); ws.row_dimensions[r].height = 26; r += 1
    ws.page_setup.orientation = 'portrait'; ws.page_setup.paperSize = 9; ws.page_setup.fitToWidth = 1; ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_area = f'A1:H{r}'

    # ---- raw data ----
    raw = wb.create_sheet('Raw Data')
    raw.sheet_view.showGridLines = False
    raw.sheet_properties.tabColor = NAVY
    pretty = lambda k: {'val': 'Market value', 'pos': 'Natural position', 'slot_pos': 'Played as', 'goals_per_90': 'Goals per 90', 'total_goals': 'Career goals',
                        'effective_rating': 'Effective rating', 'oop_penalty': 'Out-of-position penalty', 'anytime_prob': 'Chance to score %', 'career_goals': 'Career goals', 'expected_goals': 'Expected goals', 'oop_penalty': 'Out-of-position penalty', 'slot_pos': 'Played as'}.get(k, k.replace('_', ' ').capitalize())
    widths = {}
    rr = 1
    def block(title, rows, note=None, order=None):
        nonlocal rr
        if not rows: return
        cols = [c for c in order if c in rows[0]] if order else list(rows[0])
        raw.cell(rr, 1, title).font = F(size=13, bold=True, color=NAVY)
        for c in range(1, len(cols) + 1): raw.cell(rr, c).border = line(NAVY, 'medium')
        raw.row_dimensions[rr].height = 24; rr += 1
        if note: raw.cell(rr, 1, note).font = F(size=9, italic=True, color=MUTE); rr += 1
        for j, c in enumerate(cols, 1):
            x = raw.cell(rr, j, pretty(c)); x.font = F(size=10, bold=True, color='FFFFFF'); x.fill = fill(NAVY)
            x.alignment = Alignment(horizontal='left' if j == 1 else 'center', vertical='center', wrap_text=True)
            widths[j] = max(widths.get(j, 0), len(pretty(c)) + 2)
        raw.row_dimensions[rr].height = 30; rr += 1
        for n, row in enumerate(rows):
            for j, c in enumerate(cols, 1):
                v = row.get(c)
                if isinstance(v, bool): v = 'Yes' if v else 'No'
                elif isinstance(v, float): v = round(v, 2)
                x = raw.cell(rr, j, nm(v) if isinstance(v, str) else v)
                x.font = F(size=10); x.alignment = Alignment(horizontal='left' if j == 1 else 'center')
                if c == 'val' or (isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) >= 100000): x.number_format = '#,##0'
                if n % 2: x.fill = fill(PAPER)
                widths[j] = max(widths.get(j, 0), len(str(x.value)) + 2)
            rr += 1
        rr += 1

    inp = d.get('inputs') or {}
    block('Match inputs', [{'Home team': h, 'Away team': a, 'As-of Date': rep_dt, 'Home form (points per game)': inp.get('home_form_pts'), 'Away form (points per game)': inp.get('away_form_pts'), 'Knockout': inp.get('knockout')}])
    STAT = {'depth_gap': 'Starter-to-bench rating gap', 'has_outfield_in_gk': 'Outfield player in goal', 'height_mean_ATT': 'Average attacker height (cm)', 'height_mean_DEF': 'Average defender height (cm)',
            'overall_mean_ATT': 'Attack rating', 'overall_mean_DEF': 'Defence rating', 'overall_mean_GK': 'Goalkeeper rating', 'overall_mean_MID': 'Midfield rating',
            'starter_age_mean': 'Average starter age', 'starter_count': 'Starters', 'starter_height_mean': 'Average starter height (cm)', 'starter_market_val_sum': 'Starting XI market value',
            'starter_overall_max': 'Best starter rating', 'starter_overall_mean': 'Average starter rating', 'starter_overall_min': 'Weakest starter rating', 'starter_prime_mean': 'Age-prime factor (0 to 1)',
            'sub_count': 'Substitutes', 'sub_overall_max': 'Best substitute rating', 'sub_overall_mean': 'Average substitute rating'}
    block('Team statistics', [{'Statistic': STAT.get(k, pretty(k)), h: d['home_stats'][k], a: d['away_stats'][k]} for k in d['home_stats']])
    block('Team comparison', [{'Area': m['label'], h: m['home'], a: m['away']} for m in d['tactical_metrics']])
    for side, nme in (('home', h), ('away', a)):
        block(f'Lineup: {nme}', d['lineups'][side], 'Effective rating includes any out-of-position penalty.', ['name', 'role', 'slot_pos', 'pos', 'rating', 'effective_rating', 'oop_penalty', 'club', 'age', 'height', 'val', 'goals_per_90', 'total_goals'])
    for side, nme in (('home', h), ('away', a)):
        block(f'Goalscorer chances: {nme}', d['goalscorers'][side], None, ['name', 'pos', 'slot_pos', 'rating', 'effective_rating', 'oop_penalty', 'club', 'age', 'height', 'career_goals', 'goals_per_90', 'anytime_prob', 'expected_goals'])
    block('Top scorelines', [{'Score': s['score'], 'Probability %': s['prob']} for s in sp['top_scores']])
    block('All scorelines (probability %)', [{f'{h} goals': i, **{f'{a} {j}': v for j, v in enumerate(row)}} for i, row in enumerate(sp.get('score_grid', []))], f'Rows: {h} goals. Columns: {a} goals.')
    for j, w in widths.items(): raw.column_dimensions[L(j)].width = min(max(w, 11), 34)
    raw.column_dimensions['A'].width = min(max(widths.get(1, 12), 24), 34)
    raw.freeze_panes = 'B1'
    raw.page_setup.orientation = 'landscape'; raw.page_setup.paperSize = 9; raw.page_setup.fitToWidth = 1; raw.page_setup.fitToHeight = 0
    raw.sheet_properties.pageSetUpPr.fitToPage = True

    wb.properties.title = f'{h} v {a} - match prediction'
    wb.properties.creator = 'PitchPulse AI'
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='match_report.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'players': len(players_lite)})

@app.route('/api/players/search')
def search_players():
    q = (request.args.get('q') or '').strip().lower()
    role = (request.args.get('role') or request.args.get('pos') or '').strip().upper()
    status = (request.args.get('status') or 'all').strip().lower()
    limit = min(int(request.args.get('limit', 30)), 100)
    active_out, former_out = [], []
    for p in players_lite:
        is_f = bool(p.get('is_former'))
        if status == 'active' and is_f:
            continue
        if status == 'former' and not is_f:
            continue
        if role and role not in ('ALL', 'SUB'):
            p_role = (p.get('role') or '').upper()
            p_pos = (p.get('pos') or '').upper()
            if p_role != role and p_pos != role:
                continue
        if q and q not in f"{p.get('name','')} {p.get('full_name','')} {p.get('club','')} {p.get('former_club','')} {p.get('nat','')}".lower():
            continue
        if is_f:
            former_out.append(p)
        else:
            active_out.append(p)
        if status != 'former' and len(active_out) >= limit:
            break
        if status == 'former' and len(former_out) >= limit:
            break
    out = former_out[:limit] if status == 'former' else (active_out + former_out)[:limit]
    return jsonify(out)


@app.route('/api/matches/recent')
def recent_matches():
    try:
        return jsonify(get_recent_data())
    except Exception as e:
        return jsonify({'finished_matches': [], 'recent_predictions': [], 'error': str(e)}), 500


@app.route('/api/sync/status')
def sync_status():
    sb_url, _ = _sb_cfg()
    local_st = get_local_sync_state() or {}
    last_s = _sync_state.get('last_sync') or local_st.get('last_sync')
    return jsonify({
        'status': 'ok',
        'enabled': bool(_sync_state.get('enabled', True)),
        'running': bool(_sync_state.get('running', False)),
        'syncing': bool(_sync_state.get('running', False)),
        'supabase_configured': bool(sb_url),
        'interval_sec': int(_sync_state.get('interval_sec') or 21600),
        'last_sync': last_s,
        'last_run': last_s,
        'last_error': _sync_state.get('last_error'),
        'matches_synced': int(_sync_state.get('matches_synced') or 0),
        'players_updated': int(_sync_state.get('players_updated') or 0),
        'last_result': _sync_state.get('last_result') or local_st.get('last_result'),
    })


@app.route('/api/sync', methods=['POST'])
def trigger_sync():
    try:
        out = _run_sync_once()
        if out.get('status') == 'error':
            return jsonify(out), 500
        return jsonify(out)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/thesis-metrics')
def thesis_metrics():
    path = os.path.join(DATA_DIR, 'academic_report_data.json')
    if not os.path.exists(path):
        return jsonify({'status': 'missing'}), 404
    with open(path, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


_CTRY_QUERY_ALIASES = {
    'turkey': 'turkiye',
    'south korea': 'korea south',
    'ivory coast': 'cote d ivoire',
    'usa': 'united states',
    'united states of america': 'united states',
    'czechia': 'czech republic',
}
_EXPLORE_REGIONS = ['All', 'Top 5 European', 'Southeast Asia (ASEAN)', 'European Domestic & Cups', 'Americas & Global', 'International']


def _player_img(pid):
    det = _exp_blob('blob_player_details').get(str(pid))
    return det[5] if det and len(det) > 5 else ''


def _enrich_player_summary(p):
    out = _json_safe_player(p)
    if not out:
        return out
    pid = out.get('id')
    det = _exp_blob('blob_player_details').get(str(pid)) if pid is not None else None
    if not out.get('image_url') and det and len(det) > 5:
        out['image_url'] = det[5]
    if out.get('highest_val') is None and det and len(det) > 6:
        out['highest_val'] = det[6]
    if not out.get('role'):
        out['role'] = SUB_POS_TO_ROLE.get(out.get('sub_pos', '')) or POS_FALLBACK.get(out.get('pos', 'MID'), 'CM')
    out.setdefault('pos_role', out['role'])
    out['is_former'] = bool(out.get('is_former'))
    out.setdefault('former_club', '')
    return out


def _find_country_obj(name):
    if not name:
        return None
    clean = normalize_text(re.sub(r'\s*\(national team\)\s*$', '', str(name), flags=re.I))
    clean = _CTRY_QUERY_ALIASES.get(clean, clean)
    countries = explorer_bundle.get('countries') or []
    for c in countries:
        if normalize_text(c.get('name')) == clean or normalize_text(c.get('nt_name')) == clean:
            return c
    for c in countries:
        if clean and clean in normalize_text(c.get('name')):
            return c
    return None


@app.route('/api/explore/overview')
def explore_overview():
    clubs = _exp_blob('blob_clubs_light')
    countries = explorer_bundle.get('countries') or []
    leagues = explorer_bundle.get('leagues') or []
    top_clubs = sorted(clubs.values(), key=lambda x: (-float(x.get('total_val') or 0), -(x.get('avg_rating') or 0)))[:8]
    sea_leagues = [l for l in leagues if l.get('region_group') == 'Southeast Asia (ASEAN)']
    sea_names = {'indonesia', 'thailand', 'malaysia', 'vietnam', 'singapore', 'philippines'}
    sea_countries = [
        {k: v for k, v in c.items() if k not in ('top_player_ids', 'top_clubs', 'domestic_leagues')}
        for c in countries if normalize_text(c.get('name')) in sea_names
    ]
    featured_leagues = [l for l in leagues if l.get('comp_id') in ('GB1', 'ES1', 'L1', 'IT1', 'FR1', 'CL', 'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1')]
    featured_countries = [
        {k: v for k, v in c.items() if k not in ('top_player_ids', 'top_clubs', 'domestic_leagues')}
        for c in countries[:6]
    ] + [c for c in sea_countries if c.get('name') not in {x.get('name') for x in countries[:6]}]
    active_top = [_enrich_player_summary(p) for p in players_lite if not p.get('is_former')][:8]
    return jsonify({
        'status': 'success',
        'counts': {
            'players': len(players_lite),
            'active_players': sum(1 for p in players_lite if not p.get('is_former')),
            'former_players': sum(1 for p in players_lite if p.get('is_former')),
            'clubs': len(clubs),
            'countries': len(countries),
            'leagues': len(leagues),
            'presets': len(presets),
            'snapshots': _snap_count or (sum(len(v) for v in snap_rows.values()) if _hist_ready.is_set() else 0),
        },
        'top_players': active_top,
        'top_clubs': top_clubs,
        'sea_leagues': sea_leagues,
        'sea_countries': sea_countries,
        'featured_leagues': featured_leagues,
        'featured_clubs': top_clubs,
        'featured_countries': featured_countries,
    })


@app.route('/api/explore/players')
def explore_players():
    q_norm = normalize_text(request.args.get('q') or '')
    pos = (request.args.get('pos') or request.args.get('role') or '').strip().upper()
    status_filter = (request.args.get('status') or 'active').strip().lower()
    club_q = normalize_text(request.args.get('club') or '')
    nat_q = normalize_text(request.args.get('nat') or '')
    nat_q = _CTRY_QUERY_ALIASES.get(nat_q, nat_q)
    sort_by = (request.args.get('sort') or 'rating').strip().lower()
    try:
        min_rat = float(request.args.get('min_rating')) if request.args.get('min_rating') else None
    except ValueError:
        min_rat = None
    try:
        limit = max(1, min(int(request.args.get('limit', 40)), 200))
    except ValueError:
        limit = 40

    matches = []
    for p in players_lite:
        is_f = bool(p.get('is_former'))
        if status_filter == 'active' and is_f:
            continue
        if status_filter in ('former', 'legends', 'retired') and not is_f:
            continue
        if pos and pos != 'ALL':
            p_pos = (p.get('pos') or '').upper()
            p_role = (p.get('role') or '').upper()
            if p_pos != pos and p_role != pos:
                continue
        if min_rat is not None and float(p.get('rating') or 0) < min_rat:
            continue
        if club_q:
            c_hay = normalize_text(f"{p.get('club', '')} {p.get('former_club', '')}")
            if club_q not in c_hay:
                continue
        if nat_q and nat_q not in normalize_text(p.get('nat')):
            continue
        if q_norm:
            hay = normalize_text(f"{p.get('name', '')} {p.get('full_name', '')} {p.get('tm_name', '')} {p.get('club', '')} {p.get('former_club', '')} {p.get('nat', '')}")
            if q_norm not in hay:
                continue
        matches.append(p)

    if sort_by == 'val':
        matches.sort(key=lambda p: (-float(p.get('val') or 0), -float(p.get('rating') or 0)))
    elif sort_by == 'goals':
        matches.sort(key=lambda p: (-int(p.get('total_goals') or 0), -float(p.get('rating') or 0)))
    elif sort_by == 'assists':
        matches.sort(key=lambda p: (-int(p.get('total_assists') or 0), -float(p.get('rating') or 0)))
    else:
        matches.sort(key=lambda p: (-float(p.get('rating') or 0), -float(p.get('val') or 0)))

    return jsonify({
        'status': 'success',
        'status_filter': status_filter,
        'total': len(matches),
        'players': [_enrich_player_summary(p) for p in matches[:limit]],
    })


@app.route('/api/explore/player/<int:player_id>')
def explore_player_detail(player_id):
    base = player_by_id.get(player_id)
    if base is None:
        return jsonify({'status': 'error', 'message': 'Player not found'}), 404

    player = _json_safe_player(dict(base))
    det = _exp_blob('blob_player_details').get(str(player_id))
    leagues_meta = explorer_bundle.get('leagues_meta') or {}
    if det:
        comp_id = det[9] if len(det) > 9 else ''
        player.update({
            'foot': det[0],
            'dob': det[1],
            'city_of_birth': det[2],
            'country_of_birth': det[3],
            'contract': det[4],
            'image_url': det[5],
            'highest_val': det[6],
            'caps': det[7],
            'int_goals': det[8],
            'comp_id': comp_id,
            'comp_name': (leagues_meta.get(comp_id) or {}).get('name', comp_id),
        })

    raw_seasons = _exp_blob('blob_player_seasons').get(str(player_id), [])
    seasons = [{
        'season': s[0],
        'comp_id': s[1],
        'comp_name': (leagues_meta.get(s[1]) or {}).get('name', s[1]),
        'club': s[2],
        'apps': s[3],
        'minutes': s[4],
        'goals': s[5],
        'assists': s[6],
        'yellow_cards': s[7],
        'red_cards': s[8],
    } for s in raw_seasons]

    _ensure_hist()
    snapshots = [{
        'report_date': rd,
        'club': cl,
        'rating': rt,
        'form_delta': 0.0 if fd is None else fd,
        'val': vl,
        'age': ag,
        'goals_per_90': g9,
        'total_goals': tg,
    } for rd, cl, rt, fd, vl, ag, g9, tg in snap_rows.get(player_id, [])]

    return jsonify({'status': 'success', 'player': player, 'seasons': seasons, 'snapshots': snapshots})


@app.route('/api/explore/clubs')
def explore_clubs():
    q_norm = normalize_text(request.args.get('q') or '')
    comp_id = (request.args.get('comp_id') or '').strip().upper()
    ctry_q = normalize_text(request.args.get('country') or '')
    sort_by = (request.args.get('sort') or 'val').strip().lower()
    try:
        limit = max(1, min(int(request.args.get('limit', 40)), 200))
    except ValueError:
        limit = 40

    clubs = _exp_blob('blob_clubs_light')
    matches = []
    for c in clubs.values():
        if c.get('name') in ('---', 'Unknown', 'Disqualification', 'Without Club', 'Retired', 'Career break'):
            continue
        if comp_id and comp_id != 'ALL' and (c.get('comp_id') or '').upper() != comp_id:
            continue
        if ctry_q and ctry_q not in normalize_text(c.get('country_name')):
            continue
        if q_norm:
            hay = normalize_text(f"{c.get('name', '')} {c.get('comp_name', '')} {c.get('country_name', '')} {c.get('coach_name', '')}")
            if q_norm not in hay:
                continue
        matches.append(c)

    if sort_by in ('rating', 'avg_rating'):
        matches.sort(key=lambda c: (-float(c.get('avg_rating') or 0), -float(c.get('total_val') or 0)))
    elif sort_by in ('squad', 'squad_size'):
        matches.sort(key=lambda c: (-int(c.get('squad_size') or 0), -float(c.get('total_val') or 0)))
    elif sort_by == 'name':
        matches.sort(key=lambda c: (c.get('name') or '').lower())
    else:
        matches.sort(key=lambda c: (-float(c.get('total_val') or 0), -float(c.get('avg_rating') or 0)))

    return jsonify({'status': 'success', 'total': len(matches), 'clubs': matches[:limit]})


@app.route('/api/explore/club')
def explore_club_detail():
    cid_arg = (request.args.get('id') or '').strip()
    name_arg = (request.args.get('name') or '').strip()
    clubs = _exp_blob('blob_clubs_light')
    cid_str = None
    if cid_arg and cid_arg in clubs:
        cid_str = cid_arg
    elif name_arg:
        n_norm = normalize_text(name_arg)
        mapped = (explorer_bundle.get('club_norm_to_id') or {}).get(n_norm)
        if mapped is not None and str(mapped) in clubs:
            cid_str = str(mapped)
        else:
            cands = [c for c in clubs.values() if n_norm and n_norm in normalize_text(c.get('name'))]
            if cands:
                cands.sort(key=lambda c: (0 if normalize_text(c.get('name')).startswith(n_norm) else 1, -float(c.get('total_val') or 0)))
                cid_str = str(cands[0]['club_id'])

    if not cid_str or cid_str not in clubs:
        return jsonify({'status': 'error', 'message': 'Club not found'}), 404

    club = dict(clubs[cid_str])
    extras = _exp_blob('blob_club_extras').get(cid_str, {})
    pids = extras.get('player_ids') or []
    roster = [
        _enrich_player_summary(player_by_id[pid])
        for pid in pids
        if pid in player_by_id and not player_by_id[pid].get('is_former')
    ]
    cname_norm = normalize_text(club.get('name'))
    if not roster:
        roster = [
            _enrich_player_summary(p)
            for p in players_lite
            if not p.get('is_former') and normalize_text(p.get('club')) == cname_norm
        ]
    former_pids = extras.get('former_player_ids') or []
    former_players = [
        _enrich_player_summary(player_by_id[pid])
        for pid in former_pids
        if pid in player_by_id and player_by_id[pid].get('is_former')
    ]
    if not former_players:
        former_players = [
            _enrich_player_summary(p)
            for p in players_lite
            if p.get('is_former') and (
                normalize_text(p.get('former_club')) == cname_norm
                or normalize_text(p.get('club')) == cname_norm
            )
        ][:30]
    pname = club.get('preset_name')
    preset = presets.get(pname) if pname else None

    return jsonify({
        'status': 'success',
        'club': club,
        'season_records': extras.get('season_records', []),
        'recent_matches': extras.get('recent_matches', []),
        'roster': roster,
        'former_players': former_players,
        'preset': preset,
    })


@app.route('/api/explore/countries')
def explore_countries():
    q_norm = normalize_text(request.args.get('q') or '')
    conf = (request.args.get('confederation') or '').strip().upper()
    sort_by = (request.args.get('sort') or 'fifa').strip().lower()
    try:
        limit = max(1, min(int(request.args.get('limit', 124)), 200))
    except ValueError:
        limit = 124

    countries = explorer_bundle.get('countries') or []
    matches = []
    for c in countries:
        if conf and conf != 'ALL' and (c.get('confederation') or '').upper() != conf:
            continue
        if q_norm:
            hay = normalize_text(f"{c.get('name', '')} {c.get('code', '')} {c.get('nt_name', '')}")
            if q_norm not in hay:
                continue
        matches.append({k: v for k, v in c.items() if k not in ('top_player_ids', 'top_clubs', 'domestic_leagues')})

    if sort_by in ('rating', 'top11_avg_rating'):
        matches.sort(key=lambda c: (-float(c.get('top11_avg_rating') or 0), c.get('fifa_ranking') or 999))
    elif sort_by in ('val', 'top25_val'):
        matches.sort(key=lambda c: (-float(c.get('top25_val') or 0), -float(c.get('top11_avg_rating') or 0)))
    elif sort_by in ('players', 'total_players'):
        matches.sort(key=lambda c: (-int(c.get('total_players') or 0), -float(c.get('top11_avg_rating') or 0)))
    elif sort_by == 'name':
        matches.sort(key=lambda c: (c.get('name') or '').lower())
    else:
        matches.sort(key=lambda c: (c.get('fifa_ranking') if c.get('fifa_ranking') is not None else 999, -float(c.get('top11_avg_rating') or 0)))

    return jsonify({'status': 'success', 'total': len(matches), 'countries': matches[:limit]})


@app.route('/api/explore/country')
def explore_country_detail():
    name = (request.args.get('name') or '').strip()
    cobj = _find_country_obj(name)
    if not cobj:
        return jsonify({'status': 'error', 'message': 'Country not found'}), 404

    country = {k: v for k, v in cobj.items() if k not in ('top_player_ids', 'top_clubs', 'domestic_leagues')}
    top_players = [_enrich_player_summary(player_by_id[pid]) for pid in cobj.get('top_player_ids', []) if pid in player_by_id]
    pname = cobj.get('nt_preset_name')
    preset = presets.get(pname) if pname else None

    return jsonify({
        'status': 'success',
        'country': country,
        'domestic_leagues': cobj.get('domestic_leagues', []),
        'top_clubs': cobj.get('top_clubs', []),
        'top_players': top_players,
        'preset': preset,
    })


@app.route('/api/explore/leagues')
def explore_leagues():
    leagues = explorer_bundle.get('leagues') or []
    return jsonify({'status': 'success', 'regions': _EXPLORE_REGIONS, 'leagues': leagues})


@app.route('/api/explore/league')
def explore_league_detail():
    comp_id_raw = (request.args.get('comp_id') or 'GB1').strip()
    leagues_meta = explorer_bundle.get('leagues_meta') or {}
    league = leagues_meta.get(comp_id_raw) or next((v for k, v in leagues_meta.items() if k.upper() == comp_id_raw.upper()), None)
    if not league:
        return jsonify({'status': 'error', 'message': 'League not found'}), 404

    comp_id = league['comp_id']
    avail = league.get('available_seasons') or []
    try:
        season = int(request.args.get('season')) if request.args.get('season') else (avail[0] if avail else 2026)
    except ValueError:
        season = avail[0] if avail else 2026

    cs_key = f'{comp_id}|{season}'
    summary = (explorer_bundle.get('summary_by_comp_season') or {}).get((comp_id, season), {
        'total_matches': 0, 'total_goals': 0, 'avg_goals_per_match': 0.0,
        'home_win_pct': 0.0, 'draw_pct': 0.0, 'away_win_pct': 0.0, 'clean_sheet_pct': 0.0,
    })
    standings = _exp_blob('blob_standings').get(cs_key, [])
    lstats = _exp_blob('blob_league_stats')
    top_scorers = (lstats.get('sc') or {}).get(cs_key, [])
    top_assisters = (lstats.get('as') or {}).get(cs_key, [])
    recent_matches = (lstats.get('rec') or {}).get(cs_key, [])

    team_norms = {normalize_text(r.get('club_name')) for r in standings if r.get('club_name')}
    top_rated = []
    if league.get('type') == 'national_team_competition' and team_norms:
        for p in players_lite:
            if not p.get('is_former') and normalize_text(p.get('nat')) in team_norms:
                top_rated.append(_enrich_player_summary(p))
                if len(top_rated) >= 20:
                    break
    elif team_norms:
        for p in players_lite:
            if not p.get('is_former') and normalize_text(p.get('club')) in team_norms:
                top_rated.append(_enrich_player_summary(p))
                if len(top_rated) >= 20:
                    break
    if not top_rated:
        pdet = _exp_blob('blob_player_details')
        for p in players_lite:
            if p.get('is_former'):
                continue
            det = pdet.get(str(p.get('id')))
            if det and len(det) > 9 and det[9] == comp_id:
                top_rated.append(_enrich_player_summary(p))
                if len(top_rated) >= 20:
                    break
    if not top_rated and team_norms:
        for p in players_lite:
            if normalize_text(p.get('club')) in team_norms or normalize_text(p.get('former_club')) in team_norms:
                top_rated.append(_enrich_player_summary(p))
                if len(top_rated) >= 20:
                    break

    return jsonify({
        'status': 'success',
        'league': league,
        'season': season,
        'available_seasons': avail,
        'summary': summary,
        'standings': standings,
        'top_scorers': top_scorers,
        'top_assisters': top_assisters,
        'top_rated': top_rated,
        'recent_matches': recent_matches,
    })

threading.Thread(target=_bg_warmup, daemon=True, name='app-bg-warmup').start()
if _sync_state.get('enabled'):
    threading.Thread(target=_auto_sync_loop, daemon=True, name='app-auto-sync').start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Advanced 4-Tier Match Predictor with OOP Penalty running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
