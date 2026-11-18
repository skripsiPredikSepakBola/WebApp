"""Single source of truth for frozen G6+tier (25 features).

Used identically by offline training, retrain.py, and app.py.
"""
from collections import defaultdict, deque
import math

NEUTRAL_COMPS = {"FIWC", "EURO", "COPA", "AFAC", "AFCN", "KLUB"}
SINGLE_LEG_FINAL_COMPS = {"CL", "EL", "UCOL", "USC", "FAC", "CDR", "DFB", "CIT", "FRC", "GBCS", "SUC", "DFL", "FRCH", "SCI"}


def is_neutral_match(competition_id, round_str=""):
    c = str(competition_id or "").strip()
    if c in NEUTRAL_COMPS:
        return True
    r = str(round_str or "").lower()
    if c in SINGLE_LEG_FINAL_COMPS and "final" in r and "semi" not in r and "quarter" not in r:
        return True
    return False


ANTISYMMETRIC = [
    "diff_overall_mean", "diff_sub_mean", "diff_market_val_log",
    "diff_form_gd_5", "diff_cohesion", "diff_elo", "home_flag",
]
SYMMETRIC = ["sum_elo", "league_avg_goals", "league_home_win_rate", "league_tier_factor"]
SWAP_PAIRS = [
    ("own_att", "opp_att"), ("own_def", "opp_def"), ("own_gk", "opp_gk"),
    ("own_elo", "opp_elo"), ("own_gf10", "opp_gf10"), ("own_ga10", "opp_ga10"),
    ("own_rest", "opp_rest"),
]

FEATURE_COLS = ANTISYMMETRIC + SYMMETRIC + [c for pair in SWAP_PAIRS for c in pair]


def mirror(f):
    """Features of the same match seen from the other team's side. mirror(mirror(f)) == f."""
    m = {k: -f[k] for k in ANTISYMMETRIC}
    for k in SYMMETRIC:
        m[k] = f[k]
    for own, opp in SWAP_PAIRS:
        m[own], m[opp] = f[opp], f[own]
    return m


def build_feature_row(
    stats_a, stats_b,
    cohesion_a, cohesion_b,
    elo_a, elo_b,
    gf_a, ga_a, rest_a,
    gf_b, ga_b, rest_b,
    form_gd_diff,
    league_avg_goals, league_home_win_rate, league_tier_factor,
    neutral=False,
):
    """Shared 25-feature dictionary constructor for training, retrain.py, and app.py."""
    return {
        "diff_overall_mean": float(stats_a["starter_overall_mean"] - stats_b["starter_overall_mean"]),
        "diff_sub_mean": float(stats_a["sub_overall_mean"] - stats_b["sub_overall_mean"]),
        "diff_market_val_log": float(math.log1p(stats_a["starter_market_val_sum"]) - math.log1p(stats_b["starter_market_val_sum"])),
        "diff_form_gd_5": float(form_gd_diff),
        "diff_cohesion": float(cohesion_a - cohesion_b),
        "diff_elo": float(elo_a - elo_b),
        "home_flag": 0.0 if neutral else 1.0,
        "sum_elo": float(elo_a + elo_b),
        "league_avg_goals": float(league_avg_goals),
        "league_home_win_rate": float(league_home_win_rate),
        "league_tier_factor": float(league_tier_factor),
        "own_att": float(stats_a["overall_mean_ATT"]),
        "opp_att": float(stats_b["overall_mean_ATT"]),
        "own_def": float(stats_a["overall_mean_DEF"]),
        "opp_def": float(stats_b["overall_mean_DEF"]),
        "own_gk": float(stats_a["overall_mean_GK"]),
        "opp_gk": float(stats_b["overall_mean_GK"]),
        "own_elo": float(elo_a),
        "opp_elo": float(elo_b),
        "own_gf10": float(gf_a),
        "opp_gf10": float(gf_b),
        "own_ga10": float(ga_a),
        "opp_ga10": float(ga_b),
        "own_rest": float(rest_a),
        "opp_rest": float(rest_b),
    }


class LeagueStats:
    """Expanding, shrunk league goal rate and home-win rate. get() BEFORE a match, update() AFTER."""
    def __init__(self, k=200, prior_goals=2.7, prior_home=0.45):
        self.k, self.pg, self.ph = k, prior_goals, prior_home
        self.n = defaultdict(int)
        self.goals = defaultdict(float)
        self.home = defaultdict(float)

    def get(self, league):
        n = self.n[league]
        return (
            (self.goals[league] + self.k * self.pg) / (n + self.k),
            (self.home[league] + self.k * self.ph) / (n + self.k),
        )

    def update(self, league, hg, ag):
        self.n[league] += 1
        self.goals[league] += hg + ag
        self.home[league] += 1.0 if hg > ag else 0.0


class TeamState:
    """Rolling goals for/against (last 10, shrunk to 1.35) and rest days. get() before, update() after."""
    def __init__(self, window=10, prior=1.35, k=3):
        self.w, self.prior, self.k = window, prior, k
        self.hist = defaultdict(lambda: deque(maxlen=window))
        self.last = {}

    def get(self, team, date=None):
        h = self.hist[team]
        gf = (sum(x for x, _ in h) + self.k * self.prior) / (len(h) + self.k)
        ga = (sum(y for _, y in h) + self.k * self.prior) / (len(h) + self.k)
        rest = 7.0
        if date is not None and team in self.last:
            rest = float(max(1, min((date - self.last[team]).days, 14)))
        return gf, ga, rest

    def update(self, team, gf, ga, date=None):
        self.hist[team].append((gf, ga))
        if date is not None:
            self.last[team] = date
