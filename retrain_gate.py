"""Safe model promotion gate (Patch D).

Input `df`: history + live rows, forward AND mirrored rows, columns:
  match_id, date (sortable), is_forward, y3, goals_a, goals_b, + FEATURE_COLS
"""
import json
import os
import platform
import shutil
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import log_loss

from scoreline import fit_rho, rps, score_grid, wdl_from_grid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(BASE_DIR, "models"))
BUNDLE_PATH = os.path.join(MODEL_DIR, "model_bundle.joblib")
META_PATH = os.path.join(MODEL_DIR, "model_meta.json")

CLF_PARAMS = dict(
    max_iter=200, learning_rate=0.05, max_depth=4,
    l2_regularization=6.0, min_samples_leaf=250, random_state=42,
)
REG_PARAMS = dict(
    loss="poisson", max_iter=200, learning_rate=0.05, max_depth=4,
    l2_regularization=6.0, min_samples_leaf=250, random_state=42,
)
FIXED_BLEND_W = 0.25

MIN_TRAIN_MATCHES = 20_000
MIN_VAL_MATCHES = 300
MIN_IMPROVEMENT = 0.002
CALIB_TOL = 0.03


def sym_proba(clf, X_fwd, X_mir):
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


def match_split(df, tune_frac=0.10, val_frac=0.10):
    """Chronological split BY MATCH so a forward row and its mirror never straddle a boundary."""
    ids = df.drop_duplicates("match_id").sort_values(["date", "match_id"]).match_id.to_numpy()
    n = len(ids)
    a, b = int(n * (1.0 - tune_frac - val_frac)), int(n * (1.0 - val_frac))
    pick = lambda s: df[df.match_id.isin(set(s))]
    return pick(ids[:a]), pick(ids[a:b]), pick(ids[b:])


def fit_bundle(train, tune, feats):
    clf = HistGradientBoostingClassifier(**CLF_PARAMS).fit(train[feats], train.y3)
    reg = HistGradientBoostingRegressor(**REG_PARAMS).fit(train[feats], train.goals_a)
    tf, tm = _split_pairs(tune)
    la, lb = reg.predict(tf[feats]), reg.predict(tm[feats])
    rho = fit_rho(la, lb, tf.goals_a, tf.goals_b)
    return dict(clf=clf, reg=reg, rho=rho, blend_w=FIXED_BLEND_W, feats=list(feats))


def bundle_proba(b, f, m):
    p_clf = sym_proba(b["clf"], f[b["feats"]], m[b["feats"]])
    if b.get("reg") is None:
        return p_clf
    la, lb = b["reg"].predict(f[b["feats"]]), b["reg"].predict(m[b["feats"]])
    p_grid = np.array([wdl_from_grid(score_grid(a, c, b["rho"])) for a, c in zip(la, lb)])
    return b["blend_w"] * p_grid + (1.0 - b["blend_w"]) * p_clf


def gate(candidate, current, val, seed=0):
    vf, vm = _split_pairs(val)
    y = vf.y3.to_numpy()
    p_new, p_old = bundle_proba(candidate, vf, vm), bundle_proba(current, vf, vm)
    loss = lambda p: -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1.0))
    d = loss(p_old) - loss(p_new)
    rng = np.random.default_rng(seed)
    boot = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(1000)]
    m = dict(
        n_val_matches=int(len(y)),
        old_logloss=float(loss(p_old).mean()),
        new_logloss=float(loss(p_new).mean()),
        mean_gain=float(d.mean()),
        gain_p5=float(np.percentile(boot, 5)),
        old_rps=rps(p_old, y),
        new_rps=rps(p_new, y),
        home_gap=float(abs(p_new[:, 2].mean() - (y == 2).mean())),
        draw_gap=float(abs(p_new[:, 1].mean() - (y == 1).mean())),
    )
    ok = (
        m["n_val_matches"] >= MIN_VAL_MATCHES
        and m["mean_gain"] >= MIN_IMPROVEMENT
        and m["gain_p5"] > 0.0
        and m["new_rps"] <= m["old_rps"]
        and m["home_gap"] <= CALIB_TOL
        and m["draw_gap"] <= CALIB_TOL
    )
    return ok, m


def promote(candidate_refit, metrics, train_range):
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(BUNDLE_PATH):
        arch = os.path.join(MODEL_DIR, "archive", time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(arch, exist_ok=True)
        shutil.copy2(BUNDLE_PATH, arch)
        if os.path.exists(META_PATH):
            shutil.copy2(META_PATH, arch)
    joblib.dump(candidate_refit, BUNDLE_PATH)
    meta = dict(
        sklearn_version=sklearn.__version__,
        numpy_version=np.__version__,
        python_version=platform.python_version(),
        features=candidate_refit["feats"],
        clf_params=CLF_PARAMS,
        reg_params=REG_PARAMS,
        rho=candidate_refit["rho"],
        rho_procedure="grid_search(-0.25..0.10, 36 pts) on chronological tune slice",
        blend_w=candidate_refit["blend_w"],
        train_range=train_range,
        gate_metrics=metrics,
        trained_at=time.time(),
    )
    with open(META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


def retrain(df, feats, current):
    n_matches = df.match_id.nunique()
    if n_matches < MIN_TRAIN_MATCHES:
        return {"status": "skipped", "reason": f"need >= {MIN_TRAIN_MATCHES} matches, have {n_matches}"}
    train, tune, val = match_split(df)
    cand = fit_bundle(train, tune, feats)
    ok, m = gate(cand, current, val)
    if not ok:
        return {"status": "rejected", **m}
    final = fit_bundle(pd.concat([train, tune, val]), tune, feats)
    promote(final, m, [str(df.date.min()), str(df.date.max())])
    return {"status": "promoted", **m}
