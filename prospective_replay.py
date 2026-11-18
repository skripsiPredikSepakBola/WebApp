"""Weekly prospective replay on finished matches played after freeze_date (2026-11-17).

Starts from immutable 2026-11-12 base state (models/base_state_2026-11-12.json),
advances sequentially through all mapped matches > 2026-11-12, and scores both
production legacy (app.build_legacy_feature_pair) and candidate bundle arms on
mapped matches with lineups played after freeze_date.
"""
import json
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

import app as web_app
from features import FEATURE_COLS, build_feature_row, is_neutral_match, mirror
from league_tiers import LEAGUE_TIER_MAP, resolve_league_tier
from rebuild_state import (
    BASE_CUTOFF_DATE,
    BASE_STATE_PATH,
    fetch_finished_matches_paginated,
    load_trackers_from_base,
    map_match_ids,
)
from retrain import _extract_lineups
from retrain_gate import BUNDLE_PATH, sym_proba
from scoreline import rps
from sync_matches import _sb_cfg, _sb_req

ASEAN_LEAGUES = {'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'}


def paired_boot(p_leg, p_new, y, seed=0, n_boot=1000):
    idx = np.arange(len(y))
    d = (-np.log(np.clip(p_leg[idx, y], 1e-12, 1.0))) - (-np.log(np.clip(p_new[idx, y], 1e-12, 1.0)))
    rng = np.random.default_rng(seed)
    boot = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    return float(d.mean()), float(np.percentile(boot, 5)), float(np.percentile(boot, 95)), float((boot > 0).mean())


def run_prospective_replay(freeze_date='2026-11-18', matches=None, base_path=BASE_STATE_PATH):
    web_app._ensure_models()
    if matches is None:
        url, _ = _sb_cfg()
        if not url:
            return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}
        matches = fetch_finished_matches_paginated(after_date=BASE_CUTOFF_DATE)

    if not os.path.exists(BUNDLE_PATH):
        return {'status': 'skipped', 'reason': f'Missing candidate bundle at {BUNDLE_PATH}'}
    bundle = joblib.load(BUNDLE_PATH)

    with open(base_path, 'r', encoding='utf-8') as f:
        base = json.load(f)
    elo, leagues, teams, _, league_meta = load_trackers_from_base(base)
    club_name_to_id = base.get('club_name_to_id') or {}
    comp_name_to_id = base.get('comp_name_to_id') or {}
    known_cids = set(league_meta.keys()) | set(LEAGUE_TIER_MAP.keys())

    dedup = {}
    for m in matches:
        mid = m.get('match_id') or m.get('id')
        dt_str = str(m.get('match_date') or '')[:10]
        if mid and dt_str > BASE_CUTOFF_DATE and m.get('home_goals') is not None and m.get('away_goals') is not None:
            dedup[str(mid)] = (dt_str, str(mid), m)

    p_leg_all, p_new_all, y_all, cids = [], [], [], []
    mapped_by_comp, scored_by_comp = {}, {}
    total_post_freeze, mapped_post_freeze, skipped_unmapped_post_freeze = 0, 0, 0

    for dt_str, _, m in sorted(dedup.values(), key=lambda x: (x[0], x[1])):
        in_window = dt_str > freeze_date
        if in_window:
            total_post_freeze += 1

        hid, aid, cid = map_match_ids(m, club_name_to_id, comp_name_to_id, known_cids=known_cids)
        if hid is None or aid is None or cid is None:
            if in_window:
                skipped_unmapped_post_freeze += 1
            continue
        if in_window:
            mapped_post_freeze += 1
            mapped_by_comp[cid] = mapped_by_comp.get(cid, 0) + 1

        ht, at = str(m['home_team']).strip(), str(m['away_team']).strip()
        hg, ag = int(m['home_goals']), int(m['away_goals'])
        dt = pd.to_datetime(dt_str, errors='coerce')
        neu = is_neutral_match(cid)

        if in_window:
            lu = _extract_lineups(m.get('raw_json') or {})
            if lu:
                hs, hb, as_, ab = lu
                try:
                    sa, st_a, _ = web_app.aggregate_team_advanced(hs, hb, ht)
                    sb, st_b, _ = web_app.aggregate_team_advanced(as_, ab, at)
                    eh, ea = elo.rating(hid), elo.rating(aid)
                    gfh, gah, rh = teams.get(hid, dt if pd.notna(dt) else None)
                    gfa, gaa, ra = teams.get(aid, dt if pd.notna(dt) else None)
                    lgg, lgh = leagues.get(cid)
                    tier_v, _ = resolve_league_tier(cid)

                    # Production legacy arm (shared helper with app.py)
                    leg_ab, leg_ba = web_app.build_legacy_feature_pair(sa, sb, st_a, st_b)
                    p_leg = sym_proba(
                        web_app.model_advanced_3class,
                        pd.DataFrame([leg_ab])[web_app.advanced_features],
                        pd.DataFrame([leg_ba])[web_app.advanced_features],
                    )[0]

                    # New bundle arm (25 G6+tier features, keyed by id)
                    f_ab = build_feature_row(
                        sa, sb, web_app.cohesion_proxy(st_a), web_app.cohesion_proxy(st_b),
                        eh, ea, gfh, gah, rh, gfa, gaa, ra, (gfh - gah) - (gfa - gaa),
                        lgg, lgh, tier_v, neutral=neu,
                    )
                    f_ba = mirror(f_ab)
                    p_new = sym_proba(
                        bundle['clf'],
                        pd.DataFrame([f_ab])[FEATURE_COLS],
                        pd.DataFrame([f_ba])[FEATURE_COLS],
                    )[0]

                    y = 2 if hg > ag else (1 if hg == ag else 0)
                    p_leg_all.append(p_leg)
                    p_new_all.append(p_new)
                    y_all.append(y)
                    cids.append(cid)
                    scored_by_comp[cid] = scored_by_comp.get(cid, 0) + 1
                except Exception:
                    pass

        elo.update(hid, aid, hg, ag, neutral=neu)
        leagues.update(cid, hg, ag)
        if pd.notna(dt):
            teams.update(hid, hg, ag, dt)
            teams.update(aid, ag, hg, dt)

    mapping_cov = round(mapped_post_freeze / max(total_post_freeze, 1), 4)
    by_comp = {
        k: {
            'mapped': mapped_by_comp[k],
            'scored': scored_by_comp.get(k, 0),
            'lineup_rate': round(scored_by_comp.get(k, 0) / max(mapped_by_comp[k], 1), 4),
        }
        for k in sorted(mapped_by_comp)
    }
    domain_note = (
        'Only finished matches in the 74 history competitions (plus tracked UEFA Nations League '
        'divisions) with lineups (>= 7 starters per team) are scored; unmapped rows are '
        'out-of-domain youth, women, lower-tier, or friendly matches.'
    )
    if not y_all:
        return {
            'status': 'empty',
            'freeze_date': freeze_date,
            'domain_note': domain_note,
            'all_finished_matches': total_post_freeze,
            'mapped_matches': mapped_post_freeze,
            'skipped_unmapped': skipped_unmapped_post_freeze,
            'mapping_coverage': mapping_cov,
            'scored_matches': 0,
            'coverage': 0.0,
            'mapped_coverage': 0.0,
            'by_competition': by_comp,
        }

    PL, PN, Y = np.vstack(p_leg_all), np.vstack(p_new_all), np.array(y_all)
    mg, p5, p95, pgt = paired_boot(PL, PN, Y)
    res = {
        'status': 'ok',
        'freeze_date': freeze_date,
        'domain_note': domain_note,
        'all_finished_matches': total_post_freeze,
        'mapped_matches': mapped_post_freeze,
        'skipped_unmapped': skipped_unmapped_post_freeze,
        'mapping_coverage': mapping_cov,
        'scored_matches': int(len(Y)),
        'coverage': round(len(Y) / max(total_post_freeze, 1), 4),
        'mapped_coverage': round(len(Y) / max(mapped_post_freeze, 1), 4),
        'by_competition': by_comp,
        'legacy_ll': round(float(log_loss(Y, PL, labels=[0, 1, 2])), 5),
        'new_ll': round(float(log_loss(Y, PN, labels=[0, 1, 2])), 5),
        'legacy_rps': round(rps(PL, Y), 5),
        'new_rps': round(rps(PN, Y), 5),
        'boot_mean_gain': round(mg, 5),
        'boot_p5': round(p5, 5),
        'boot_p95': round(p95, 5),
        'P_new_better': round(pgt, 3),
        'new_home_gap': round(float(PN[:, 2].mean() - (Y == 2).mean()), 4),
        'new_draw_gap': round(float(PN[:, 1].mean() - (Y == 1).mean()), 4),
    }
    asean_mask = np.isin(cids, list(ASEAN_LEAGUES))
    if asean_mask.any():
        ya = Y[asean_mask]
        leg_a = float(log_loss(ya, PL[asean_mask], labels=[0, 1, 2]))
        new_a = float(log_loss(ya, PN[asean_mask], labels=[0, 1, 2]))
        res['asean'] = {
            'n': int(asean_mask.sum()),
            'legacy_ll': round(leg_a, 5),
            'new_ll': round(new_a, 5),
            'gain': round(leg_a - new_a, 5),
            'legacy_rps': round(rps(PL[asean_mask], ya), 5),
            'new_rps': round(rps(PN[asean_mask], ya), 5),
        }
    return res


if __name__ == '__main__':
    print(json.dumps(run_prospective_replay(), indent=2))
