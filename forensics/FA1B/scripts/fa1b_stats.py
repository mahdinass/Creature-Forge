"""FA-1B Investigation E: targeted checks of FA-1's statistical claims (read-only; FA-1 episode_index.csv only).

E1  eta^2 shares of binary FULL (fa1_misc.py:51-60) recomputed, with their expectation under 'no group effect'
    (E[eta^2] = (k-1)/(N-1) for k groups, N observations) and the chance-corrected omega^2.
E2  pooled single-fault Wilson interval (fa1_f1.py:40-45, labelled 'clustered by instance'): design effect from the
    instance ICC; distinct instances / bases; exact McNemar discordants recomputed.
E3  'correct diagnosis does not help': within-instance comparison among instances whose arms disagree on diagnosis
    correctness (holds the physical instance fixed; still confounded by arm/trajectory)."""
import collections
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1b_load as L

E = list(csv.DictReader(open(os.path.join(L.FA1, "episode_index.csv"), encoding="utf-8")))
B = lambda x: x in (True, "True")  # noqa: E731


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def shares(rows, key):
    y = [1.0 if B(r["full"]) else 0.0 for r in rows]
    mu = sum(y) / len(y)
    sst = sum((v - mu) ** 2 for v in y)
    g = collections.defaultdict(list)
    for r, v in zip(rows, y):
        g[r[key] if not callable(key) else key(r)].append(v)
    ssb = sum(len(v) * (sum(v) / len(v) - mu) ** 2 for v in g.values())
    k, n = len(g), len(y)
    ssw = sst - ssb
    msw = ssw / (n - k)
    omega = (ssb - (k - 1) * msw) / (sst + msw)
    return ssb / sst, (k - 1) / (n - 1), omega, k, n


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0, 1.0
    one = sum(math.comb(n, i) for i in range(b, n + 1)) / 2 ** n
    two = min(1.0, 2 * min(one, sum(math.comb(n, i) for i in range(0, b + 1)) / 2 ** n))
    return one, two


def main():
    print("## E1 descriptive variance shares of binary FULL (144 arm-episodes)")
    for name, key in (("instance", "instance_id"), ("arm", "arm"), ("robot base", "robot_base"), ("failure family", "failure_family")):
        eta, null, omega, k, n = shares(E, key)
        print(f"  {name:14s}: eta^2 {eta:.3f}  (expected under no effect {(null):.3f}, k={k}, N={n}); omega^2 {omega:.3f}")
    print("\n## E2 pooled single-fault diagnosis x FULL: independence vs. instance clustering")
    S = [e for e in E if e["kind"] == "single"]
    inst = collections.defaultdict(list)
    for e in S:
        inst[e["instance_id"]].append(1.0 if B(e["full"]) else 0.0)
    # one-way ANOVA ICC for binary outcome, m = 4 per instance
    m = 4
    y = [v for vs in inst.values() for v in vs]
    mu = sum(y) / len(y)
    msb = sum(m * (sum(v) / m - mu) ** 2 for v in inst.values()) / (len(inst) - 1)
    msw = sum((x - sum(v) / m) ** 2 for v in inst.values() for x in v) / (len(y) - len(inst))
    icc = (msb - msw) / (msb + (m - 1) * msw)
    deff = 1 + (m - 1) * icc
    print(f"  singles: {len(S)} arm-episodes, {len(inst)} instances, {len({e['robot_base'] for e in S})} bases; ICC(instance) {icc:.3f}; design effect {deff:.2f}")
    for f in ("true_structure_match",):
        for lab, sel in (("correct", True), ("wrong", False)):
            xs = [e for e in S if B(e[f]) == sel]
            k, n = sum(B(e["full"]) for e in xs), len(xs)
            lo, hi = wilson(k, n)
            ne = n / deff
            lo2, hi2 = wilson(k / n * ne, ne)
            print(f"  {lab:7s}: FULL {k}/{n} = {k / n:.2f}; ordinary Wilson {lo:.2f}-{hi:.2f}; with design effect (n_eff {ne:.0f}) {lo2:.2f}-{hi2:.2f};"
                  f" distinct instances {len({e['instance_id'] for e in xs})}")
    print("\n## E2 exact McNemar on paired FULL (36 instances, recomputed)")
    by = collections.defaultdict(dict)
    for e in E:
        by[e["instance_id"]][e["arm"]] = B(e["full"])
    for a, b in (("A3v5", "A1e6"), ("A4x", "A1e6"), ("A1e6", "A1e"), ("A4x", "A3v5")):
        bb = sum(1 for v in by.values() if v[a] and not v[b])
        cc = sum(1 for v in by.values() if v[b] and not v[a])
        p1, p2 = mcnemar_exact(bb, cc)
        print(f"  {a} vs {b}: {a}-only {bb}, {b}-only {cc}; exact p one-sided {p1:.3f}, two-sided {p2:.3f}")
    print("\n## E3 within-instance diagnosis comparison (singles; instances where arms differ in exact-diagnosis correctness)")
    di = collections.defaultdict(list)
    for e in S:
        di[e["instance_id"]].append((B(e["true_structure_match"]), B(e["full"]), e["arm"]))
    mixed = {k: v for k, v in di.items() if len({c for c, _, _ in v}) == 2}
    rc = sum(f for v in mixed.values() for c, f, _ in v if c)
    nc = sum(1 for v in mixed.values() for c, f, _ in v if c)
    rw = sum(f for v in mixed.values() for c, f, _ in v if not c)
    nw = sum(1 for v in mixed.values() for c, f, _ in v if not c)
    print(f"  instances with mixed diagnosis correctness: {len(mixed)}; FULL when correct {rc}/{nc}, when wrong {rw}/{nw}")
    disc = [(k, v) for k, v in mixed.items() if len({f for _, f, _ in v}) == 2]
    print(f"  of those, instances with mixed FULL outcome: {len(disc)}")
    for k, v in disc:
        print("   ", k, sorted(v, key=lambda t: t[2]))
    # instance-mean difference (each mixed instance weighted equally)
    dd = []
    for v in mixed.values():
        c = [f for cc_, f, _ in v if cc_]
        w = [f for cc_, f, _ in v if not cc_]
        dd.append(sum(c) / len(c) - sum(w) / len(w))
    print(f"  mean within-instance FULL difference (correct - wrong): {sum(dd) / len(dd):+.3f} over {len(dd)} instances; "
          f"positive {sum(d > 0 for d in dd)}, negative {sum(d < 0 for d in dd)}, zero {sum(d == 0 for d in dd)}")
    allsame = sum(1 for v in di.values() if len({c for c, _, _ in v}) == 1)
    print(f"  instances where all arms agree on correctness: {allsame} (correct-everywhere {sum(1 for v in di.values() if all(c for c, _, _ in v))}, "
          f"wrong-everywhere {sum(1 for v in di.values() if not any(c for c, _, _ in v))})")


if __name__ == "__main__":
    main()
