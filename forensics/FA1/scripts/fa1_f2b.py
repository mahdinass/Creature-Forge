"""FA-1 F2b: replay each assimilation's structure-level update from its recorded counts and weights (count-bound model),
and compare the expected with the realised posterior shift. Also mass-weighted disagreement."""
import collections, csv, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fa1_load as L
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = lambda x: x in (True, "True")
k = L.PER_SEED_NATS / 6.0
def rank(v):
    o = np.argsort(v); r = np.empty(len(v)); r[o] = np.arange(len(v)); return r
def spearman(a, b):
    return float(np.corrcoef(rank(np.array(a)), rank(np.array(b)))[0, 1])
rows = [r for r in csv.DictReader(open(os.path.join(OUT, "feedback_events.csv"), encoding="utf-8")) if not B(r["skipped"])]
res = []
for r in rows:
    pred = json.loads(r["predicted_walking"]); obs = int(r["observed_walking"])
    before = json.loads(r["posterior_before"]); after = json.loads(r["posterior_after"])
    bw = {L.st_str(s): w for s, w in before}; aw = {L.st_str(s): w for s, w in after}
    # count-bound replay over the top-4 (unmodelled inherits the leading modelled structure's likelihood, i.e. the best particle)
    lead_mod = next((L.st_str(s) for s, _ in before if L.st_str(s) != "unmodelled:any"), None)
    ll = {}
    for s, w in bw.items():
        key = lead_mod if s == "unmodelled:any" else s
        if key in pred:
            ll[s] = -k * abs(pred[key] - obs)
    if len(ll) < 2:
        continue
    tot = sum(bw[s] for s in ll)
    pb = {s: bw[s] / tot for s in ll}
    m = max(ll.values()); z = sum(pb[s] * math.exp(ll[s] - m) for s in ll)
    pa = {s: pb[s] * math.exp(ll[s] - m) / z for s in ll}
    tv_exp = 0.5 * sum(abs(pa[s] - pb[s]) for s in ll)
    # realised TV restricted to the same structures, renormalised
    tota = sum(aw.get(s, 0.0) for s in ll)
    tv_real = 0.5 * sum(abs((aw.get(s, 0.0) / tota if tota else 0) - pb[s]) for s in ll) if tota else None
    # mass-weighted disagreement: expected |pred_s - pred_leader| under the modelled posterior excluding the leader
    mods = [(s, w) for s, w in before if L.st_str(s) != "unmodelled:any" and L.st_str(s) in pred]
    lw = mods[0][1]; lp = pred[L.st_str(mods[0][0])]
    others = mods[1:]
    wdis = sum(w * abs(pred[L.st_str(s)] - lp) for s, w in others) / (sum(w for _, w in mods) or 1)
    comp_mass = sum(w for _, w in others)
    lead_flip_exp = max(pa, key=pa.get) != max(pb, key=pb.get)
    res.append(dict(r, tv_exp=tv_exp, tv_real=tv_real, wdis=wdis, comp_mass=comp_mass, lead_flip_exp=lead_flip_exp,
                    lead_w=lw))
print("events replayed", len(res))
te = [x["tv_exp"] for x in res]; tr = [x["tv_real"] for x in res if x["tv_real"] is not None]
print("expected TV (count-bound replay): median %.4f p75 %.4f p90 %.4f max %.3f" % (np.median(te), np.percentile(te, 75), np.percentile(te, 90), max(te)))
print("realised TV (same structures):    median %.4f p75 %.4f p90 %.4f max %.3f" % (np.median(tr), np.percentile(tr, 75), np.percentile(tr, 90), max(tr)))
pairs = [(x["tv_exp"], x["tv_real"]) for x in res if x["tv_real"] is not None]
print("Spearman(expected, realised) %.3f; mean ratio realised/expected over events with expected>0.02: %.2f (n %d)" % (
    spearman([a for a, _ in pairs], [b for _, b in pairs]),
    np.mean([b / a for a, b in pairs if a > 0.02]), sum(1 for a, _ in pairs if a > 0.02)))
big = [x for x in res if x["tv_exp"] > 0.1]
print("events with expected TV > 0.1:", len(big), "realised TV for them:", [round(x["tv_real"], 3) for x in big])
print("expected leader flips (count bound):", sum(x["lead_flip_exp"] for x in res), [(x["arm"], x["instance_id"], x["event_order"], round(x["tv_exp"], 3), round(x["tv_real"], 3), x["leader_changed"]) for x in res if x["lead_flip_exp"]])
print("\nmass-weighted disagreement (seeds, competitor mass-weighted |pred - leader pred|):")
wd = [x["wdis"] for x in res]
print("  median %.3f p75 %.3f p90 %.3f max %.3f; events >= 1 seed: %d; >= 2 seeds: %d" % (np.median(wd), np.percentile(wd, 75), np.percentile(wd, 90), max(wd), sum(w >= 1 for w in wd), sum(w >= 2 for w in wd)))
cm = [x["comp_mass"] for x in res]
print("  modelled competitor mass (top-4 minus leader): median %.3f p25 %.3f p75 %.3f" % (np.median(cm), np.percentile(cm, 25), np.percentile(cm, 75)))
lw = [x["lead_w"] for x in res]
print("  leader (modelled) mass before: median %.3f p25 %.3f p75 %.3f; >=0.9: %d of %d" % (np.median(lw), np.percentile(lw, 25), np.percentile(lw, 75), sum(w >= .9 for w in lw), len(lw)))
print("\nsensitivity: replay without tempering (T=1) - how many leader flips would the same counts imply?")
flips1 = 0; tv1 = []
for x in res:
    pred = json.loads(x["predicted_walking"]); obs = int(x["observed_walking"])
    before = json.loads(x["posterior_before"]); bw = {L.st_str(s): w for s, w in before}
    lead_mod = next((L.st_str(s) for s, _ in before if L.st_str(s) != "unmodelled:any"), None)
    ll = {s: -L.PER_SEED_NATS * abs(pred[(lead_mod if s == "unmodelled:any" else s)] - obs) for s in bw if (lead_mod if s == "unmodelled:any" else s) in pred}
    if len(ll) < 2: continue
    # untempered posterior before: raise tempered weights to the power 6 (w_T6 ~ exp(loglik/6))
    pb6 = {s: bw[s] ** 6 for s in ll}; t = sum(pb6.values()); pb6 = {s: v / t for s, v in pb6.items()}
    m = max(ll.values()); z = sum(pb6[s] * math.exp(ll[s] - m) for s in ll); pa = {s: pb6[s] * math.exp(ll[s] - m) / z for s in ll}
    flips1 += max(pa, key=pa.get) != max(pb6, key=pb6.get); tv1.append(0.5 * sum(abs(pa[s] - pb6[s]) for s in ll))
print("  T=1 replay: leader flips %d, median TV %.4f p90 %.4f" % (flips1, np.median(tv1), np.percentile(tv1, 90)))
print("\nleader prediction vs observation, among events where the leader carried >=0.5 modelled mass:")
c = collections.Counter()
for x in res:
    pred = json.loads(x["predicted_walking"]); before = json.loads(x["posterior_before"])
    mods = [(L.st_str(s), w) for s, w in before if L.st_str(s) != "unmodelled:any" and L.st_str(s) in pred]
    if mods and mods[0][1] >= .5:
        d = pred[mods[0][0]] - int(x["observed_walking"])
        c["leader over-predicts >=3" if d >= 3 else "leader under-predicts >=3" if d <= -3 else "within 2"] += 1
print(" ", dict(c))
# write augmented columns
with open(os.path.join(OUT, "feedback_replay.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["instance_id", "arm", "event_order", "design", "tv_expected_countbound", "tv_realised", "massweighted_disagreement_seeds", "competitor_mass", "leader_mass", "expected_leader_flip"])
    for x in res: w.writerow([x["instance_id"], x["arm"], x["event_order"], x["design"], round(x["tv_exp"], 5), round(x["tv_real"], 5), round(x["wdis"], 4), round(x["comp_mass"], 4), round(x["lead_w"], 4), x["lead_flip_exp"]])
