"""Poisson + Dixon-Coles scoreline grid, W/D/L from the grid, rho fit, RPS."""
from math import lgamma
import numpy as np

MAX_GOALS = 10
_LG = np.array([lgamma(i + 1) for i in range(MAX_GOALS + 1)])


def _pois_pmf(lam, n=MAX_GOALS):
    lam = max(float(lam), 0.05)
    k = np.arange(n + 1)
    return np.exp(k * np.log(lam) - lam - _LG[: n + 1])


def score_grid(lam_a, lam_b, rho=-0.08, max_goals=MAX_GOALS):
    """grid[i, j] = P(team A scores i, team B scores j). Rows = A goals."""
    la, lb = max(float(lam_a), 0.05), max(float(lam_b), 0.05)
    g = np.outer(_pois_pmf(la, max_goals), _pois_pmf(lb, max_goals))
    g[0, 0] *= 1.0 - la * lb * rho
    g[0, 1] *= 1.0 + la * rho
    g[1, 0] *= 1.0 + lb * rho
    g[1, 1] *= 1.0 - rho
    g = np.clip(g, 0.0, None)
    return g / g.sum()


def wdl_from_grid(g):
    """Return (P_B_win, P_draw, P_A_win) to match the repo's class order 0/1/2."""
    return float(np.triu(g, 1).sum()), float(np.trace(g)), float(np.tril(g, -1).sum())


def rescale_grid_to_wdl(g, p_b_win, p_draw, p_a_win):
    """Rescale each outcome region of Poisson/Dixon-Coles grid so region sums equal classifier W/D/L."""
    out = np.array(g, dtype=float, copy=True)
    n = out.shape[0]
    iu = np.triu_indices(n, 1)
    idg = np.diag_indices(n)
    il = np.tril_indices(n, -1)

    for idx, target in ((iu, p_b_win), (idg, p_draw), (il, p_a_win)):
        cur = float(out[idx].sum())
        if cur > 1e-12:
            out[idx] *= float(target) / cur
    tot = float(out.sum())
    return out / tot if tot > 0 else out


def fit_rho(lams_a, lams_b, goals_a, goals_b, grid=np.linspace(-0.25, 0.10, 36)):
    """Pick rho by scoreline log-likelihood on VALIDATION data only."""
    best_rho, best_ll = 0.0, -np.inf
    for rho in grid:
        ll = 0.0
        for la, lb, ga, gb in zip(lams_a, lams_b, goals_a, goals_b):
            gr = score_grid(la, lb, rho)
            ll += np.log(max(gr[min(int(ga), MAX_GOALS), min(int(gb), MAX_GOALS)], 1e-12))
        if ll > best_ll:
            best_rho, best_ll = float(rho), ll
    return best_rho


def rps(probs, y):
    """Ranked probability score. probs: (n,3) in order [B win, draw, A win]; y: 0/1/2."""
    probs = np.asarray(probs, float)
    onehot = np.eye(3)[np.asarray(y, int)]
    diff = np.cumsum(probs, axis=1)[:, :2] - np.cumsum(onehot, axis=1)[:, :2]
    return float(np.mean(np.sum(diff ** 2, axis=1) / 2.0))
