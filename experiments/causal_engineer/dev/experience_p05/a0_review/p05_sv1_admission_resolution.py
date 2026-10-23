"""P0.5 A0 review: Monte Carlo decision uncertainty of the P05-SV1 admission rule (exact binomial; nothing is simulated).

Rule (amendment 2.2 section 4.2, renamed by erratum E5): an interval method is admissible only if, in EVERY P05-SV1 cell at
the planned G, its estimated coverage k/S >= 0.85 AND the lower end of the Wilson 90 % interval for k/S >= 0.75.
With S datasets per cell, k ~ Binomial(S, c) for a method whose true coverage is c, independently across cells.

    python -I p05_sv1_admission_resolution.py [--out p05_sv1_admission_resolution_output.md]
"""
from __future__ import annotations

import argparse
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
Z = {"two-sided 90 % (z = 1.645, as in revision 2 Wilson tables)": 1.6448536269514722,
     "one-sided 90 % (z = 1.282)": 1.2815515655446004}


def wilson_lower(k: int, n: int, z: float) -> float:
    if n == 0:
        return 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half


def k_min(S: int, z: float, point: float = 0.85, lower: float = 0.75) -> int | None:
    for k in range(S + 1):
        if k / S >= point - 1e-12 and wilson_lower(k, S, z) >= lower - 1e-12:
            return k
    return None


def binom_sf(k: int, n: int, p: float) -> float:
    """P(Binomial(n, p) >= k), exact."""
    return sum(math.comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k, n + 1))


def p_admit(c: float, S: int, z: float, cells: int) -> float:
    k = k_min(S, z)
    return 0.0 if k is None else binom_sf(k, S, c) ** cells


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "p05_sv1_admission_resolution_output.md"))
    a = ap.parse_args(argv)
    L = ["# P05-SV1 admission rule: Monte Carlo decision uncertainty (exact binomial; NOT a calibration run)", ""]
    cs = (0.75, 0.80, 0.85, 0.88, 0.90, 0.93)
    for zname, z in Z.items():
        L += [f"## Wilson bound: {zname}", "",
              "| S per cell | minimum k (k/S) | cells | " + " | ".join(f"P(admit), true c = {c}" for c in cs) + " |",
              "|---|---|---|" + "---|" * len(cs)]
        for S in (40, 60, 100, 150, 200, 300):
            k = k_min(S, z)
            for cells in (2, 3):
                L.append(f"| {S} | {k} ({k / S:.3f}) | {cells} | " + " | ".join(f"{p_admit(c, S, z, cells):.3f}" for c in cs) + " |")
        L.append("")
    # smallest S meeting an operating characteristic, two cells, two-sided Wilson
    z = Z["two-sided 90 % (z = 1.645, as in revision 2 Wilson tables)"]
    L += ["## Smallest S per cell for an operating characteristic (2 cells, two-sided Wilson)", "",
          "| requirement | smallest S (searched 20..1000) |", "|---|---|"]
    for good, bad, pg, pb in ((0.90, 0.80, 0.80, 0.10), (0.90, 0.80, 0.90, 0.05), (0.90, 0.85, 0.80, 0.20)):
        found = next((S for S in range(20, 1001) if p_admit(good, S, z, 2) >= pg and p_admit(bad, S, z, 2) <= pb), None)
        L.append(f"| P(admit | c = {good}) >= {pg} and P(admit | c = {bad}) <= {pb} | {found} |")
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
