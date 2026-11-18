"""Sequential Elo tracker. Call rating() BEFORE a match, update() AFTER it."""
from collections import defaultdict


class EloTracker:
    def __init__(self, k=20.0, home_adv=65.0, base=1500.0):
        self.k = k
        self.home_adv = home_adv
        self.base = base
        self.r = defaultdict(lambda: base)

    def rating(self, team):
        return self.r[team]

    def expected_home(self, home, away, neutral=False):
        ha = 0.0 if neutral else self.home_adv
        return 1.0 / (1.0 + 10.0 ** (-(self.r[home] + ha - self.r[away]) / 400.0))

    def update(self, home, away, hg, ag, neutral=False):
        exp_h = self.expected_home(home, away, neutral)
        score = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        gd = abs(hg - ag)
        mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11.0 + gd) / 8.0)
        delta = self.k * mult * (score - exp_h)
        self.r[home] += delta
        self.r[away] -= delta

    def season_regress(self, frac=0.25):
        """Call once at each season boundary: pull ratings toward the mean."""
        for t in list(self.r):
            self.r[t] = self.r[t] * (1.0 - frac) + self.base * frac
