"""Walk-forward (expanding window, by football season) evaluation.

Expected input DataFrame (one row per match PER ORIENTATION, i.e. forward + mirrored):
  match_id, season, is_forward (1 = real home/away orientation, 0 = mirrored),
  y3 (0 = B win, 1 = draw, 2 = A win), goals_a, goals_b, + feature columns.
Optional: competition_id for per-competition group reporting.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import log_loss

from scoreline import score_grid, wdl_from_grid, fit_rho, rps

CLF_PARAMS = dict(
    max_iter=200, learning_rate=0.05, max_depth=4, l2_regularization=3.0,
    min_samples_leaf=100, random_state=42,
)
REG_PARAMS = dict(
    loss="poisson", max_iter=200, learning_rate=0.05, max_depth=4,
    l2_regularization=3.0, min_samples_leaf=100, random_state=42,
)

TOP5_COMPS = {"GB1", "ES1", "L1", "IT1", "FR1"}
UEFA_COMPS = {"CL", "EL", "UCOL", "USC", "CLQ", "ELQ", "ECLQ", "EURO"}
ASEAN_COMPS = {"IN1L", "MYS1", "THA1", "VIE1", "SIN1"}


def comp_group(cid):
    c = str(cid or "").strip()
    if c in TOP5_COMPS:
        return "Top-5"
    if c in UEFA_COMPS:
        return "UEFA"
    if c in ASEAN_COMPS:
        return "ASEAN"
    return "Others"


def sym_proba(clf, X_fwd, X_mir):
    """Average forward and mirrored predictions -> exact swap symmetry."""
    p_ab, p_ba = clf.predict_proba(X_fwd), clf.predict_proba(X_mir)
    return np.column_stack([
        (p_ab[:, 0] + p_ba[:, 2]) / 2.0,
        (p_ab[:, 1] + p_ba[:, 1]) / 2.0,
        (p_ab[:, 2] + p_ba[:, 0]) / 2.0,
    ])


def _split_pairs(df):
    f = df[df.is_forward == 1].sort_values("match_id")
    m = df[df.is_forward == 0].set_index("match_id").loc[f.match_id].reset_index()
    return f.reset_index(drop=True), m


def ece(p_true_class_conf, correct, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    idx = np.digitize(p_true_class_conf, edges[1:-1])
    out = 0.0
    for b in range(bins):
        sel = idx == b
        if sel.any():
            out += sel.mean() * abs(correct[sel].mean() - p_true_class_conf[sel].mean())
    return float(out)


def run_fold(df, feats, test_season, val_season, blend_grid=(0.0, 0.25, 0.5, 0.75, 1.0), test_override=None):
    train = df[df.season < val_season]
    val = df[df.season == val_season]
    test = df[df.season == test_season]

    clf = HistGradientBoostingClassifier(**CLF_PARAMS).fit(train[feats], train.y3)
    reg = HistGradientBoostingRegressor(**REG_PARAMS).fit(train[feats], train.goals_a)

    def lambdas(part):
        f, m = _split_pairs(part)
        return f, m, reg.predict(f[feats]), reg.predict(m[feats])

    vf, vm, vla, vlb = lambdas(val)
    rho = fit_rho(vla, vlb, vf.goals_a, vf.goals_b)
    p_clf_v = sym_proba(clf, vf[feats], vm[feats])
    p_grid_v = np.array([wdl_from_grid(score_grid(a, b, rho)) for a, b in zip(vla, vlb)])
    best_w = min(blend_grid, key=lambda w: log_loss(vf.y3, w * p_grid_v + (1 - w) * p_clf_v, labels=[0, 1, 2]))

    full = df[df.season < test_season]
    clf = HistGradientBoostingClassifier(**CLF_PARAMS).fit(full[feats], full.y3)
    reg = HistGradientBoostingRegressor(**REG_PARAMS).fit(full[feats], full.goals_a)

    if test_override:
        test = test.copy()
        for col, val_ov in test_override.items():
            test[col] = val_ov

    tf, tm, tla, tlb = lambdas(test)
    p_clf = sym_proba(clf, tf[feats], tm[feats])
    p_grid = np.array([wdl_from_grid(score_grid(a, b, rho)) for a, b in zip(tla, tlb)])
    p = best_w * p_grid + (1 - best_w) * p_clf

    prior = np.bincount(full[full.is_forward == 1].y3, minlength=3) / (full.is_forward == 1).sum()
    p_prior = np.tile(prior, (len(tf), 1))
    y = tf.y3.values
    conf = p.max(1)
    row = dict(
        test_season=test_season,
        n=len(tf),
        rho=rho,
        blend_w_grid=best_w,
        logloss=log_loss(y, p, labels=[0, 1, 2]),
        rps=rps(p, y),
        acc=float((p.argmax(1) == y).mean()),
        mean_p_draw=float(p[:, 1].mean()),
        actual_draw=float((y == 1).mean()),
        draw_gap=float(p[:, 1].mean() - (y == 1).mean()),
        mean_p_home=float(p[:, 2].mean()),
        actual_home=float((y == 2).mean()),
        home_gap=float(p[:, 2].mean() - (y == 2).mean()),
        mean_pred_goals=float((tla + tlb).mean()),
        actual_goals=float((tf.goals_a + tf.goals_b).mean()),
        goals_gap=float((tla + tlb).mean() - (tf.goals_a + tf.goals_b).mean()),
        ece=ece(conf, (p.argmax(1) == y).astype(float)),
        baseline_prior_logloss=log_loss(y, p_prior, labels=[0, 1, 2]),
        baseline_prior_rps=rps(p_prior, y),
    )

    grp_rows = []
    if "competition_id" in tf.columns:
        groups = tf["competition_id"].map(comp_group)
        for gname in ("Top-5", "UEFA", "ASEAN", "Others"):
            mask = (groups == gname).to_numpy()
            if not mask.any():
                continue
            pg, yg = p[mask], y[mask]
            g_pred = (tla[mask] + tlb[mask]).mean()
            g_act = (tf.goals_a.values[mask] + tf.goals_b.values[mask]).mean()
            grp_rows.append(dict(
                test_season=test_season, group=gname, n=int(mask.sum()),
                logloss=log_loss(yg, pg, labels=[0, 1, 2]), rps=rps(pg, yg),
                acc=float((pg.argmax(1) == yg).mean()),
                home_gap=float(pg[:, 2].mean() - (yg == 2).mean()),
                draw_gap=float(pg[:, 1].mean() - (yg == 1).mean()),
                goals_gap=float(g_pred - g_act),
                ece=ece(pg.max(1), (pg.argmax(1) == yg).astype(float)),
            ))
    return row, grp_rows


def summarize_folds(fold_df):
    cols = ["logloss", "rps", "acc", "ece", "home_gap", "draw_gap", "goals_gap"]
    plain = fold_df[cols].mean().to_dict()
    w = fold_df["n"].to_numpy(dtype=float)
    weighted = {c: float(np.average(fold_df[c].to_numpy(dtype=float), weights=w)) for c in cols}
    return plain, weighted


def walk_forward(df, feats, test_seasons, gap=1, test_override=None, return_groups=False):
    rows, grp_all = [], []
    for ts in test_seasons:
        r, gr = run_fold(df, feats, ts, ts - gap, test_override=test_override)
        rows.append(r)
        grp_all.extend(gr)
    fdf = pd.DataFrame(rows)
    if return_groups:
        return fdf, pd.DataFrame(grp_all)
    return fdf
