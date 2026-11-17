"""F11 Train/Serve Parity (100 matches) + Section 11 Acceptance Checks."""
import os
import tempfile
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss

import app as web_app
from features import FEATURE_COLS, build_feature_row, mirror
from scoreline import score_grid, wdl_from_grid, fit_rho, rps
from retrain_gate import CLF_PARAMS, REG_PARAMS, FIXED_BLEND_W, sym_proba, _split_pairs, fit_bundle, gate, retrain as gated_retrain
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor


def test_f11_parity(n=100):
    web_app._ensure_models()
    hist = pd.read_parquet(os.path.join(web_app.DATA_DIR, 'data', 'history_features.parquet'))
    sample = hist[hist['is_forward'] == 1].tail(n).reset_index(drop=True)
    max_diff = 0.0
    for row in sample.itertuples(index=False):
        stats_a = {
            'starter_overall_mean': row.own_att + row.diff_overall_mean,  # exact inverse check via direct fields:
        }
        # Reconstruct exact inputs from row and verify build_feature_row == build_bundle_feature_pair
        sa = {
            'starter_overall_mean': row.diff_overall_mean + 70.0,
            'sub_overall_mean': row.diff_sub_mean + 65.0,
            'starter_market_val_sum': np.expm1(row.diff_market_val_log + 10.0),
            'overall_mean_ATT': row.own_att,
            'overall_mean_DEF': row.own_def,
            'overall_mean_GK': row.own_gk,
        }
        sb = {
            'starter_overall_mean': 70.0,
            'sub_overall_mean': 65.0,
            'starter_market_val_sum': np.expm1(10.0),
            'overall_mean_ATT': row.opp_att,
            'overall_mean_DEF': row.opp_def,
            'overall_mean_GK': row.opp_gk,
        }
        ctx = {
            'neutral': row.home_flag == 0.0,
            'elo_a': row.own_elo, 'elo_b': row.opp_elo,
            'gf_a': row.own_gf10, 'ga_a': row.own_ga10, 'rest_a': row.own_rest,
            'gf_b': row.opp_gf10, 'ga_b': row.opp_ga10, 'rest_b': row.opp_rest,
            'league_avg_goals': row.league_avg_goals,
            'league_home_win_rate': row.league_home_win_rate,
            'league_tier_factor': row.league_tier_factor,
            'elo_missing': False, 'tier_missing': False,
        }
        # Patch cohesion_proxy for parity check of exact shared builder
        orig_coh = web_app.cohesion_proxy
        web_app.cohesion_proxy = lambda st: row.diff_cohesion if st is sa else 0.0
        try:
            f_ab, f_ba, _ = web_app.build_bundle_feature_pair('TeamA', 'TeamB', sa, sb, sa, sb, {}, ctx=ctx)
        finally:
            web_app.cohesion_proxy = orig_coh

        # Also override diff_form_gd_5 input to match exact row.diff_form_gd_5
        f_train = build_feature_row(
            sa, sb, row.diff_cohesion, 0.0,
            row.own_elo, row.opp_elo,
            row.own_gf10, row.own_ga10, row.own_rest,
            row.opp_gf10, row.opp_ga10, row.opp_rest,
            (row.own_gf10 - row.own_ga10) - (row.opp_gf10 - row.opp_ga10),
            row.league_avg_goals, row.league_home_win_rate, row.league_tier_factor,
            neutral=(row.home_flag == 0.0),
        )
        for c in FEATURE_COLS:
            max_diff = max(max_diff, abs(f_ab[c] - f_train[c]))
            assert abs(f_ab[c] - f_train[c]) < 1e-9, f"Parity mismatch on {c}: {f_ab[c]} vs {f_train[c]}"
        # Check mirror round-trip
        assert mirror(f_ba) == f_ab
    print(f"F11 Train/Serve Parity PASSED across {n} matches (max_diff={max_diff:.2e} < 1e-9).")


def test_section11():
    web_app._ensure_models()
    assert web_app.USE_BUNDLE is False, "USE_BUNDLE must default to False in PR!"
    hist = pd.read_parquet(os.path.join(web_app.DATA_DIR, 'data', 'history_features.parquet'))

    # 1. Grid sums & swap symmetry
    g = score_grid(1.78, 1.42, -0.02)
    assert abs(g.sum() - 1.0) < 1e-12
    assert abs(sum(wdl_from_grid(g)) - 1.0) < 1e-12

    # Evaluate frozen G6+tier StrongReg w=0.25 on 2023-2026 for per-league calibration & symmetry
    p_all, y_all, cid_all, la_all, lb_all, ga_all, gb_all = [], [], [], [], [], [], []
    max_sym_err = 0.0
    last_bundle = None
    for ts in (2023, 2024, 2025, 2026):
        tr = hist[hist.season < ts - 1]
        va = hist[hist.season == ts - 1]
        te = hist[hist.season == ts]
        b = fit_bundle(tr, va, FEATURE_COLS)
        # Refit on train+val with rho from tune
        full = hist[hist.season < ts]
        clf = HistGradientBoostingClassifier(**CLF_PARAMS).fit(full[FEATURE_COLS], full.y3)
        reg = HistGradientBoostingRegressor(**REG_PARAMS).fit(full[FEATURE_COLS], full.goals_a)
        tf, tm = _split_pairs(te)
        tla, tlb = reg.predict(tf[FEATURE_COLS]), reg.predict(tm[FEATURE_COLS])
        p_ab = sym_proba(clf, tf[FEATURE_COLS], tm[FEATURE_COLS])
        p_ba = sym_proba(clf, tm[FEATURE_COLS], tf[FEATURE_COLS])
        max_sym_err = max(max_sym_err, float(np.max(np.abs(p_ab[:, 2] - p_ba[:, 0]))))

        p_g = np.array([wdl_from_grid(score_grid(a, c, b['rho'])) for a, c in zip(tla, tlb)])
        p = FIXED_BLEND_W * p_g + (1.0 - FIXED_BLEND_W) * p_ab
        p_all.append(p)
        y_all.append(tf.y3.to_numpy())
        cid_all.append(tf.competition_id.to_numpy())
        la_all.append(tla); lb_all.append(tlb)
        ga_all.append(tf.goals_a.to_numpy()); gb_all.append(tf.goals_b.to_numpy())
        last_bundle = dict(clf=clf, reg=reg, rho=b['rho'], blend_w=FIXED_BLEND_W, feats=FEATURE_COLS)

    assert max_sym_err < 1e-9, f"Swap symmetry error {max_sym_err}"
    print(f"Section 11 Grid Sums & Swap Symmetry PASSED (max_sym_err={max_sym_err:.2e} < 1e-9).")

    # 2. Per-league calibration table
    P = np.vstack(p_all)
    Y = np.concatenate(y_all)
    CID = np.concatenate(cid_all)
    LA, LB = np.concatenate(la_all), np.concatenate(lb_all)
    GA, GB = np.concatenate(ga_all), np.concatenate(gb_all)

    print("\n=== SECTION 11 PER-LEAGUE CALIBRATION (2023-2026) ===")
    buckets = [
        ('GB1 (Premier League)', CID == 'GB1'),
        ('ES1 (LaLiga)', CID == 'ES1'),
        ('L1  (Bundesliga)', CID == 'L1'),
        ('IT1 (Serie A)', CID == 'IT1'),
        ('FR1 (Ligue 1)', CID == 'FR1'),
        ('NL1 (Eredivisie)', CID == 'NL1'),
        ('PO1 (Liga Portugal)', CID == 'PO1'),
        ('TR1 (Super Lig)', CID == 'TR1'),
        ('UEFA (CL/EL/UCOL/Q)', np.isin(CID, ['CL', 'EL', 'UCOL', 'CLQ', 'ELQ', 'ECLQ', 'USC'])),
        ('ASEAN (5 leagues)', np.isin(CID, ['IN1L', 'MYS1', 'THA1', 'VIE1', 'SIN1'])),
        ('ALL TEST', np.ones(len(Y), dtype=bool)),
    ]
    for label, mask in buckets:
        n_b = int(mask.sum())
        if not n_b:
            continue
        pb, yb = P[mask], Y[mask]
        ll = log_loss(yb, pb, labels=[0, 1, 2])
        rp = rps(pb, yb)
        hg = float(pb[:, 2].mean() - (yb == 2).mean())
        dg = float(pb[:, 1].mean() - (yb == 1).mean())
        gg = float((LA[mask] + LB[mask]).mean() - (GA[mask] + GB[mask]).mean())
        print(f"  {label:22s} n={n_b:5d} | LL={ll:.4f} RPS={rp:.4f} | home_gap={hg:+.4f} draw_gap={dg:+.4f} goals_gap={gg:+.4f}")

    # 3. Retrain gate unit checks (no overwrite of real models/)
    small_res = gated_retrain(hist.head(1000), FEATURE_COLS, last_bundle)
    assert small_res['status'] == 'skipped', small_res
    same_res = gated_retrain(hist, FEATURE_COLS, last_bundle)
    assert same_res['status'] == 'rejected', same_res
    print(f"Section 11 Retrain Gate PASSED: <20k={small_res['status']}, identical={same_res['status']} (mean_gain={same_res['mean_gain']:+.5f}).")


if __name__ == '__main__':
    test_f11_parity(100)
    test_section11()
