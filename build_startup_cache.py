from collections import Counter
import json
import math
import os
import pickle
import re
import sys
import time
import unicodedata
import zlib

import joblib
import numpy as np
import pandas as pd

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
NON_CLUB_MARKERS = {'Retired', 'Without Club', 'Career break', '---', 'Unknown', ''}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
TM_DIR = os.path.join(ROOT_DIR, 'Football Data from Transfermarkt')
OUT_PATH = os.path.join(BASE_DIR, 'startup_cache.joblib')

NT_ALIASES = {
    'turkey': 'turkiye',
    'south korea': 'korea south',
    'ivory coast': 'cote d ivoire',
    'usa': 'united states',
    'united states of america': 'united states',
    'czechia': 'czech republic',
}


def normalize_text(text):
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text).lower()
    return ' '.join(text.split())


def _clean_str(val):
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _clean_int(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


_FLOAT_MEMO = {}


def _clean_native(val):
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, (float, np.floating)):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return _FLOAT_MEMO.setdefault(f, f)
    if isinstance(val, str):
        return sys.intern(val)
    if isinstance(val, dict):
        return {sys.intern(str(k)): _clean_native(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_clean_native(x) for x in val]
    return val


def _load_json(filename, default):
    for d in (BASE_DIR, ROOT_DIR):
        p = os.path.join(d, filename)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    return default


def _load_snapshots():
    s_dates, s_rows = {}, {}
    snap_path = os.path.join(BASE_DIR, 'player_monthly_snapshots.csv')
    if not os.path.exists(snap_path):
        snap_path = os.path.join(ROOT_DIR, 'player_monthly_snapshots.csv')
    if not os.path.exists(snap_path):
        return s_dates, s_rows

    wanted = {'player_id', 'report_date', 'club', 'rating', 'form_delta', 'val', 'age', 'goals_per_90', 'total_goals'}
    df = pd.read_csv(snap_path, usecols=lambda c: c in wanted, dtype={'report_date': 'str', 'club': 'str'}, low_memory=False)
    if df.empty or 'player_id' not in df.columns or 'report_date' not in df.columns:
        return s_dates, s_rows

    df = df.dropna(subset=['player_id', 'report_date'])
    df['player_id'] = pd.to_numeric(df['player_id'], errors='coerce')
    df = df.dropna(subset=['player_id'])
    df['player_id'] = df['player_id'].astype(int)
    df['report_date'] = df['report_date'].astype(str).str.slice(0, 10)
    df = df.sort_values(['player_id', 'report_date'], kind='mergesort')

    n = len(df)
    pids = df['player_id'].tolist()
    rds = [sys.intern(str(x)) for x in df['report_date'].tolist()]
    clubs = [sys.intern('' if pd.isna(x) else str(x)) for x in df['club']] if 'club' in df else [sys.intern('')] * n
    ratings = [None if pd.isna(x) else _FLOAT_MEMO.setdefault(round(float(x), 1), round(float(x), 1)) for x in pd.to_numeric(df['rating'], errors='coerce')] if 'rating' in df else [None] * n
    fdeltas = [_FLOAT_MEMO.setdefault(0.0, 0.0) if pd.isna(x) else _FLOAT_MEMO.setdefault(round(float(x), 2), round(float(x), 2)) for x in pd.to_numeric(df['form_delta'], errors='coerce')] if 'form_delta' in df else [_FLOAT_MEMO.setdefault(0.0, 0.0)] * n
    vals = [None if pd.isna(x) else int(round(float(x))) for x in pd.to_numeric(df['val'], errors='coerce')] if 'val' in df else [None] * n
    ages = [None if pd.isna(x) else _FLOAT_MEMO.setdefault(round(float(x), 1), round(float(x), 1)) for x in pd.to_numeric(df['age'], errors='coerce')] if 'age' in df else [None] * n
    g90s = [None if pd.isna(x) else _FLOAT_MEMO.setdefault(round(float(x), 3), round(float(x), 3)) for x in pd.to_numeric(df['goals_per_90'], errors='coerce')] if 'goals_per_90' in df else [None] * n
    tgs = [None if pd.isna(x) else int(x) for x in pd.to_numeric(df['total_goals'], errors='coerce')] if 'total_goals' in df else [None] * n

    for pid, rd, cl, rt, fd, vl, ag, g9, tg in zip(pids, rds, clubs, ratings, fdeltas, vals, ages, g90s, tgs):
        if pid not in s_dates:
            s_dates[pid] = []
            s_rows[pid] = []
        s_dates[pid].append(rd)
        s_rows[pid].append((rd, cl, rt, fd, vl, ag, g9, tg))

    return s_dates, s_rows


def build_cache():
    t0 = time.perf_counter()

    raw_players = _load_json('players_lite.json', [])
    presets = _clean_native(_load_json('preset_lineups.json', {}))
    categories = _clean_native(_load_json('preset_categories.json', {}))
    historical_presets = _clean_native(_load_json('historical_presets.json', {}))
    hist_presets_norm = {normalize_text(k): k for k in historical_presets}

    p_csv = pd.read_csv(
        os.path.join(TM_DIR, 'players.csv'),
        usecols=[
            'player_id',
            'image_url',
            'current_club_id',
            'current_national_team_id',
            'last_season',
            'current_club_name',
            'sub_position',
        ],
        low_memory=False,
    )
    clubs_df = pd.read_csv(os.path.join(TM_DIR, 'clubs.csv'), usecols=['club_id', 'name'], low_memory=False)
    nt_df = pd.read_csv(
        os.path.join(TM_DIR, 'national_teams.csv'),
        usecols=['national_team_id', 'name', 'country_name', 'team_image_url'],
        low_memory=False,
    )

    p_img = {}
    p_cid = {}
    p_nt_id = {}
    p_last_season = {}
    p_raw_club = {}
    p_sub_pos = {}
    for pid_raw, img_raw, cid_raw, ntid_raw, ls_raw, rclub_raw, spos_raw in zip(
        p_csv['player_id'],
        p_csv['image_url'],
        p_csv['current_club_id'],
        p_csv['current_national_team_id'],
        p_csv['last_season'],
        p_csv['current_club_name'],
        p_csv['sub_position'],
    ):
        pid = _clean_int(pid_raw)
        if pid is None:
            continue
        img = _clean_str(img_raw)
        if img:
            p_img[pid] = img
        cid = _clean_int(cid_raw)
        if cid is not None:
            p_cid[pid] = cid
        ntid = _clean_int(ntid_raw)
        if ntid is not None:
            p_nt_id[pid] = ntid
        ls = _clean_int(ls_raw)
        if ls is not None:
            p_last_season[pid] = ls
        rc = _clean_str(rclub_raw)
        if rc:
            p_raw_club[pid] = rc
        sp = _clean_str(spos_raw)
        if sp:
            p_sub_pos[pid] = sp

    club_norm_to_info = {}
    for cid_raw, cname_raw in zip(clubs_df['club_id'], clubs_df['name']):
        cid = _clean_int(cid_raw)
        cname = _clean_str(cname_raw)
        if cid is not None and cname:
            club_norm_to_info.setdefault(normalize_text(cname), (cid, cname))

    players_lite = []
    for raw_p in raw_players:
        p = _clean_native(raw_p)
        pid = _clean_int(p.get('id'))
        if pid is None:
            continue
        p[sys.intern('id')] = pid
        for int_k in ('val', 'height', 'pace', 'stamina', 'potential', 'total_goals', 'total_assists'):
            if p.get(int_k) is not None:
                p[sys.intern(int_k)] = int(round(float(p[int_k])))
        p[sys.intern('image_url')] = sys.intern(p_img.get(pid) or _clean_str(p.get('image_url')))

        sub_pos = _clean_str(p.get('sub_pos')) or p_sub_pos.get(pid, '')
        pos_4 = _clean_str(p.get('pos')) or 'MID'
        if not p.get('role'):
            p[sys.intern('role')] = sys.intern(SUB_POS_TO_ROLE.get(sub_pos) or POS_FALLBACK.get(pos_4, 'CM'))
        else:
            p[sys.intern('role')] = sys.intern(str(p['role']))

        ls = _clean_int(p.get('last_season'))
        if ls is None:
            ls = p_last_season.get(pid)
        p[sys.intern('last_season')] = ls

        raw_club = p_raw_club.get(pid) or _clean_str(p.get('club'))
        if 'is_former' in p and p['is_former'] is not None:
            is_former = bool(p['is_former'])
        else:
            is_former = bool((ls is not None and int(ls) <= 2024) or raw_club in NON_CLUB_MARKERS)
        p[sys.intern('is_former')] = is_former

        if 'former_club' in p and p['former_club'] is not None:
            f_club = _clean_str(p['former_club'])
        else:
            f_club = raw_club if (is_former and raw_club not in NON_CLUB_MARKERS) else ''
        p[sys.intern('former_club')] = sys.intern(f_club)

        cid = p_cid.get(pid)
        if cid is None:
            c_lookup = f_club if (is_former and f_club) else _clean_str(p.get('club'))
            if c_lookup:
                info = club_norm_to_info.get(normalize_text(c_lookup))
                cid = info[0] if info else None
        p[sys.intern('club_id')] = cid
        players_lite.append(p)

    players_lite.sort(key=lambda p: (-float(p.get('rating') or 0), int(p.get('id') or 0)))

    player_by_id = {p['id']: p for p in players_lite}
    player_by_name = {}
    player_search_blobs = []
    # Index active players first so retired homonyms do not shadow active players
    ordered_for_lookup = [p for p in players_lite if not p.get('is_former')] + [
        p for p in players_lite if p.get('is_former')
    ]
    for p in ordered_for_lookup:
        norms = []
        for k in ('name', 'full_name', 'tm_name'):
            raw_v = p.get(k) or ''
            low = sys.intern(raw_v.lower())
            nrm = sys.intern(normalize_text(raw_v))
            if low and low not in player_by_name:
                player_by_name[low] = p
            if nrm and nrm not in player_by_name:
                player_by_name[nrm] = p
            if nrm and nrm not in norms:
                norms.append(nrm)
        blob_s = norms[0] if len(norms) == 1 else sys.intern(' | '.join(norms))
        player_search_blobs.append((p, blob_s))

    def _resolve_pid(item):
        if isinstance(item, dict):
            pid = _clean_int(item.get('id'))
            if pid is not None and pid in player_by_id:
                return pid
            item_str = _clean_str(item.get('name'))
        elif isinstance(item, int) and item in player_by_id:
            return item
        else:
            item_str = _clean_str(item)
        if not item_str:
            return None
        p_hit = player_by_name.get(item_str.lower()) or player_by_name.get(normalize_text(item_str))
        if p_hit is not None:
            return p_hit['id']
        nrm = normalize_text(item_str)
        if nrm:
            for p_cand, blob in player_search_blobs:
                if nrm in blob:
                    return p_cand['id']
        return None

    preset_pids = set()
    for sq in presets.values():
        for x in (sq.get('starters') or []) + (sq.get('subs') or []):
            pid = _resolve_pid(x)
            if pid is not None:
                preset_pids.add(pid)

    top_2500_ids = {p['id'] for p in players_lite[:2500]}
    boot_ids = preset_pids | top_2500_ids
    boot_players = [p for p in players_lite if p['id'] in boot_ids]

    # Build national team lookup + preset_meta
    nt_norm_to_info = {}
    for _, r in nt_df.iterrows():
        nid = _clean_int(r['national_team_id'])
        img = _clean_str(r['team_image_url'])
        if not img and nid is not None:
            img = f'https://tmssl.akamaized.net/images/wappen/head/{nid}.png'
        for col in ('name', 'country_name'):
            nv = normalize_text(_clean_str(r[col]))
            if nv:
                nt_norm_to_info.setdefault(nv, (nid, img))

    preset_meta = {}
    for pname, sq in presets.items():
        if pname.endswith(' (National Team)'):
            base = pname[:-len(' (National Team)')]
            nb = NT_ALIASES.get(normalize_text(base), normalize_text(base))
            info = nt_norm_to_info.get(nb)
            if info:
                nid, crest = info
            else:
                nt_counts = Counter()
                for x in (sq.get('starters') or []) + (sq.get('subs') or []):
                    pid = _resolve_pid(x)
                    if pid is not None and pid in p_nt_id:
                        nt_counts[p_nt_id[pid]] += 1
                nid = nt_counts.most_common(1)[0][0] if nt_counts else None
                crest = f'https://tmssl.akamaized.net/images/wappen/head/{nid}.png' if nid is not None else ''
            entry = {'crest_url': crest, 'club_id': nid, 'is_national': True}
            preset_meta[pname] = entry
            preset_meta[normalize_text(pname)] = entry
            preset_meta.setdefault(base, entry)
            preset_meta.setdefault(normalize_text(base), entry)
        elif pname.endswith(' Legends') or pname.endswith(' Icons'):
            base = pname[:-len(' Legends')] if pname.endswith(' Legends') else ''
            info = club_norm_to_info.get(normalize_text(base)) if base else None
            if info:
                cid = info[0]
            else:
                cid = None
            crest = f'https://tmssl.akamaized.net/images/wappen/head/{cid}.png' if cid is not None else ''
            entry = {'crest_url': crest, 'club_id': cid, 'is_national': False, 'is_legend': True}
            preset_meta[pname] = entry
            preset_meta[normalize_text(pname)] = entry
        else:
            info = club_norm_to_info.get(normalize_text(pname))
            canon_name = None
            if info:
                cid, canon_name = info
            else:
                cid_counts = Counter()
                for x in (sq.get('starters') or []):
                    pid = _resolve_pid(x)
                    if pid is not None and player_by_id[pid].get('club_id') is not None:
                        cid_counts[player_by_id[pid]['club_id']] += 1
                if not cid_counts:
                    for x in (sq.get('subs') or []):
                        pid = _resolve_pid(x)
                        if pid is not None and player_by_id[pid].get('club_id') is not None:
                            cid_counts[player_by_id[pid]['club_id']] += 1
                cid = cid_counts.most_common(1)[0][0] if cid_counts else None
            crest = f'https://tmssl.akamaized.net/images/wappen/head/{cid}.png' if cid is not None else ''
            entry = {'crest_url': crest, 'club_id': cid, 'is_national': False}
            preset_meta[pname] = entry
            preset_meta[normalize_text(pname)] = entry
            if canon_name and canon_name != pname:
                preset_meta.setdefault(canon_name, entry)
                preset_meta.setdefault(normalize_text(canon_name), entry)

    snap_dates, snap_rows = _load_snapshots()
    snap_count = sum(len(v) for v in snap_rows.values())

    bundle = {
        'players_lite': players_lite,
        'boot_players': boot_players,
        'player_by_id': player_by_id,
        'player_by_name': player_by_name,
        'player_search_blobs': player_search_blobs,
        'presets': presets,
        'categories': categories,
        'preset_meta': preset_meta,
        'snap_count': snap_count,
        'blob_snapshots': zlib.compress(
            pickle.dumps((snap_dates, snap_rows), protocol=pickle.HIGHEST_PROTOCOL),
            level=9,
        ),
        'blob_historical': zlib.compress(
            pickle.dumps((historical_presets, hist_presets_norm), protocol=pickle.HIGHEST_PROTOCOL),
            level=6,
        ),
    }

    tmp_path = f'{OUT_PATH}.tmp'
    joblib.dump(bundle, tmp_path, compress=0)
    sz_mb = os.path.getsize(tmp_path) / (1024 * 1024)
    t_a = time.perf_counter()
    with open(tmp_path, 'rb') as f:
        _ = pickle.load(f)
    t_b = time.perf_counter()
    os.replace(tmp_path, OUT_PATH)

    total_s = time.perf_counter() - t0
    print(
        f'Saved {OUT_PATH} (compress=0+zlib, {sz_mb:.2f} MB, '
        f'load={t_b - t_a:.3f}s) in {total_s:.2f}s | '
        f'players={len(players_lite)}, boot_players={len(boot_players)}, '
        f'presets={len(presets)}, preset_meta_keys={len(preset_meta)}, '
        f'snap_players={len(snap_dates)}'
    )


if __name__ == '__main__':
    build_cache()
