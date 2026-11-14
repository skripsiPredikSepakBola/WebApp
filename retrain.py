import json
import os
import joblib
import numpy as np
import pandas as pd
from collections import defaultdict, deque
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import log_loss

from app import aggregate_team_advanced, cohesion_proxy, advanced_features, model_advanced_3class
from sync_matches import _sb_cfg, _sb_req

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_3_PATH = os.path.join(BASE_DIR, 'model_advanced_3class.joblib')
MODEL_XG_PATH = os.path.join(BASE_DIR, 'model_advanced_xg.joblib')


_POS_MAP = {
    'G': 'GK', 'GK': 'GK', 'GOALKEEPER': 'GK',
    'D': 'DEF', 'DEF': 'DEF', 'DEFENDER': 'DEF',
    'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF', 'LCB': 'DEF', 'RCB': 'DEF', 'LWB': 'DEF', 'RWB': 'DEF',
    'M': 'MID', 'MID': 'MID', 'MIDFIELDER': 'MID', 'MIDFIELD': 'MID',
    'CM': 'MID', 'DM': 'MID', 'AM': 'MID', 'LM': 'MID', 'RM': 'MID',
    'F': 'ATT', 'ATT': 'ATT', 'ATTACK': 'ATT', 'ATTACKER': 'ATT', 'STRIKER': 'ATT', 'FORWARD': 'ATT',
    'CF': 'ATT', 'LW': 'ATT', 'RW': 'ATT', 'SS': 'ATT',
}


def _norm_pos(val):
    return _POS_MAP.get(str(val or '').strip().upper(), 'MID')


def _tm_player(p):
    pos_obj = p.get('position') or {}
    slot_pos = _norm_pos(pos_obj.get('category') or pos_obj.get('shortName'))
    item = {'slot_pos': slot_pos}
    pid = p.get('id')
    if pid is not None and str(pid).isdigit():
        item['id'] = int(pid)
    if p.get('name'):
        item['name'] = p['name']
    return item


def _extract_lineups(raw):
    lineups = raw.get('lineups') or []
    if len(lineups) >= 2:
        home_id = (raw.get('teams') or {}).get('home', {}).get('id')
        h_lu = next((x for x in lineups if (x.get('team') or {}).get('id') == home_id), lineups[0])
        a_lu = next((x for x in lineups if x is not h_lu), lineups[1])
        to_af = lambda arr: [{
            'name': (p.get('player') or {}).get('name', ''),
            'slot_pos': _norm_pos((p.get('player') or {}).get('pos')),
        } for p in (arr or [])]
        hs, as_ = to_af(h_lu.get('startXI')), to_af(a_lu.get('startXI'))
        if len(hs) >= 7 and len(as_) >= 7:
            return hs, to_af(h_lu.get('substitutes')), as_, to_af(a_lu.get('substitutes'))

    hc_lu = (raw.get('homeClub') or {}).get('lineup') or {}
    ac_lu = (raw.get('awayClub') or {}).get('lineup') or {}
    if hc_lu and ac_lu:
        hs = [_tm_player(p) for p in (hc_lu.get('players') or [])]
        as_ = [_tm_player(p) for p in (ac_lu.get('players') or [])]
        if len(hs) >= 7 and len(as_) >= 7:
            hb = [_tm_player(p) for p in (hc_lu.get('substitutes') or [])]
            ab = [_tm_player(p) for p in (ac_lu.get('substitutes') or [])]
            return hs, hb, as_, ab
    return None


def build_dataset(matches):
    form = defaultdict(lambda: deque(maxlen=5))
    rows_X, rows_y3, rows_yxg = [], [], []

    for m in matches:
        hg, ag = m.get('home_goals'), m.get('away_goals')
        if hg is None or ag is None:
            continue
        ht, at = m['home_team'], m['away_team']
        h_pts = sum(p for p, _ in form[ht]) / max(len(form[ht]), 1) if form[ht] else 1.5
        a_pts = sum(p for p, _ in form[at]) / max(len(form[at]), 1) if form[at] else 1.5
        h_gd = sum(g for _, g in form[ht]) / max(len(form[ht]), 1) if form[ht] else 0.0
        a_gd = sum(g for _, g in form[at]) / max(len(form[at]), 1) if form[at] else 0.0

        lu = _extract_lineups(m.get('raw_json') or {})
        if lu:
            hs, hb, as_, ab = lu
            try:
                sa, st_a, _ = aggregate_team_advanced(hs, hb, ht)
                sb, st_b, _ = aggregate_team_advanced(as_, ab, at)
                f_ab = {
                    'diff_overall_mean': sa['starter_overall_mean'] - sb['starter_overall_mean'],
                    'diff_overall_max': sa['starter_overall_max'] - sb['starter_overall_max'],
                    'diff_overall_min': sa['starter_overall_min'] - sb['starter_overall_min'],
                    'diff_attack_vs_defense': sa['overall_mean_ATT'] - sb['overall_mean_DEF'],
                    'diff_defense_vs_attack': sa['overall_mean_DEF'] - sb['overall_mean_ATT'],
                    'diff_midfield': sa['overall_mean_MID'] - sb['overall_mean_MID'],
                    'diff_sub_mean': sa['sub_overall_mean'] - sb['sub_overall_mean'],
                    'diff_depth_gap': sa['depth_gap'] - sb['depth_gap'],
                    'diff_market_val_log': float(np.log1p(sa['starter_market_val_sum']) - np.log1p(sb['starter_market_val_sum'])),
                    'diff_form_pts_5': h_pts - a_pts,
                    'diff_form_gd_5': h_gd - a_gd,
                    'diff_aerial_att_vs_def': sa['height_mean_ATT'] - sb['height_mean_DEF'],
                    'diff_aerial_def_vs_att': sa['height_mean_DEF'] - sb['height_mean_ATT'],
                    'diff_prime_score': sa['starter_prime_mean'] - sb['starter_prime_mean'],
                    'diff_cohesion': cohesion_proxy(st_a) - cohesion_proxy(st_b),
                    'league_tier_factor': 0.95,
                }
                f_ba = {k: (v if k == 'league_tier_factor' else -v) for k, v in f_ab.items()}
                f_ba['diff_attack_vs_defense'] = -f_ab['diff_defense_vs_attack']
                f_ba['diff_defense_vs_attack'] = -f_ab['diff_attack_vs_defense']
                f_ba['diff_aerial_att_vs_def'] = -f_ab['diff_aerial_def_vs_att']
                f_ba['diff_aerial_def_vs_att'] = -f_ab['diff_aerial_att_vs_def']

                y_ab = 2 if hg > ag else (1 if hg == ag else 0)
                y_ba = 0 if y_ab == 2 else (2 if y_ab == 0 else 1)
                rows_X.extend([f_ab, f_ba])
                rows_y3.extend([y_ab, y_ba])
                rows_yxg.extend([float(hg), float(ag)])
            except Exception:
                pass

        form[ht].append((3 if hg > ag else (1 if hg == ag else 0), hg - ag))
        form[at].append((3 if ag > hg else (1 if ag == hg else 0), ag - hg))

    if not rows_X:
        return None, None, None
    return pd.DataFrame(rows_X)[advanced_features], np.array(rows_y3), np.array(rows_yxg)


def retrain(min_matches=50):
    url, _ = _sb_cfg()
    if not url:
        return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}

    matches = _sb_req('finished_matches?select=home_team,away_team,home_goals,away_goals,match_date,raw_json&order=match_date.asc&limit=5000') or []
    X, y3, yxg = build_dataset(matches)
    if X is None or len(X) < min_matches * 2:
        return {'status': 'skipped', 'reason': f'Need >= {min_matches} matches with lineups (found {(len(X)//2) if X is not None else 0})'}

    split = int(len(X) * 0.8)
    X_tr, X_val = X.iloc[:split], X.iloc[split:]
    y3_tr, y3_val = y3[:split], y3[split:]
    yxg_tr = yxg[:split]

    new_3c = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, random_state=42).fit(X_tr, y3_tr)
    new_xg = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=42).fit(X_tr, yxg_tr)

    new_ll = float(log_loss(y3_val, new_3c.predict_proba(X_val), labels=[0, 1, 2]))
    old_ll = float(log_loss(y3_val, model_advanced_3class.predict_proba(X_val), labels=[0, 1, 2]))

    if new_ll <= old_ll:
        joblib.dump(new_3c, MODEL_3_PATH)
        joblib.dump(new_xg, MODEL_XG_PATH)
        return {'status': 'promoted', 'samples': len(X), 'old_log_loss': round(old_ll, 4), 'new_log_loss': round(new_ll, 4)}
    return {'status': 'rejected', 'samples': len(X), 'old_log_loss': round(old_ll, 4), 'new_log_loss': round(new_ll, 4)}


if __name__ == '__main__':
    print(json.dumps(retrain()))
