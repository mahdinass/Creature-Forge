"""P0.5 revision 2.2 amendment: exact, lightweight arithmetic (no data, no simulator, no Monte Carlo).

    python -I p05_amend22.py [--out p05_amend22_output.md]

Sections: P permutation-control degeneracy (exact combinatorics) | S stratum singletons | R representativeness and precision
of population options | Z Stage-0b sequential rollout requirements. Imports p05_design_calc for the precision and cost
formulas. Every number is [ASSUMP]-conditional arithmetic, not a property of Creature Forge.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from itertools import permutations

sys.modules["mujoco"] = None          # tripwire
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p05_design_calc as c  # noqa: E402

N_PERM = 20                           # permutations per control (revision 2 section 8.3 / 2.1 section 7.2)


# ============================================================================================== P. permutation degeneracy
def derangements(m: int) -> int:
    """Number of permutations of m items with no fixed point (!m)."""
    return round(math.factorial(m) * sum((-1) ** k / math.factorial(k) for k in range(m + 1)))


def perm_stats(m: int, n_groups: int, scheme: str) -> dict:
    """Exact properties of a within-group permutation control with groups of size m over n_groups training groups.
    scheme 'uniform': each group's permutation uniform over all m! (identity allowed);
    scheme 'derangement': uniform over the !m fixed-point-free permutations.
    moved = expected fraction of items reassigned to another item's row; P_identity_group = chance a group is untouched;
    distinct = number of distinct joint permutations; P_dup = chance two of N_PERM independent draws coincide."""
    if m < 1:
        raise ValueError(m)
    if scheme == "uniform":
        per = math.factorial(m)
        moved = (m - 1) / m if m > 1 else 0.0           # E[fixed points] = 1
        p_id = 1.0 / per
    elif scheme == "derangement":
        per = derangements(m)
        if per == 0:
            return {"m": m, "per_group": 0, "moved": 0.0, "P_identity_group": 1.0, "distinct": 1, "P_dup": 1.0,
                    "note": "no derangement exists: control cannot alter this group"}
        moved, p_id = 1.0, 0.0
    else:
        raise ValueError(scheme)
    distinct = per ** n_groups
    # birthday bound for N_PERM draws from `distinct` equally likely joint permutations
    p_dup = 1.0 - math.prod(1.0 - k / distinct for k in range(N_PERM)) if distinct >= N_PERM else 1.0
    return {"m": m, "per_group": per, "moved": moved, "P_identity_group": p_id, "distinct": distinct, "P_dup": p_dup}


def brute_perm_stats(m: int, scheme: str) -> dict:
    """Enumeration check of perm_stats for one group."""
    ps = [p for p in permutations(range(m)) if scheme == "uniform" or all(p[i] != i for i in range(m))]
    if not ps:
        return {"per_group": 0, "moved": 0.0}
    moved = sum(sum(p[i] != i for i in range(m)) for p in ps) / (len(ps) * m)
    return {"per_group": len(ps), "moved": moved}


# ============================================================================================== S. stratum singletons
def p_all_singletons(m: int, K: int) -> float:
    """Probability that m instances of one base fall in m distinct severity bins when bins are drawn uniformly from K
    (independently); 0 if m > K. Under a severity-BALANCED draw (distinct bins forced) the probability is 1 for m <= K."""
    if m > K:
        return 0.0
    return math.prod((K - i) / K for i in range(m))


def frac_groups_alterable(m: int, K: int, balanced: bool) -> float:
    """Expected fraction of bases whose (base, severity-bin) strata contain at least one stratum of size >= 2."""
    if balanced:
        return 0.0 if m <= K else 1.0
    return 1.0 - p_all_singletons(m, K)


# ============================================================================================== R. population options
GENERATORS = {"T1": {"hdb-v1": 18}, "T3": {"hdb-v1": 16}, "T2": {"walkrec-m1": 8, "hand": 4}}
OPTIONS = {
    # option: (population tiers, pilot description, pilot draw by generator, pilot source tiers)
    "P-A": (("T1",), "6 T3 bases (hdb-v1)", {"hdb-v1": 6}, ("T3",)),
    "P-B / T2 pilot": (("T1", "T3"), "6 T2 bases (2 hand + 4 walkrec)", {"hand": 2, "walkrec-m1": 4}, ("T2",)),
    "P-B / T1-panel pilot (recommended default)": (("T1", "T3"), "6 of the 12 T1-panel bases (hdb-v1)", {"hdb-v1": 6}, ("T1",)),
    "P-C / stratified pilot": (("T1", "T3", "T2"), "4 hdb-v1 + 1 walkrec + 1 hand from the population", {"hdb-v1": 4, "walkrec-m1": 1, "hand": 1}, ("T1", "T2")),
}


def composition(tiers) -> dict:
    out: dict = {}
    for t in tiers:
        for g, n in GENERATORS[t].items():
            out[g] = out.get(g, 0) + n
    return out


def option_row(name) -> dict:
    tiers, desc, pilot, src = OPTIONS[name]
    pop = composition(tiers)
    n_pop = sum(pop.values())
    in_pop = any(s in tiers for s in src)
    lost = sum(pilot.values()) if in_pop else 0
    G = n_pop - lost
    share = {g: pop[g] / n_pop for g in pop}
    pshare = {g: pilot.get(g, 0) / sum(pilot.values()) for g in set(pop) | set(pilot)}
    tv = 0.5 * sum(abs(share.get(g, 0) - pshare.get(g, 0)) for g in set(share) | set(pshare))
    return {"option": name, "population": pop, "n_pop": n_pop, "pilot": desc, "lost": lost, "G": G, "TV": tv}


# ============================================================================================== Z. Stage 0b
def stage0b_steps(cs: dict) -> list:
    """Sequential Stage-0b plan: (step, new repair executions, new prefixes, sentinel episodes). Arms: D (own prefix first),
    0 (no prefix), D' (another instance's prefix first). Arm-0 executions double as matrix cells."""
    return [
        ("1 sentinel reproduction (one stored A1e6 episode)", 0, 0, 1),
        ("2 one instance x 2 tools (dims 1 and 5) x 1 seed x arms {D, 0, D'}", 6, 2, 0),
        ("3 instrumentation neutrality: step-2 arm 0 rerun without hooks", 2, 0, 0),
        ("4 same instance, remaining 8 tools x 1 seed x 3 arms", 24, 0, 0),
        ("5 three instances x 10 tools x 2 seeds x 3 arms, minus steps 2-4", 150, 4, 0),
    ]


def stage0b_re(cs: dict) -> list:
    cell = cs["B_plant"] + c.verify_re(cs["p_pass"], cs["cache_original"])
    pre = c.prefix_re(cs)
    rows, cum = [], 0.0
    for name, ex, pf, se in stage0b_steps(cs):
        re_ = ex * cell + pf * pre + se * c.SENTINEL_RE
        cum += re_
        rows.append((name, ex, re_, cum))
    return rows


# ============================================================================================== report
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="p05_amend22_output.md")
    a = ap.parse_args(argv)
    L = ["# P0.5 rev. 2.2 amendment: exact arithmetic (NOT measured Creature Forge properties)", ""]
    L += ["## P. Within-group permutation controls (exact)", "",
          "| m_inst | scheme | perms per base | expected fraction of rows moved | P(base untouched) | distinct joint perms (G-1 = 27) | P(some of 20 draws coincide) |",
          "|---|---|---|---|---|---|---|"]
    for m in (1, 2, 3):
        for sch in ("uniform", "derangement"):
            r = perm_stats(m, 27, sch)
            L.append(f"| {m} | {sch} | {r['per_group']} | {r['moved']:.3f} | {r['P_identity_group']:.3f} | {r['distinct']:.3g} | {r['P_dup']:.3g} |")
    L += ["", "## S. (base, severity-bin) strata: fraction of bases where S-family-free can move anything", "",
          "| m_inst | K bins | uniform independent bins | severity-balanced draw (adversarial, valid) |", "|---|---|---|---|"]
    for m in (2, 3):
        for K in (2, 3):
            L.append(f"| {m} | {K} | {frac_groups_alterable(m, K, False):.3f} | {frac_groups_alterable(m, K, True):.3f} |")
    L += ["", "## R. Population options: generator composition, pilot representativeness and confirmatory bases", "",
          "TV = total-variation distance between pilot and population generator shares (0 = identical, 1 = disjoint).", "",
          "| option | population (by generator) | pilot | confirmatory bases lost | confirmatory G | TV(pilot, population) | MDE q=.30 rho=.3 infl=2.25, 2 / 3 per base | M_nmg same |",
          "|---|---|---|---|---|---|---|---|"]
    for name in OPTIONS:
        r = option_row(name)
        mdes = " / ".join(c.fmt(c.mde(0.30, r["G"], mi, 0.3, 2.25)) for mi in (2, 3))
        nmg = " / ".join(f"{c.equivalence_margin_demonstrable(0.30, r['G'], mi, 0.3, 2.25):.3f}" for mi in (2, 3))
        L.append(f"| {name} | {r['population']} | {r['pilot']} | {r['lost']} | {r['G']} | {r['TV']:.2f} | {mdes} | {nmg} |")
    L += ["", "## Z. Stage 0b sequential physics validation (NOT executed): rollout-equivalents per step", ""]
    for sn, cs in c.COST_SETS.items():
        L += [f"### cost set {sn} (B = {cs['B_plant']}, n_train = {cs['n_train']})", "",
              "| step | new repair executions | step RE | cumulative RE |", "|---|---|---|---|"]
        for name, ex, re_, cum in stage0b_re(cs):
            L.append(f"| {name} | {ex} | {re_:,.0f} | {cum:,.0f} |")
        L.append("")
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
