"""Foot contact estimation from MuJoCo normal force: hysteresis + minimum duration debouncing.

The same class runs online (inside the gait controller, one `update` per 200 Hz sample) and offline (metrics
replay recorded forces), so the controller and the evaluator can never disagree about what a touchdown is.
Two views are kept per foot:

* ``raw``  - force with hysteresis only (a single noisy sample cannot flip it, but brief chatter still counts);
             used to *measure* contact chatter.
* ``deb``  - raw state that has persisted for the minimum duration; used for stance/step decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

SAMPLE_DT = 0.005  # contact sampling period (matches simulate.LOG_EVERY * timestep)


@dataclass(frozen=True)
class ContactConfig:
    on_frac: float = 0.05    # loaded when normal force exceeds this fraction of body weight
    off_frac: float = 0.02   # unloaded when it falls below this fraction (hysteresis band)
    min_on_s: float = 0.02   # raw "loaded" must persist this long to confirm a touchdown
    min_off_s: float = 0.02  # raw "unloaded" must persist this long to confirm a liftoff

    def as_dict(self) -> dict:
        return asdict(self)


class FootContactEstimator:
    def __init__(self, weight_n: float, n_feet: int = 2, cfg: ContactConfig = ContactConfig()):
        self.cfg = cfg
        self.on_thr = cfg.on_frac * weight_n
        self.off_thr = cfg.off_frac * weight_n
        self.n = n_feet
        self.raw = [False] * n_feet
        self.raw_since = [0.0] * n_feet
        self.deb = [False] * n_feet
        self.raw_touchdowns = [0] * n_feet  # every raw unloaded->loaded transition (chatter measure)
        self.events: list[dict] = []        # confirmed events; `t` is the raw onset time (backdated)

    def update(self, t: float, forces) -> list[dict]:
        """Feed one sample of per-foot normal force (N). Returns events confirmed at this sample."""
        new: list[dict] = []
        for k in range(self.n):
            f = forces[k]
            if not self.raw[k] and f > self.on_thr:
                self.raw[k], self.raw_since[k] = True, t
                self.raw_touchdowns[k] += 1
            elif self.raw[k] and f < self.off_thr:
                self.raw[k], self.raw_since[k] = False, t
            if self.raw[k] != self.deb[k]:
                need = self.cfg.min_on_s if self.raw[k] else self.cfg.min_off_s
                if t - self.raw_since[k] >= need - 1e-9:
                    self.deb[k] = self.raw[k]
                    ev = {"foot": k, "kind": "touchdown" if self.deb[k] else "liftoff",
                          "t": self.raw_since[k], "t_confirm": t}
                    new.append(ev)
        self.events.extend(new)
        return new


def replay(times, forces, weight_n: float, cfg: ContactConfig = ContactConfig()):
    """Run the estimator over recorded samples. Returns (estimator, raw_state[n,2], deb_state[n,2])."""
    forces = np.asarray(forces, dtype=float)
    est = FootContactEstimator(weight_n, forces.shape[1], cfg)
    raw = np.zeros(forces.shape, dtype=bool)
    deb = np.zeros(forces.shape, dtype=bool)
    for i, t in enumerate(times):
        est.update(float(t), forces[i])
        raw[i] = est.raw
        deb[i] = est.deb
    return est, raw, deb
