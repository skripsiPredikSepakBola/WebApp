"""Independent F11 Train/Serve Parity + Rescaled Grid + Section 11 Gate Checks."""
import math
import os
import random
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import log_loss

import app as web_app
from features import FEATURE_COLS, mirror
from league_tiers import resolve_league_tier
from retrain_gate import CLF_PARAMS, FIXED_BLEND_W, REG_PARAMS, fit_bundle, gate, retrain as gated_retrain, sym_proba, _split_pairs
from scoreline import rescale_grid_to_wdl, rps, score_grid, wdl_from_grid


def test_f11_independent_parity(n=100, seed=42):
    web_app._ensure_models()
    p_map = {p['name']: p for p in web_app.players_lite}
    roles = ['GK', 'LB', 'CB', 'CB', 'RB', 'CM', 'CM', 'CAM', 'LW', 'ST', 'RW']
    preset_names = [k for k, v in web_app.presets.items() if len(v.get('starters', [])) >= 11]
    rng = random.Random(seed)
    cids = ['GB1', 'ES1', 'L1', 'IT1', 'FR1', 'CL', 'IN1L', 'THA1', 'UNKNOWN_LG']

    max_diff = 0.0
    for i in range(n):
        ha, hb = rng.sample(preset_names, 2)
        cid = cids[i % len(cids)]
        neutral = (cid == 'CL' and i % 3 == 0)
        st_a_in = [{'id': p_map[nm]['id'], 'name': nm, 'slot_pos': r}
                   for nm, r in zip(web_app.presets[ha]['starters'][:11], roles) if nm in p_map]
        st_b_in = [{'id': p_map[nm]['id'], 'name': nm, 'slot_pos': r}
                   for nm, r in zip(web_app.presets[hb]['starters'][:11], roles) if nm in p_map]
        if len(st_a_in) < 8 or len(st_b_in) < 8:
            continue
        payload = {'league_id': cid, 'neutral': neutral, 'home_rest': 5.0, 'away_rest': 7.0}

        # Serve path (same calls as predict())
        stats_a, st_a, _ = web_app.aggregate_team_advanced(st_a_in, [], ha)
        stats_b, st_b, _ = web_app.aggregate_team_advanced(st_b_in, [], hb)
        f_ab, f_ba, ctx = web_app.build_bundle_feature_pair(ha, hb, st_a, st_b, stats_a, stats_b, payload)

        # Independent reference calculation (does NOT call build_feature_row)
        sa_st = web_app._lookup_team_state(ha) or {}
        sb_st = web_app._lookup_team_state(hb) or {}
        lg_st = web_app.LEAGUE_STATE.get(cid, {'avg_goals': 2.7, 'home_win': 0.45})
        tier_v, _ = resolve_league_tier(cid)
        elo_a, elo_b = sa_st.get('elo', 1500.0), sb_st.get('elo', 1500.0)
        gfa, gaa = sa_st.get('gf10', 1.35), sa_st.get('ga10', 1.35)
        gfb, gab = sb_st.get('gf10', 1.35), sb_st.get('ga10', 1.35)
        coh_a, coh_b = web_app.cohesion_proxy(st_a), web_app.cohesion_proxy(st_b)

        ref = {
            'diff_overall_mean': stats_a['starter_overall_mean'] - stats_b['starter_overall_mean'],
            'diff_sub_mean': stats_a['sub_overall_mean'] - stats_b['sub_overall_mean'],
            'diff_market_val_log': math.log1p(stats_a['starter_market_val_sum']) - math.log1p(stats_b['starter_market_val_sum']),
            'diff_form_gd_5': (gfa - gaa) - (gfb - gab),
            'diff_cohesion': coh_a - coh_b,
            'diff_elo': elo_a - elo_b,
            'home_flag': 0.0 if neutral else 1.0,
            'sum_elo': elo_a + elo_b,
            'league_avg_goals': float(lg_st['avg_goals']),
            'league_home_win_rate': float(lg_st['home_win']),
            'league_tier_factor': float(tier_v),
            'own_att': stats_a['overall_mean_ATT'], 'opp_att': stats_b['overall_mean_ATT'],
            'own_def': stats_a['overall_mean_DEF'], 'opp_def': stats_b['overall_mean_DEF'],
            'own_gk': stats_a['overall_mean_GK'], 'opp_gk': stats_b['overall_mean_GK'],
            'own_elo': elo_a, 'opp_elo': elo_b,
            'own_gf10': gfa, 'opp_gf10': gfb,
            'own_ga10': gaa, 'opp_ga10': gab,
            'own_rest': 5.0, 'opp_rest': 7.0,
        }
        for c in FEATURE_COLS:
            d = abs(f_ab[c] - ref[c])
            max_diff = max(max_diff, d)
            assert d < 1e-9, f"{c}: {f_ab[c]} vs {ref[c]}"
        assert mirror(f_ba) == f_ab
    print(f"F11 Independent Payload Parity PASSED ({n} matchups, max_diff={max_diff:.2e} < 1e-9).")


def test_rescaled_grid_and_gate():
    web_app._ensure_models()
    assert web_app.USE_BUNDLE is False
    hist = pd.read_parquet(os.path.join(web_app.DATA_DIR, 'data', 'history_features.parquet'))

    p_all, y_all = [], []
    max_reg_err, max_sym_err = 0.0, 0.0
    last_bundle, last_va = None, None

    for ts in (2023, 2024, 2025, 2026):
        tr, va, te = hist[hist.season < ts - 1], hist[hist.season == ts - 1], hist[hist.season == ts]
        b = fit_bundle(tr, va, FEATURE_COLS)
        full = hist[hist.season < ts]
        clf = HistGradientBoostingClassifier(**CLF_PARAMS).fit(full[FEATURE_COLS], full.y3)
        reg = HistGradientBoostingRegressor(**REG_PARAMS).fit(full[FEATURE_COLS], full.goals_a)

        tf, tm = _split_pairs(te)
        tla, tlb = reg.predict(tf[FEATURE_COLS]), reg.predict(tm[FEATURE_COLS])
        p_ab = sym_proba(clf, tf[FEATURE_COLS], tm[FEATURE_COLS])
        p_ba = sym_proba(clf, tm[FEATURE_COLS], tf[FEATURE_COLS])
        max_sym_err = max(max_sym_err, float(np.max(np.abs(p_ab[:, 2] - p_ba[:, 0]))))

        # Verify rescaled grid region totals match classifier W/D/L to 1e-9 (sample first 500 per fold for speed)
        for idx in range(min(500, len(tf))):
            pb, pd_, pa = float(p_ab[idx, 0]), float(p_ab[idx, 1]), float(p_ab[idx, 2])
            gr = rescale_grid_to_wdl(score_grid(tla[idx], tlb[idx], b['rho']), pb, pd_, pa)
            gb, gd, ga = wdl_from_grid(gr)
            max_reg_err = max(max_reg_err, abs(gb - pb), abs(gd - pd_), abs(ga - pa))
            assert abs(gr.sum() - 1.0) < 1e-12

        p_all.append(p_ab)
        y_all.append(tf.y3.to_numpy())
        last_bundle = dict(clf=clf, reg=reg, rho=b['rho'], blend_w=FIXED_BLEND_W, feats=FEATURE_COLS)
        last_va = va

    P = np.vstack(p_all)
    Y = np.concatenate(y_all)
    ll = log_loss(Y, P, labels=[0, 1, 2])
    rp = rps(P, Y)
    assert max_reg_err < 1e-9 and max_sym_err < 1e-9
    print(f"Rescaled Grid & Clf-Only PASSED: LL={ll:.5f}, RPS={rp:.5f}, max_region_err={max_reg_err:.2e}, max_sym_err={max_sym_err:.2e}")

    # Gate checks: identical model -> mean_gain == 0.0 -> rejected; better model vs uniform dummy -> promoted
    ok_same, m_same = gate(last_bundle, last_bundle, last_va)
    assert not ok_same and abs(m_same['mean_gain']) < 1e-12, m_same

    dummy = DummyClassifier(strategy='prior').fit(last_va[FEATURE_COLS], last_va.y3)
    weak_bundle = dict(clf=dummy, reg=None, rho=0.0, blend_w=0.0, feats=FEATURE_COLS)
    ok_better, m_better = gate(last_bundle, weak_bundle, last_va)
    assert ok_better and m_better['mean_gain'] > 0.05 and m_better['gain_p5'] > 0.0, m_better

    small_res = gated_retrain(hist.head(1000), FEATURE_COLS, last_bundle)
    assert small_res['status'] == 'skipped'
    print(f"Gate Unit Checks PASSED: identical={ok_same} (gain={m_same['mean_gain']:.2e}), better_vs_prior={ok_better} (gain={m_better['mean_gain']:+.4f}, p5={m_better['gain_p5']:+.4f}), <20k={small_res['status']}.")


if __name__ == '__main__':
    test_f11_independent_parity(100)
    test_rescaled_grid_and_gate()
