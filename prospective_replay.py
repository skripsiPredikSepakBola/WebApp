"""Weekly prospective replay on finished matches played after freeze_date (2026-11-17).

Scores both legacy and new models sequentially in date order using exact as-of state,
then compares LL, RPS, calibration, and ASEAN subset via paired bootstrap.
"""
import json
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

import app as web_app
from elo import EloTracker
from features import FEATURE_COLS, LeagueStats, TeamState, build_feature_row, is_neutral_match, mirror
from league_tiers import resolve_league_tier
from retrain import _extract_lineups
from retrain_gate import BUNDLE_PATH, META_PATH, sym_proba
from scoreline import rps
from sync_matches import _sb_cfg, _sb_req

ASEAN_LEAGUES = {'IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'}


def paired_boot(p_leg, p_new, y, seed=0, n_boot=1000):
    idx = np.arange(len(y))
    d = (-np.log(np.clip(p_leg[idx, y], 1e-12, 1.0))) - (-np.log(np.clip(p_new[idx, y], 1e-12, 1.0)))
    rng = np.random.default_rng(seed)
    boot = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)])
    return float(d.mean()), float(np.percentile(boot, 5)), float(np.percentile(boot, 95)), float((boot > 0).mean())


def run_prospective_replay(freeze_date='2026-11-17', matches=None):
    web_app._ensure_models()
    if matches is None:
        url, _ = _sb_cfg()
        if not url:
            return {'status': 'skipped', 'reason': 'Set SUPABASE_URL and SUPABASE_KEY'}
        matches = _sb_req(
            f'finished_matches?select=match_id,home_team,away_team,home_goals,away_goals,match_date,league,raw_json'
            f'&match_date=gt.{freeze_date}&order=match_date.asc&limit=5000'
        ) or []

    if not os.path.exists(BUNDLE_PATH):
        return {'status': 'skipped', 'reason': f'Missing candidate bundle at {BUNDLE_PATH}'}
    bundle = joblib.load(BUNDLE_PATH)

    elo, leagues, teams = EloTracker(), LeagueStats(), TeamState()
    for name, v in (web_app.TEAM_STATE.get('by_name') or {}).items():
        elo.r[name] = float(v.get('elo', 1500.0))
        if v.get('last_date'):
            teams.last[name] = pd.Timestamp(v['last_date'])
    for cid, v in (web_app.LEAGUE_STATE or {}).items():
        leagues.n[cid] = int(v.get('n', 0))
        leagues.goals[cid] = float(v.get('goals', 0.0))
        leagues.home[cid] = float(v.get('home', 0.0))

    p_leg_all, p_new_all, y_all, cids = [], [], [], []
    dedup = {}
    for m in matches:
        mid = m.get('match_id') or m.get('id')
        dt_str = str(m.get('match_date') or '')[:10]
        if mid and dt_str > freeze_date and m.get('home_goals') is not None and m.get('away_goals') is not None:
            dedup[str(mid)] = (dt_str, str(mid), m)

    total_finished = len(dedup)
    for dt_str, _, m in sorted(dedup.values(), key=lambda x: (x[0], x[1])):
        ht, at = str(m['home_team']).strip(), str(m['away_team']).strip()
        hg, ag = int(m['home_goals']), int(m['away_goals'])
        cid = str(m.get('league') or '').strip()
        dt = pd.to_datetime(dt_str, errors='coerce')
        neu = is_neutral_match(cid)

        lu = _extract_lineups(m.get('raw_json') or {})
        if lu:
            hs, hb, as_, ab = lu
            try:
                sa, st_a, _ = web_app.aggregate_team_advanced(hs, hb, ht)
                sb, st_b, _ = web_app.aggregate_team_advanced(as_, ab, at)
                eh, ea = elo.rating(ht), elo.rating(at)
                gfh, gah, rh = teams.get(ht, dt if pd.notna(dt) else None)
                gfa, gaa, ra = teams.get(at, dt if pd.notna(dt) else None)
                lgg, lgh = leagues.get(cid)
                tier_v, _ = resolve_league_tier(cid)

                # Legacy probabilities
                leg_ab = {
                    'diff_overall_mean': sa['starter_overall_mean'] - sb['starter_overall_mean'],
                    'diff_overall_max': sa['starter_overall_max'] - sb['starter_overall_max'],
                    'diff_overall_min': sa['starter_overall_min'] - sb['starter_overall_min'],
                    'diff_attack_vs_defense': sa['overall_mean_ATT'] - sb['overall_mean_DEF'],
                    'diff_defense_vs_attack': sa['overall_mean_DEF'] - sb['overall_mean_ATT'],
                    'diff_midfield': sa['overall_mean_MID'] - sb['overall_mean_MID'],
                    'diff_sub_mean': sa['sub_overall_mean'] - sb['sub_overall_mean'],
                    'diff_depth_gap': sa['depth_gap'] - sb['depth_gap'],
                    'diff_market_val_log': float(np.log1p(sa['starter_market_val_sum']) - np.log1p(sb['starter_market_val_sum'])),
                    'diff_form_pts_5': (3.0 if gfh > gah else 1.5) - (3.0 if gfa > gaa else 1.5),
                    'diff_form_gd_5': (gfh - gah) - (gfa - gaa),
                    'diff_aerial_att_vs_def': sa['height_mean_ATT'] - sb['height_mean_DEF'],
                    'diff_aerial_def_vs_att': sa['height_mean_DEF'] - sb['height_mean_ATT'],
                    'diff_prime_score': sa['starter_prime_mean'] - sb['starter_prime_mean'],
                    'diff_cohesion': web_app.cohesion_proxy(st_a) - web_app.cohesion_proxy(st_b),
                    'league_tier_factor': 0.95,
                }
                leg_ba = {k: (v if k == 'league_tier_factor' else -v) for k, v in leg_ab.items()}
                leg_ba['diff_attack_vs_defense'] = -leg_ab['diff_defense_vs_attack']
                leg_ba['diff_defense_vs_attack'] = -leg_ab['diff_attack_vs_defense']
                leg_ba['diff_aerial_att_vs_def'] = -leg_ab['diff_aerial_def_vs_att']
                leg_ba['diff_aerial_def_vs_att'] = -leg_ab['diff_aerial_att_vs_def']
                p_leg = sym_proba(
                    web_app.model_advanced_3class,
                    pd.DataFrame([leg_ab])[web_app.advanced_features],
                    pd.DataFrame([leg_ba])[web_app.advanced_features],
                )[0]

                # New bundle probabilities
                f_ab = build_feature_row(
                    sa, sb, web_app.cohesion_proxy(st_a), web_app.cohesion_proxy(st_b),
                    eh, ea, gfh, gah, rh, gfa, gaa, ra, (gfh - gah) - (gfa - gaa),
                    lgg, lgh, tier_v, neutral=neu,
                )
                f_ba = mirror(f_ab)
                p_new = sym_proba(bundle['clf'], pd.DataFrame([f_ab])[FEATURE_COLS], pd.DataFrame([f_ba])[FEATURE_COLS])[0]

                y = 2 if hg > ag else (1 if hg == ag else 0)
                p_leg_all.append(p_leg)
                p_new_all.append(p_new)
                y_all.append(y)
                cids.append(cid)
            except Exception:
                pass

        elo.update(ht, at, hg, ag, neutral=neu)
        leagues.update(cid, hg, ag)
        teams.update(ht, hg, ag, dt if pd.notna(dt) else None)
        teams.update(at, ag, hg, dt if pd.notna(dt) else None)

    if not y_all:
        return {'status': 'empty', 'freeze_date': freeze_date, 'all_finished_matches': total_finished, 'scored_matches': 0, 'coverage': 0.0}

    PL, PN, Y = np.vstack(p_leg_all), np.vstack(p_new_all), np.array(y_all)
    mg, p5, p95, pgt = paired_boot(PL, PN, Y)
    res = {
        'status': 'ok',
        'freeze_date': freeze_date,
        'all_finished_matches': total_finished,
        'scored_matches': int(len(Y)),
        'coverage': round(len(Y) / max(total_finished, 1), 4),
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
