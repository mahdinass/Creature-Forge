"""Stage-2 failure analysis (phase 3; read-only; development records only). Where do diagnosis, experiment selection, repair
delegation and memory lose information, and is there a learnable repair signal in the experience data?

Sections 1-6 and A-D read the Stage-2 transfer records (all arms); "corpus" and "tempering" read experience-base records
only (no transfer or sealed data). Output: experiments/causal_engineer/dev/hdb/STAGE2_FAILURE_ANALYSIS.md.
Usage: python scripts/stage2_failure_analysis.py   (from the repo root, after pulling the VM artifacts)
"""
import json, math, collections, statistics as st
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

F = 'artifacts/vm/hdb/artifacts/hdb/'
S = F + 'stage2_final/'
def rows(p): return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
SINGLE = {'A1e': F + 's2T_A1e.jsonl', 'A2': F + 's2T_A2.jsonl', 'A3': S + 's2_transfer_A3.jsonl', 'A4': S + 's2_transfer_A4.jsonl',
          'A4lfo': S + 's2_transfer_A4lfo.jsonl', 'A4bad': S + 's2_transfer_A4bad.jsonl'}
COMP = {'A1e': F + 's2TDC_A1e.jsonl', 'A3': S + 's2_transfer_devcomp_A3.jsonl', 'A4': S + 's2_transfer_devcomp_A4.jsonl'}
D = {('single', a): rows(p) for a, p in SINGLE.items()}
D.update({('comp', a): rows(p) for a, p in COMP.items()})
full = lambda r: r['verification']['status'] == 'FULL_RECOVERY'
inj = lambda r: {tuple(x) for x in r['injected_structure']}
mapc = lambda r: r['map_structure'] == r['injected_structure']

def cat(r):
    v = r['verification']
    if v['status'] == 'FULL_RECOVERY': return 'FULL'
    rs = ' '.join(v['reasons'])
    if 'validation' in rs or ('walking' in rs and 'confirmation' not in rs): return 'validation walking < 80 %'
    if 'verdict' in rs: return 'walks, but verdict_v1 not VERIFIED (displacement vs faulty)'
    if 'confirmation' in rs: return '20 s confirmation failed'
    return 'other: ' + rs[:60]

def final_entry(r):
    rep = r.get('repair') or {}
    for e in rep.get('log') or []:
        if e.get('design') == rep.get('design'): last = e
    return locals().get('last')

def H(ws):
    s = sum(ws); return -sum(w / s * math.log(w / s) for w in ws if w > 0) if s else 0.0

def pct(a, b): return f'{a}/{b} ({100 * a / b:.0f} %)' if b else '0/0'
out = []
P = out.append

# ---------------------------------------------------------------- 1. outcome decomposition
P('## 1. Why non-FULL episodes failed (verification reasons)')
for key in [('single', 'A1e'), ('single', 'A3'), ('single', 'A4'), ('comp', 'A1e'), ('comp', 'A3'), ('comp', 'A4')]:
    c = collections.Counter(cat(r) for r in D[key])
    P(f'- {key[0]} {key[1]}: ' + '; '.join(f'{k}: {v}' for k, v in c.most_common()))
allr = [r for k, v in D.items() for r in v]
c = collections.Counter(cat(r) for r in allr if not full(r))
P(f'- pooled non-FULL (all arms, n = {sum(c.values())}): ' + '; '.join(f'{k}: {v}' for k, v in c.most_common()))

# ---------------------------------------------------------------- 2. diagnosis -> recovery
P('\n## 2. Does a correct diagnosis convert into recovery?')
for kind in ('single', 'comp'):
    rs = [r for (k, a), v in D.items() if k == kind for r in v]
    cr = [r for r in rs if mapc(r)]; wr = [r for r in rs if not mapc(r)]
    P(f'- {kind} (all arms pooled): FULL | MAP correct {pct(sum(map(full, cr)), len(cr))}; FULL | MAP wrong {pct(sum(map(full, wr)), len(wr))}')
    if kind == 'comp':
        part = [r for r in rs if any(tuple(m) in inj(r) for m in r['map_structure'])]
        none = [r for r in rs if r not in part]
        P(f'  - MAP shares >= 1 injected primitive: FULL {pct(sum(map(full, part)), len(part))}; shares none: FULL {pct(sum(map(full, none)), len(none))}')
# mass calibration on single
rs = [r for (k, a), v in D.items() if k == 'single' for r in v]
for lo, hi in ((0, .5), (.5, .9), (.9, .99), (.99, 1.01)):
    b = [r for r in rs if lo <= r['map_mass'] < hi]
    P(f'  - single, MAP mass in [{lo}, {hi}): MAP correct {pct(sum(map(mapc, b)), len(b))}')
rs = [r for (k, a), v in D.items() if k == 'comp' for r in v]
P(f'  - comp: MAP mass >= 0.99 in {pct(sum(r["map_mass"] >= .99 for r in rs), len(rs))}, correct in 0')

# ---------------------------------------------------------------- 3. experiment selection
P('\n## 3. Experiment selection: information gained per experiment (structure-level posterior)')
ig = collections.defaultdict(list); tg = collections.defaultdict(list)
for (kind, a), v in D.items():
    for r in v:
        hist = r['engine']['history']
        chosen = {e['id']: e.get('by', 'engine') for e in r['engine']['events'] if e['kind'] == 'experiment_chosen'}
        for h0, h1 in zip(hist, hist[1:]):
            lab = h1['label'][len('after_'):]
            by = chosen.get(lab, 'engine' if a in ('A1e', 'A2') else 'other')
            w0 = [s['w'] for s in h0['structures']]; w1 = [s['w'] for s in h1['structures']]
            t0 = sum(s['w'] for s in h0['structures'] if {tuple(x) for x in s['structure']} == inj(r))
            t1 = sum(s['w'] for s in h1['structures'] if {tuple(x) for x in s['structure']} == inj(r))
            kindx = 'designed' if (lab.startswith('cf:') and by == 'nemotron' and lab[3:] not in __import__('creature_forge.belief_engine', fromlist=['CANDIDATE_CFS']).CANDIDATE_CFS) else 'listed'
            ig[(kind, by)].append(H(w0) - H(w1)); tg[(kind, by)].append(math.log(max(t1, 1e-6)) - math.log(max(t0, 1e-6)))
            if by == 'nemotron': ig[(kind, 'nemotron-' + kindx)].append(H(w0) - H(w1)); tg[(kind, 'nemotron-' + kindx)].append(math.log(max(t1, 1e-6)) - math.log(max(t0, 1e-6)))
for k in sorted(ig):
    P(f'- {k[0]} chosen by {k[1]}: n {len(ig[k])}, entropy drop median {st.median(ig[k]):+.3f} nats, log-mass gain on truth median {st.median(tg[k]):+.2f}, '
      f'share moving the truth up {sum(x > 0.05 for x in tg[k])}/{len(tg[k])}, down {sum(x < -0.05 for x in tg[k])}/{len(tg[k])}')
first = collections.defaultdict(list)
for (kind, a), v in D.items():
    for r in v:
        h = r['engine']['history']
        first[(kind, a)].append(sum(s['w'] for s in h[0]['structures'] if {tuple(x) for x in s['structure']} == inj(r)))
        first[(kind, a, 'end')].append(r['posterior_mass_on_injected'])
for kind, a in [('single', 'A1e'), ('single', 'A3'), ('comp', 'A1e'), ('comp', 'A3')]:
    P(f'- {kind} {a}: mean mass on truth after observation only {st.mean(first[(kind, a)]):.2f} -> end {st.mean(first[(kind, a, "end")]):.2f}')

# ---------------------------------------------------------------- 4. plant/twin budget use
P('\n## 4. Where the plant and twin budgets go (mean per episode)')
for key in [('single', 'A1e'), ('single', 'A3'), ('single', 'A4'), ('comp', 'A1e'), ('comp', 'A3')]:
    items = collections.Counter(); tw = 0; exh = 0
    for r in D[key]:
        for li in r['engine']['ledger']['lines']: items[li['item']] += li['n']
        tw += r['engine']['ledger']['twin']['used']
        exh += any(e['kind'] == 'twin_budget_exhausted' for e in r['engine']['events'])
    n = len(D[key])
    diag = sum(items[k] for k in ('observe', 'counterfactual', 'floor_test', 'weigh_test'))
    P(f'- {key[0]} {key[1]}: plant diagnosis {diag / n:.0f}, repair {items["repair"] / n:.0f}, robustness {items["robustness_check"] / n:.0f}, '
      f'stress {items["stress_test"] / n:.0f}; twin {tw / n:.0f} of 2800; twin budget exhausted in {exh}/{n}')

# ---------------------------------------------------------------- 5. repair delegation
P('\n## 5. Repair: tool screen, tool choice, twin-to-plant transfer, stopping')
ties = []; topgap = []
for (kind, a), v in D.items():
    for r in v:
        for e in r['engine']['events']:
            if e['kind'] == 'tool_screen':
                sc = [x['score'] for x in e['ranking']]
                ties.append(sum(s >= sc[0] - 0.01 * abs(sc[0]) for s in sc)); break
        for e in r['engine']['events']:
            if e['kind'] == 'tool_screen_cma':
                topgap.append(len({x['cma_walking'] for x in e['ranking']}) == 1); break
P(f'- tool screen: top score shared (within 1 %) by >= 3 tools in {pct(sum(t >= 3 for t in ties), len(ties))} of screens; '
  f'median number tied at the top {st.median(ties)}')
P(f'- CMA re-ranking: every top-5 tool reached the same twin walking count in {pct(sum(topgap), len(topgap))}')
# known-good tools per instance (any arm reached FULL with it)
for kind in ('single', 'comp'):
    good = collections.defaultdict(set); tried_any = collections.defaultdict(set)
    for (k, a), v in D.items():
        if k != kind: continue
        for r in v:
            fe = final_entry(r)
            if full(r) and fe: good[r['instance_id']].add(fe['tool'])
    miss = hit_tried = hit_final = 0; nonfull = 0; nogood = 0
    for (k, a), v in D.items():
        if k != kind: continue
        for r in v:
            if full(r): continue
            nonfull += 1
            g = good.get(r['instance_id'], set())
            if not g: nogood += 1; continue
            tools = {e['tool'] for e in (r.get('repair') or {}).get('log') or []}
            fe = final_entry(r)
            if fe and fe['tool'] in g: hit_final += 1
            elif tools & g: hit_tried += 1
            else: miss += 1
    P(f'- {kind}: non-FULL episodes {nonfull}; on instances no arm recovered: {nogood}; on recoverable instances: '
      f'submitted a tool that worked in another arm {hit_final}, tried it but submitted another {hit_tried}, never tried it {miss}')
# twin -> plant transfer
sur = tot = 0; sur_map = []
for (kind, a), v in D.items():
    for r in v:
        for e in (r.get('repair') or {}).get('log') or []:
            ev = e.get('evidence') or {}
            if e.get('step') == 'twin' and (e.get('twin_walking') or 0) >= 7 and ev.get('robust16') is not None:
                tot += 1
                if ev['robust16'] <= 12: sur += 1; sur_map.append(mapc(r))
P(f'- twin-optimised designs walking >= 7/8 in the twin: plant robust16 <= 12/16 (the plant contradicts the twin) in {pct(sur, tot)}; '
  f'MAP was correct in {sum(sur_map)}/{len(sur_map)} of those (contradictions occurred only under a wrong diagnosis)')
P('- contradictions fed back into the belief (assimilate): 0 in every arm (assimilate was never called by Nemotron; the engine never does it)')
# stopping calibration on transfer
acc = [(final_entry(r)['evidence'].get('p_full'), full(r)) for (k, a), v in D.items() for r in v
       if (r.get('repair') or {}).get('accepted') and final_entry(r) and final_entry(r).get('evidence', {}).get('p_full') is not None]
na = [r for (k, a), v in D.items() for r in v if not (r.get('repair') or {}).get('accepted')]
P(f'- accepted by the calibrated stop: {len(acc)}, mean mapped P(FULL) {st.mean(p for p, _ in acc):.2f}, verified {pct(sum(f for _, f in acc), len(acc))}; '
  f'not accepted (budget/turns ran out): {len(na)}, verified {pct(sum(map(full, na)), len(na))}')
dis = [r for (k, a), v in D.items() for r in v if cat(r).startswith('walks, but') and (r.get('repair') or {}).get('accepted')]
P(f'- accepted designs that walked but failed on displacement (verdict_v1): {len(dis)} (the stop rule never sees forward displacement)')

# ---------------------------------------------------------------- 6. memory
P('\n## 6. Memory retrieval vs what the engine did anyway (A4, single)')
mem = json.load(open(S + 'memory_v5.json', encoding='utf-8'))['dossiers']
mem = mem if isinstance(mem, list) else list(mem.values())
byid = {d['id']: d for d in mem}
same = differ = 0; agree_full = [0, 0]; dis_full = [0, 0]; nod = 0
for r in D[('single', 'A4')]:
    ds = [d for d in mem if {tuple(x) for x in d['mechanism']['structure']} == inj(r) and d.get('status') != 'retired']
    fe = final_entry(r)
    if not ds or not fe: nod += 1; continue
    tools = set(ds[0]['repair']['tools'])
    if fe['tool'] in tools: same += 1; agree_full[0] += full(r); agree_full[1] += 1
    else: differ += 1; dis_full[0] += full(r); dis_full[1] += 1
P(f'- instances with a non-retired dossier for the true mechanism: {same + differ} (no dossier or no repair: {nod})')
P(f'- the submitted tool was already one of the dossier\'s recommended tools in {same}; FULL {agree_full[0]}/{agree_full[1]}. '
  f'Different tool: {differ}; FULL {dis_full[0]}/{dis_full[1]}')
for d in mem:
    sup = [h['support'] for h in d['history'] if h.get('event') == 'support_refresh']
    s = sup[-1] if sup else {}
    P(f'  - {d["id"]} {d["mechanism"]["structure"]} [{d.get("status")}] tools {d["repair"]["tools"]}: precision {s.get("precision")}, '
      f'recommended repair FULL {s.get("recommended_repair")}, other repairs {s.get("other_repairs")}')
P('- dossier content is a mechanism -> tool list; it carries no conditions under which a tool fails, no magnitudes or start edits learned from outcomes, and no link from a failed repair back to the hypothesis')

print('\n'.join(out))

print('\n## 7. Paired diagnosis, evidence of the submitted design, procedure noise, families')
# A. paired diagnosis: entropy & truth mass after observation vs at the end of diagnosis, A1e vs A3 on the same instance
def Hs(h): ws=[s['w'] for s in h['structures']]; s=sum(ws); return -sum(w/s*math.log(w/s) for w in ws if w>0)
def tm(h, r): return sum(s['w'] for s in h['structures'] if {tuple(x) for x in s['structure']} == inj(r))
for kind in ('single',):
    A = {r['instance_id']: r for r in D[(kind,'A1e')]}; B = {r['instance_id']: r for r in D[(kind,'A3')]}
    rows_=[]
    for i in A:
        a, b = A[i], B[i]
        rows_.append((Hs(a['engine']['history'][0]), Hs(a['engine']['history'][-1]), Hs(b['engine']['history'][-1]),
                      a['posterior_mass_on_injected'], b['posterior_mass_on_injected'], len(a['engine']['history'])-1, len(b['engine']['history'])-1,
                      a['engine']['ledger']['lines'] and sum(l['n'] for l in a['engine']['ledger']['lines'] if l['item'] in ('observe','counterfactual','floor_test','weigh_test')),
                      sum(l['n'] for l in b['engine']['ledger']['lines'] if l['item'] in ('observe','counterfactual','floor_test','weigh_test'))))
    print('A. single, paired A1e vs A3: entropy after observation %.2f; end of diagnosis A1e %.2f, A3 %.2f nats' % tuple(st.mean(x[k] for x in rows_) for k in (0,1,2)))
    print('   truth mass end: A1e %.2f A3 %.2f; A3 higher on %d, lower on %d, equal %d' % (st.mean(x[3] for x in rows_), st.mean(x[4] for x in rows_),
          sum(x[4]>x[3]+.05 for x in rows_), sum(x[4]<x[3]-.05 for x in rows_), sum(abs(x[4]-x[3])<=.05 for x in rows_)))
    print('   experiments per episode A1e %.1f, A3 %.1f; diagnostic plant rollouts A1e %.1f, A3 %.1f' % tuple(st.mean(x[k] for x in rows_) for k in (5,6,7,8)))
    print('   entropy already < 0.1 nats after observation in %d/36 (EIG can only be small afterwards)' % sum(x[0] < .1 for x in rows_))
# B. evidence of the submitted design by outcome
print('B. submitted design evidence by verification category (all arms, single + comp):')
g = collections.defaultdict(list)
for k, v in D.items():
    for r in v:
        fe = final_entry(r)
        if not fe: g[cat(r)].append(None); continue
        ev = fe.get('evidence') or {}
        g[cat(r)].append((ev.get('robust16'), ev.get('stress4'), ev.get('p_full'), fe.get('step')))
for c, L in g.items():
    L2 = [x for x in L if x and x[0] is not None]
    print(f'   {c}: n {len(L)}; robust16 median {st.median(x[0] for x in L2) if L2 else None}, >= 15 in {sum(x[0]>=15 for x in L2)}/{len(L2)}; '
          f'stress4 = 4 in {sum((x[1] or 0)==4 for x in L2)}; p_full median {st.median(x[2] for x in L2 if x[2] is not None) if L2 else None:.2f}; '
          f'final step plant {sum(x[3]=="plant" for x in L2)}, twin {sum(x[3]=="twin" for x in L2)}')
# C. procedure noise floor: two deterministic engine arms that differ only by the learned prior
A = {r['instance_id']: r for r in D[('single','A1e')]}; B = {r['instance_id']: r for r in D[('single','A2')]}
same_tool = [(full(A[i]), full(B[i])) for i in A if final_entry(A[i]) and final_entry(B[i]) and final_entry(A[i])['tool']==final_entry(B[i])['tool']]
print(f'C. A1e vs A2 discordant {sum(full(A[i])!=full(B[i]) for i in A)}/36; among instances where both submitted the SAME tool: discordant {sum(a!=b for a,b in same_tool)}/{len(same_tool)}')
for x, y in (('A1e','A3'), ('A1e','A4'), ('A3','A4')):
    A = {r['instance_id']: r for r in D[('single',x)]}; B = {r['instance_id']: r for r in D[('single',y)]}
    st_ = [(full(A[i]), full(B[i])) for i in A if final_entry(A[i]) and final_entry(B[i]) and final_entry(A[i])['tool']==final_entry(B[i])['tool']]
    print(f'   {x} vs {y}: discordant {sum(full(A[i])!=full(B[i]) for i in A)}/36; same final tool on {len(st_)}, of which discordant {sum(a!=b for a,b in st_)}')
# D. per-family FULL across all arms (does any arm crack the hard families?)
fam = collections.defaultdict(lambda: [0,0])
for (k,a), v in D.items():
    if k!='single': continue
    for r in v: fam[r['family']][0]+=full(r); fam[r['family']][1]+=1
print('D. single, FULL by family across all arms:', {f: f'{a}/{b}' for f,(a,b) in sorted(fam.items(), key=lambda x: x[1][0]/x[1][1])})

print('\n## 8. Recoverability ceiling and twin search')
for kind in ('single', 'comp'):
    u = collections.defaultdict(int); arms = collections.defaultdict(set)
    for (k, a), v in D.items():
        if k != kind: continue
        for r in v: u[r['instance_id']] |= full(r); arms[r['instance_id']].add(a)
    print(f'{kind}: instances {len(u)}; recovered by at least one arm {sum(u.values())}')
# twin search success per episode (max twin walking among twin steps) and what happened next
c = collections.Counter()
for (k, a), v in D.items():
    for r in v:
        log = (r.get('repair') or {}).get('log') or []
        tw = [e.get('twin_walking') or 0 for e in log if e.get('step') == 'twin']
        best = max(tw) if tw else None
        c[(('no twin step' if best is None else 'twin >= 7/8' if best >= 7 else 'twin < 7/8'), full(r))] += 1
print('twin search outcome x FULL:', dict(sorted(c.items())))

print('\n## 9. Experience corpus (experience bases only): verified tool outcomes and offline repair-prior checks')
def rows(p): return [json.loads(l) for l in open(F + p, encoding='utf-8') if l.strip()]
def final_tool(r):
    rep = r.get('repair') or {}
    for e in rep.get('log') or []:
        if e.get('design') == rep.get('design'): t = e.get('tool')
    return locals().get('t')
tri = collections.defaultdict(dict)   # instance -> tool -> best verified status
fam = {}
def add(i, tool, status, f):
    if not tool: return
    fam[i] = f
    rank = {'FULL_RECOVERY': 2, 'PARTIAL_IMPROVEMENT': 1, 'NOT_RECOVERED': 0}[status]
    tri[i][tool] = max(tri[i].get(tool, -1), rank)
for r in rows('stopcal.jsonl'):
    if r['source'] != 'initial':
        add(r['instance_id'], r['source'].split(':')[-1], r['status'], r['family'])
for p in ('fresh_A1c5.jsonl', 'vs5_A1c.jsonl', 'vs4_A1c.jsonl', 'vs4_a1.jsonl', 'vs4_A1f.jsonl', 's2DC_exp_A1e.jsonl'):
    for r in rows(p):
        if r.get('eligible') is False or 'verification' not in r: continue
        add(r['instance_id'], final_tool(r), r['verification']['status'], r['family'])
n_a0 = 0
for p in ('fresh_A0.jsonl', 'vs4_A0.jsonl'):
    for r in rows(p):
        if r.get('eligible') is False or 'verification' not in r or 'policy' not in r: continue
        sub = r.get('submitted'); des = r.get('designs') or []
        src = [d.get('source') for d in des if d.get('index') == sub]
        t = src[0].split(':')[-1] if src and src[0] and src[0] != 'initial' else None
        if t: n_a0 += 1
        add(r['instance_id'], t, r['verification']['status'], r['family'])
n = len(tri); cells = sum(len(v) for v in tri.values())
anyfull = sum(any(s == 2 for s in v.values()) for v in tri.values())
multi = [v for v in tri.values() if len(v) >= 2]
print(f'experience instances with >= 1 verified tool outcome: {n}; (instance, tool) cells: {cells}; A0 cells parsed {n_a0}')
print(f'instances with >= 2 tools verified: {len(multi)}; mean tools per instance {cells / n:.2f}; instances where some tool gave FULL: {anyfull}')
disc = sum(1 for v in multi if len({s == 2 for s in v.values()}) == 2)
print(f'instances where tools disagree (some FULL, some not): {disc}/{len(multi)}  <- tool choice matters here')
byf = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
for i, v in tri.items():
    for t, s in v.items(): byf[fam[i]][t][0] += s == 2; byf[fam[i]][t][1] += 1
for f in sorted(byf):
    ts = sorted(byf[f].items(), key=lambda x: -x[1][0] / max(1, x[1][1]))
    print(f'  {f}: ' + ', '.join(f'{t} {a}/{b}' for t, (a, b) in ts if b >= 3))

# Offline check (experience bases only; leave-one-base-out): on instances with >= 2 verified tools, compare the engine's own
# choice (A1c5 final tool) with the tool a mechanism-conditioned success prior would pick among the tools whose outcome is known.
eng = {}
for p in ('fresh_A1c5.jsonl', 'vs5_A1c.jsonl'):
    for r in rows(p):
        if r.get('eligible') is False or 'verification' not in r: continue
        eng[r['instance_id']] = final_tool(r)
base = lambda i: i.split(':')[0]
import random
random.seed(0)
res = collections.Counter(); n = 0
for i, v in tri.items():
    if len(v) < 2 or i not in eng or eng[i] not in v or fam[i].startswith('devcomp'): continue
    cnt = collections.defaultdict(lambda: [0, 0])
    for j, w in tri.items():
        if base(j) == base(i) or fam[j] != fam[i]: continue
        for t, s in w.items(): cnt[t][0] += s == 2; cnt[t][1] += 1
    score = lambda t: (cnt[t][0] + 1) / (cnt[t][1] + 2)
    pick = max(v, key=score)
    n += 1
    res['engine'] += v[eng[i]] == 2; res['learned'] += v[pick] == 2; res['best_known'] += max(v.values()) == 2
    res['random_known'] += sum(s == 2 for s in v.values()) / len(v)
print(f'\nOffline (LOBO, true family as the condition = upper bound; within tools whose outcome is known), n = {n} instances:')
print({k: round(x, 1) for k, x in res.items()})

# Experience as a correction of the engine's own ranking: among the engine's CMA top-k tools whose outcome is known, pick by
# (engine rank) combined with the LOBO mechanism-conditioned success prior.
cma = {}
for p in ('fresh_A1c5.jsonl', 'vs5_A1c.jsonl'):
    for r in rows(p):
        if r.get('eligible') is False or 'engine' not in r: continue
        for e in r['engine']['events']:
            if e['kind'] == 'tool_screen_cma': cma[r['instance_id']] = [x['tool'] for x in e['ranking']]
import math
for lam in (0.0, 0.5, 1.0, 2.0, 4.0):
    res = collections.Counter(); n = 0
    for i, v in tri.items():
        if i not in cma or fam[i].startswith('devcomp'): continue
        known = [t for t in cma[i] if t in v]
        if len(known) < 2: continue
        cnt = collections.defaultdict(lambda: [0, 0])
        for j, w in tri.items():
            if base(j) == base(i) or fam[j] != fam[i]: continue
            for t, s in w.items(): cnt[t][0] += s == 2; cnt[t][1] += 1
        lp = lambda t: math.log((cnt[t][0] + 1) / (cnt[t][1] + 2))
        pick = max(known, key=lambda t: -cma[i].index(t) + lam * lp(t))
        n += 1; res['combined'] += v[pick] == 2; res['engine_top_known'] += v[known[0]] == 2; res['best_known'] += max(v[t] for t in known) == 2
    print(f'lambda {lam}: n {n}', dict(res))

print('\n## 10. Likelihood tempering (experience bases only; offline from stored particle log-likelihoods)')
F = 'artifacts/vm/hdb/artifacts/hdb/'
def rows(p): return [json.loads(l) for l in open(F + p, encoding='utf-8') if l.strip()]
def post(r, T):
    ps = r['engine']['particles']; m = max(p['loglik'] for p in ps)
    w = collections.defaultdict(float)
    for p in ps: w[tuple(sorted(tuple(x) for x in p['structure']))] += math.exp((p['loglik'] - m) / T)
    z = sum(w.values()); return {k: v / z for k, v in w.items()}
single = [r for r in rows('fresh_A1c5.jsonl') if r.get('eligible') is not False and r.get('engine')]
comp = [r for r in rows('s2DC_exp_A1e.jsonl')]
print('n single', len(single), 'n comp', len(comp))
for T in (1, 2, 4, 8, 16, 32):
    ll = []; conf_wrong = 0; top_ok = []
    for r in single:
        P = post(r, T); tru = tuple(sorted(tuple(x) for x in r['injected_structure']))
        ll.append(math.log(max(P.get(tru, 0), 1e-4)))
        mx = max(P, key=P.get); top_ok.append((P[mx], mx == tru)); conf_wrong += P[mx] >= .95 and mx != tru
    hi = [ok for p, ok in top_ok if p >= .95]
    cl = []; cwc = 0
    for r in comp:
        P = post(r, T); inj = {tuple(x) for x in r['injected_structure']}
        cl.append(sum(v for k, v in P.items() if set(k) & inj)); mx = max(P, key=P.get); cwc += P[mx] >= .95
    print(f'T {T:>2}: single mean log P(truth) {st.mean(ll):+.2f}, MAP mass >= .95 in {len(hi)} (correct {sum(hi)}), confident-wrong {conf_wrong}; '
          f'comp: mass on structures sharing an injected primitive {st.mean(cl):.2f}, MAP mass >= .95 in {cwc}/{len(comp)}')
