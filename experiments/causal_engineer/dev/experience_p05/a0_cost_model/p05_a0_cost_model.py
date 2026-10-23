"""P0.5 A0 cost and precision model for the owner-selected planning settings (2026-10-23). Read-only arithmetic.

Settings: D2 P-B (hdb-v1), 28 confirmatory bases; D7' pilot 4 T1-panel + 2 T3 bases; D3 B = 300 plant rollouts, 8 train
seeds; D5 three instances per base, two severity bins; D1 minimum meaningful effect 0.10.
Reuses the archived formulas in ../design_archive/p05_design_calc.py (no physics, no data, no Monte Carlo).

    python -I p05_a0_cost_model.py [--out p05_a0_cost_model_output.md]

Every number is [ASSUMP]-conditional arithmetic, NOT a measured property of Creature Forge, and no costed work is run.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.modules["mujoco"] = None          # tripwire
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "design_archive"))
import p05_design_calc as c  # noqa: E402

D1 = 0.10
G_CONF, M_INST, G_PILOT = 28, 3, 6
REP_FRAC = 0.25                        # revision 2 section 2.5: 25 % of instances get R = 2 for every tool
N_SENTINEL = 3
SET = dict(c.COST_SETS["mid"], B_plant=300, n_train=8)      # D3; other mid inputs are [ASSUMP]
PRICE_SETS = {                         # all [ASSUMP]; $0.269/h and 31,200 RE/h are historical ledger/W3 values, unverified now
    "old recorded rate ($0.269/VM-h, 31.2k RE/h)": {"price_h": 0.269, "throughput_h": 31_200, "idle_frac": 0.20, "overhead_h": 0.5, "sessions": 3},
    "pessimistic ($0.60/VM-h, 15.6k RE/h)": {"price_h": 0.60, "throughput_h": 15_600, "idle_frac": 0.35, "overhead_h": 1.0, "sessions": 5},
}
CAP_REMAINING = 96.0 - 89.405          # [HIST] existing infrastructure cap minus ledger; governs until the owner changes it
VM_CREDIT_REPORTED = 40.04             # [owner-reported 2026-10-23, unverified; not an authorisation]
TOKEN_FACTORY_REPORTED = 47.00         # [owner-reported 2026-10-23, unverified; separate pool; P0.5 uses no inference]


def power_at(delta, q, G, m, rho, infl, alpha=0.05):
    """Approximate power of the one-sided level-alpha t test (G-1 df) for a paired-difference mean delta."""
    se = math.sqrt(c.var_mean_diff(q, delta, G, m, rho, infl))
    return c.t_cdf(delta / se - c.t_ppf(1 - alpha, G - 1), G - 1)


def campaign_design(m_inst=M_INST, G=G_CONF):
    n = G * m_inst
    n_rep = round(REP_FRAC * n)
    return dict(n_inst=n, tools=10, R=1 + n_rep / n, aug_per_inst=2, n_confirm_cells=2 * n_rep, n_sentinel=N_SENTINEL)


def pilot_design(m_inst):
    n = G_PILOT * m_inst
    return dict(n_inst=n, tools=10, R=2, aug_per_inst=2, n_confirm_cells=2 * n, n_sentinel=N_SENTINEL)


def dollars(re_, p):
    hours = re_ / p["throughput_h"] * (1 + p["idle_frac"]) + p["sessions"] * p["overhead_h"]
    return hours, hours * p["price_h"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "p05_a0_cost_model_output.md"))
    a = ap.parse_args(argv)
    c.check_all_tools_feasible(SET)
    L = ["# P0.5 A0 cost and precision model (B = 300, 8 train seeds, 3 instances per base; NOT executed; [ASSUMP])", ""]
    L += ["## 1. Units", "",
          f"- Independent confirmatory bases G = {G_CONF} (the unit of inference); instances = {G_CONF * M_INST} "
          f"(3 per base, NOT independent); pilot bases = {G_PILOT} (excluded from confirmatory analysis).",
          f"- Budget-feasible tools at B = 300 / 336 / 340 with 8 train seeds: {len(c.budget_feasible(300, 8))} / "
          f"{len(c.budget_feasible(336, 8))} / {len(c.budget_feasible(340, 8))} (bounds feasibility per robot is UNKNOWN until the E-check).",
          f"- Verification per cell: {c.verify_re(SET['p_pass'], SET['cache_original']):.1f} RE (p_pass = {SET['p_pass']} [ASSUMP], original not cached); "
          f"cell = B + verification = {SET['B_plant'] + c.verify_re(SET['p_pass'], SET['cache_original']):.1f} RE; prefix = {c.prefix_re(SET):.0f} RE.", ""]
    L += ["## 2. Rollout-equivalents (RE) by stage", "",
          "RE: one 10 s plant or twin rollout = 1; one 20 s confirmation rollout = 2.", "",
          "| stage | count | RE |", "|---|---|---|"]
    rows = []
    from p05_amend22 import stage0b_re  # noqa: E402  (archived; same formulas)
    s0b = stage0b_re(SET)[-1][3]
    rows.append(("Stage 0b (local physics, $0 cloud; 182 repair executions + sentinel)", "182 executions", s0b))
    for nb in (16, 34):
        rows.append((f"Stage E for {nb} bases (16 = all T3; 34 = every P-B base) [UNKNOWN which are needed]", f"{nb} bases",
                     c.stage_e_re(nb, 39)))
    for mi in (2, 3):
        p = c.design_re(SET, **pilot_design(mi))
        rows.append((f"Pilot: 6 bases x {mi} instances, full matrix R = 2, phase-2 + selector cells, 3 sentinels",
                     f"{6 * mi * 10 * 2} matrix cells", p["total"]))
    cp = c.design_re(SET, **campaign_design())
    d = campaign_design()
    rows.append((f"Campaign: 28 bases x 3 instances, full matrix, {int(REP_FRAC * 100)} % R = 2, 2 cost-matched + selector cells",
                 f"{round(d['n_inst'] * d['R'] * 10)} matrix + {2 * d['n_inst']} cost-matched + {d['n_confirm_cells']} selector cells",
                 cp["total"]))
    for name, units, re_ in rows:
        L.append(f"| {name} | {units} | {re_:,.0f} |")
    L += ["", "## 3. VM hours and USD per stage (prices and throughput UNVERIFIED; local stages cost $0 cloud)", "",
          "VM hours = RE / throughput x (1 + idle fraction) + sessions x overhead per session (each stage pays its own "
          "session overhead) [ASSUMP].", "",
          "| stage | " + " | ".join(f"{k}: VM-hours / USD" for k in PRICE_SETS) + " |", "|---|" + "---|" * len(PRICE_SETS)]
    usd = {}
    for name, _, re_ in rows:
        if name.startswith("Stage 0b"):
            L.append(f"| {name} | local, $0 | local, $0 |")
            continue
        vals = [dollars(re_, p) for p in PRICE_SETS.values()]
        usd[name] = [v[1] for v in vals]
        L.append(f"| {name} | " + " | ".join(f"{h:.1f} VM-h / ${d:.2f}" for h, d in vals) + " |")
    names = list(usd)
    e16, e34, p2, p3, camp = names
    L += ["", "## 4. Programme totals (Stage E + pilot + campaign; Stage 0b is local) and funding constraints", "",
          "| scenario | " + " | ".join(f"{k}: USD" for k in PRICE_SETS) + " |", "|---|" + "---|" * len(PRICE_SETS)]
    for label, parts in (("low: Stage E 16 bases + pilot 6 x 2 + campaign", (e16, p2, camp)),
                         ("high: Stage E 34 bases + pilot 6 x 3 + campaign", (e34, p3, camp))):
        L.append(f"| {label} | " + " | ".join(f"${sum(usd[n][i] for n in parts):.2f}" for i in range(len(PRICE_SETS))) + " |")
    L += ["", "| funding item | USD | status |", "|---|---|---|",
          f"| existing infrastructure spending cap remaining | {CAP_REMAINING:.3f} | [HIST] $96 cap minus $89.405 ledger; binding until the owner decides A10 |",
          f"| Nebius AI Cloud VM credit | {VM_CREDIT_REPORTED:.2f} | owner-reported 2026-10-23, unverified; a balance, NOT an authorisation |",
          f"| Nebius Token Factory credit | {TOKEN_FACTORY_REPORTED:.2f} | owner-reported, unverified; separate pool, not usable for VMs; P0.5 needs none |", ""]
    L += ["## 5. Statistical precision at G = 28 (t-based, one-sided 0.05, power 0.80) versus D1 = 0.10", "",
          "| m_inst | q | rho | infl | MDE | M_nmg (no meaningful gain shown at M) | power to detect delta = 0.10 |",
          "|---|---|---|---|---|---|---|"]
    for mi in (2, 3):
        for q in (0.15, 0.30, 0.42, 0.50, 0.60, 1.0):
            for rho in (0.1, 0.3):
                for infl in (1.0, 2.25, 2.7):
                    pw = power_at(D1, q, G_CONF, mi, rho, infl) if D1 <= q else float("nan")
                    L.append(f"| {mi} | {q} | {rho} | {infl} | {c.fmt(c.mde(q, G_CONF, mi, rho, infl))} | "
                             f"{c.equivalence_margin_demonstrable(q, G_CONF, mi, rho, infl):.3f} | {pw:.2f} |")
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
