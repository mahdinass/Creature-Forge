"""Design-stage precision/power approximations for P0.5 (no data access, no simulation)."""
import math
z90, z95, z80 = 1.645, 1.645, 0.8416

def se(q, delta, G, m, rho, infl):
    # paired per-instance difference d in {-1,0,1}: Var(d) = q - delta^2; base-cluster design effect 1+(m-1)rho;
    # infl = extra variance from learning the policy inside LOBO folds (assumed, not measured)
    var = max(q - delta**2, 1e-9) * (1 + (m - 1) * rho) * infl
    return math.sqrt(var / (G * m))

print("A. 90% CI half-width for a paired policy-value difference (delta=0)")
print("q\(G,m)", *[f"{G}x{m}" for G in (12, 24, 36, 46) for m in (1, 2, 3)])
for q in (0.10, 0.15, 0.25):
    for rho in (0.0, 0.2, 0.5):
        for infl in (1.0, 1.5):
            print(f"q={q} rho={rho} infl={infl}", *[f"{z90*se(q,0,G,m,rho,infl):.3f}" for G in (12,24,36,46) for m in (1,2,3)])

print("\nB. Minimum detectable effect (one-sided alpha=0.05, power 0.80)")
for q in (0.10, 0.15, 0.25):
    for rho in (0.0, 0.2, 0.5):
        row = []
        for G in (24, 36, 46):
            for m in (1, 2, 3):
                d = 0.0
                for _ in range(50):
                    d = (z95 + z80) * se(q, d, G, m, rho, 1.5)
                row.append(f"{G}x{m}:{d:.3f}")
        print(f"q={q} rho={rho} infl=1.5", *row)

print("\nC. Instances (G*m) needed for MDE delta at power .80, infl=1.5")
for delta in (0.05, 0.10, 0.15):
    for q in (0.10, 0.15, 0.25):
        for rho, m in ((0.0, 1), (0.2, 2), (0.5, 2), (0.2, 3)):
            n = (z95 + z80) ** 2 * (q - delta**2) * (1 + (m - 1) * rho) * 1.5 / delta**2
            print(f"delta={delta} q={q} rho={rho} m={m}: instances={math.ceil(n)} bases={math.ceil(n/m)}")

print("\nD. Spurious 'informative' rate from optimizer noise alone (all K tools share the same Q=p)")
for p in (0.1, 0.3, 0.5):
    print(p, *[f"K={K}:{1-p**K-(1-p)**K:.2f}" for K in (2, 4, 10)])

print("\nE. Replicate flip-rate precision (Wilson 90% half-width)")
for n in (20, 40, 60, 100):
    for f in (0.05, 0.15, 0.30):
        z = z90; c = (f + z*z/(2*n)) / (1 + z*z/n); h = z*math.sqrt(f*(1-f)/n + z*z/(4*n*n)) / (1 + z*z/n)
        print(f"pairs={n} f={f}: [{c-h:.3f},{c+h:.3f}]")

print("\nF. Cost sensitivity (USD) = rollout-eq * price; price per 1k rollout-eq")
designs = {
  "pilot 16 inst x 10 tools + 40 rep + 16 aug": (16, 16*10 + 40 + 16),
  "campaign 46x2 full matrix + 10% rep + aug": (92, 92*10 + 92 + 92),
  "campaign 46x3 full matrix + 10% rep + aug": (138, 138*10 + 138 + 138),
  "old P0.5b 120 x 4 + 48 rep": (120, 528),
}
for name, (pref, cells) in designs.items():
    for cell in (600, 1000, 2000, 4000):
        re = pref * 1600 + cells * cell
        print(f"{name} | cell={cell}: {re/1e3:.0f}k rollout-eq |",
              " ".join(f"${re/1e3*pr:.2f}@{pr}" for pr in (0.009, 0.02, 0.05)))
