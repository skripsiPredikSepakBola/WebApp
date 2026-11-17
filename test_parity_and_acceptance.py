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


def test_context_lookup_parity_and_mutation(n=100):
    """Independent plain-Python sequential rebuild vs real get_match_context() + mutation test."""
    from collections import defaultdict, deque
    import hashlib, json

    web_app._ensure_models()
    hist = pd.read_parquet(os.path.join(web_app.DATA_DIR, 'data', 'history_features.parquet'))
    hist_fwd = hist[hist['is_forward'] == 1].set_index('match_id')

    games_csv = os.path.abspath(os.path.join(web_app.DATA_DIR, '..', 'Football Data from Transfermarkt', 'games.csv'))
    games = pd.read_csv(
        games_csv,
        usecols=['game_id', 'season', 'competition_id', 'round', 'date',
                 'home_club_id', 'away_club_id', 'home_club_goals', 'away_club_goals'],
    )
    for col in ('game_id', 'season', 'home_club_id', 'away_club_id', 'home_club_goals', 'away_club_goals'):
        games[col] = pd.to_numeric(games[col], errors='coerce')
    games['date'] = pd.to_datetime(games['date'], errors='coerce')
    games = games.dropna().drop_duplicates('game_id', keep='last').sort_values(['date', 'game_id'], kind='mergesort')

    # Independent plain-Python trackers (do NOT import EloTracker, LeagueStats, or TeamState)
    elo_r = defaultdict(lambda: 1500.0)
    lg_n, lg_g, lg_h = defaultdict(int), defaultdict(float), defaultdict(float)
    tm_hist, tm_last = defaultdict(lambda: deque(maxlen=10)), {}
    neutral_comps = {'FIWC', 'EURO', 'COPA', 'AFAC', 'AFCN', 'KLUB'}
    final_comps = {'CL', 'EL', 'UCOL', 'USC', 'FAC', 'CDR', 'DFB', 'CIT', 'FRC', 'GBCS', 'SUC', 'DFL', 'FRCH', 'SCI'}

    target_ids = set(hist_fwd.tail(n).index.astype(int).tolist())
    prev_s = None
    orig_ts, orig_ls = web_app.TEAM_STATE, web_app.LEAGUE_STATE
    max_err = 0.0
    checked = 0
    mutation_caught = False

    try:
        for r in games.itertuples(index=False):
            if prev_s is not None and r.season != prev_s:
                for k in list(elo_r):
                    elo_r[k] = elo_r[k] * 0.75 + 1500.0 * 0.25
            prev_s = r.season
            gid, hid, aid = int(r.game_id), int(r.home_club_id), int(r.away_club_id)
            cid = str(r.competition_id or '').strip()
            rd = str(r.round or '').lower()
            neu = (cid in neutral_comps) or (cid in final_comps and 'final' in rd and 'semi' not in rd and 'quarter' not in rd)

            if gid in target_ids:
                eh, ea = elo_r[hid], elo_r[aid]
                hh, ha = tm_hist[hid], tm_hist[aid]
                gfh = (sum(x for x, _ in hh) + 4.05) / (len(hh) + 3.0)
                gah = (sum(y for _, y in hh) + 4.05) / (len(hh) + 3.0)
                gfa = (sum(x for x, _ in ha) + 4.05) / (len(ha) + 3.0)
                gaa = (sum(y for _, y in ha) + 4.05) / (len(ha) + 3.0)
                rh = float(max(1, min((r.date - tm_last[hid]).days, 14))) if hid in tm_last else 7.0
                ra = float(max(1, min((r.date - tm_last[aid]).days, 14))) if aid in tm_last else 7.0
                lgg = (lg_g[cid] + 200.0 * 2.7) / (lg_n[cid] + 200.0)
                lgh = (lg_h[cid] + 200.0 * 0.45) / (lg_n[cid] + 200.0)

                web_app.TEAM_STATE = {
                    'by_id': {
                        str(hid): {'elo': eh, 'gf10': gfh, 'ga10': gah},
                        str(aid): {'elo': ea, 'gf10': gfa, 'ga10': gaa},
                    },
                    'by_name': {},
                }
                web_app.LEAGUE_STATE = {cid: {'avg_goals': lgg, 'home_win': lgh, 'tier_known': True}}
                ctx = web_app.get_match_context('Home', 'Away', {
                    'home_club_id': hid, 'away_club_id': aid, 'league_id': cid,
                    'neutral': neu, 'home_rest': rh, 'away_rest': ra,
                })
                row = hist_fwd.loc[gid]
                diffs = [
                    abs(ctx['elo_a'] - row['own_elo']),
                    abs(ctx['elo_b'] - row['opp_elo']),
                    abs(ctx['gf_a'] - row['own_gf10']),
                    abs(ctx['ga_a'] - row['own_ga10']),
                    abs(ctx['gf_b'] - row['opp_gf10']),
                    abs(ctx['ga_b'] - row['opp_ga10']),
                    abs(ctx['league_avg_goals'] - row['league_avg_goals']),
                    abs(ctx['league_home_win_rate'] - row['league_home_win_rate']),
                    abs(ctx['league_tier_factor'] - row['league_tier_factor']),
                    abs((0.0 if ctx['neutral'] else 1.0) - row['home_flag']),
                ]
                max_err = max(max_err, *diffs)
                assert max(diffs) < 1e-9, f"Context parity mismatch at game_id={gid}: {diffs}"

                # Mutation test on first target match: shift Elo by +1.0 and assert parity FAILS
                if not mutation_caught:
                    web_app.TEAM_STATE['by_id'][str(hid)]['elo'] = eh + 1.0
                    mut_ctx = web_app.get_match_context('Home', 'Away', {
                        'home_club_id': hid, 'away_club_id': aid, 'league_id': cid,
                        'neutral': neu, 'home_rest': rh, 'away_rest': ra,
                    })
                    assert abs(mut_ctx['elo_a'] - row['own_elo']) >= 1.0 - 1e-9
                    mutation_caught = True
                checked += 1

            # Update independent trackers
            ha_adj = 0.0 if neu else 65.0
            exp_h = 1.0 / (1.0 + 10.0 ** (-(elo_r[hid] + ha_adj - elo_r[aid]) / 400.0))
            sc = 1.0 if r.home_club_goals > r.away_club_goals else (0.5 if r.home_club_goals == r.away_club_goals else 0.0)
            gd = abs(r.home_club_goals - r.away_club_goals)
            mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11.0 + gd) / 8.0)
            delta = 20.0 * mult * (sc - exp_h)
            elo_r[hid] += delta
            elo_r[aid] -= delta
            lg_n[cid] += 1
            lg_g[cid] += r.home_club_goals + r.away_club_goals
            lg_h[cid] += 1.0 if r.home_club_goals > r.away_club_goals else 0.0
            tm_hist[hid].append((r.home_club_goals, r.away_club_goals))
            tm_hist[aid].append((r.away_club_goals, r.home_club_goals))
            tm_last[hid] = r.date
            tm_last[aid] = r.date
    finally:
        web_app.TEAM_STATE, web_app.LEAGUE_STATE = orig_ts, orig_ls

    assert checked == n and mutation_caught
    print(f"F11 Independent Context Parity + Mutation PASSED ({checked} matches, max_diff={max_err:.2e}, mutation_caught=True).")


def test_idempotent_state_updater_and_freeze_hashes():
    import hashlib, json
    from update_states import apply_matches_idempotent

    ts0 = {'as_of': '2026-11-17', 'watermark': {'date': '2026-11-17', 'ids': []}, 'by_id': {}, 'by_name': {}}
    ls0 = {}
    batch = [
        {'match_id': 'm2', 'home_team': 'TeamA', 'away_team': 'TeamB', 'home_goals': 2, 'away_goals': 1, 'match_date': '2026-11-18', 'league': 'GB1'},
        {'match_id': 'm1', 'home_team': 'TeamA', 'away_team': 'TeamB', 'home_goals': 1, 'away_goals': 1, 'match_date': '2026-11-18', 'league': 'GB1'},
    ]
    ts1, ls1, c1 = apply_matches_idempotent(ts0, ls0, batch)
    ts2, ls2, c2 = apply_matches_idempotent(ts1, ls1, batch)
    assert c1 == 2 and c2 == 0 and ts1 == ts2 and ls1 == ls2
    print(f"State Updater Idempotency PASSED (first_run={c1}, second_run={c2}).")

    # Verify freeze SHA-256 hashes in models/model_meta.json
    meta_path = os.path.join(web_app.DATA_DIR, 'models', 'model_meta.json')
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    hashes = meta.get('freeze_sha256') or {}
    for rel, expected in hashes.items():
        if expected is None:
            continue
        p = os.path.join(web_app.DATA_DIR, rel)
        actual = hashlib.sha256(open(p, 'rb').read()).hexdigest()
        assert actual == expected, f"Freeze SHA-256 mismatch on {rel}: {actual} != {expected}"
    print(f"Freeze SHA-256 Integrity PASSED ({len(hashes)} artifacts verified).")


if __name__ == '__main__':
    test_f11_independent_parity(100)
    test_context_lookup_parity_and_mutation(100)
    test_idempotent_state_updater_and_freeze_hashes()
    test_rescaled_grid_and_gate()
