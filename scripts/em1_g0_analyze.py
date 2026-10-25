"""Exploratory G0 descriptives, with base clustering and no fitted learner.

Walking fractions do not label FULL recovery. Fixed post-policy candidate sets
cannot identify a counterfactual effect on the original adaptive engine.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from r0_experiment import write_new,canonical


def mean(xs): return sum(xs)/len(xs) if xs else None


def base_mean(rows,key):
    by=collections.defaultdict(list)
    for r in rows:by[r['base']].append(r[key])
    return {b:mean(v) for b,v in sorted(by.items())}


def bootstrap(values,n=10000,seed=2026102509):
    rng=random.Random(seed)
    draws=sorted(mean([rng.choice(values) for _ in values]) for _ in range(n))
    return [draws[249],draws[9749]]


def analyze(root):
    root=Path(root)
    data=json.loads((root/'jobs.json').read_text())
    expected={j['id']:j for j in data['jobs']}
    files={f.stem:f for f in (root/'predictions').glob('*.json')}
    if files.keys()!=expected.keys():raise ValueError(f'incomplete/unexpected predictions {len(files)}/{len(expected)}')
    rows=[]
    for uid,j in expected.items():
        p=json.loads(files[uid].read_text());q=j['predictor'];e=j['evaluation'];n=j['gold']['n']
        if p['id']!=uid or p['input_sha256']!=hashlib.sha256(canonical(q)).hexdigest() or p['candidate_sha256']!=hashlib.sha256(canonical(q['candidate'])).hexdigest():
            raise ValueError('mismatched prediction intervention')
        if p['n']!=n or len(p['seeds'])!=n or len(set(p['seeds']))!=n or len(p['rows'])!=n or p['duration']!=10.:
            raise ValueError('mismatched seed/condition identity')
        if any(not r.get('ok') for r in p['rows']):raise ValueError('errored physical prediction')
        if sum(r['walking'] for r in p['rows'])!=p['walking']:raise ValueError('prediction aggregate inconsistent')
        y=j['gold']['walking']/n;pred=p['walking']/n
        rows.append({'id':uid,'instance_id':e['instance_id'],'base':e['base'],'family':e['family'],
                     'design_index':e['design_index'],'original_submission':e['is_original_submission'],
                     'full_known':e['verified_status'] is not None,'known_full':e['verified_status']=='FULL_RECOVERY',
                     'n':n,'observed':y,'predicted':pred,'residual':y-pred,'squared_mean_error':(y-pred)**2,
                     'aggregate_bernoulli_brier':y*(1-pred)**2+(1-y)*pred**2,
                     'worker_s':p['wall_s']})
    bias=base_mean(rows,'residual');mse=base_mean(rows,'squared_mean_error')
    per_family={}
    for family in sorted({r['family'] for r in rows}):
        rr=[r for r in rows if r['family']==family]
        bb=base_mean(rr,'residual')
        per_family[family]={'bases':len(bb),'episodes':len({r['instance_id'] for r in rr}),
                            'interventions':len(rr),'base_mean_residual':mean(list(bb.values())),
                            'descriptive_bootstrap95':bootstrap(list(bb.values()))}
    by=collections.defaultdict(list)
    for r in rows:by[r['instance_id']].append(r)
    comparisons=[]
    for iid,rr in sorted(by.items()):
        original=next((r for r in rr if r['original_submission']),None)
        if original is None:continue
        # Tie-break is prespecified without consulting outcome: original final,
        # then earlier design index. This is an audit ranker, not actual B0.
        ranked=sorted(rr,key=lambda r:(-r['predicted'],-int(r['original_submission']),r['design_index']))
        chosen=ranked[0];oracle=max(r['observed'] for r in rr)
        comparisons.append({'instance_id':iid,'base':rr[0]['base'],'family':rr[0]['family'],
          'available_designs':len(rr),'twin_only_choice':chosen['id'],'original_choice':original['id'],
          'twin_only_walking_regret':oracle-chosen['observed'],
          'original_walking_regret':oracle-original['observed'],
          'twin_changes_submission':chosen['id']!=original['id'],
          'unknown_full_for_twin_choice':not chosen['full_known']})
    original_regret=base_mean(comparisons,'original_walking_regret')
    raw_regret=base_mean(comparisons,'twin_only_walking_regret')
    # Planning sensitivity, not fitted power and not an E-1-derived estimate.
    # Single independent base per pair, normal paired-difference approximation;
    # binary discordance q contributes variance q-delta^2.
    power=[]
    for delta in (.05,.10,.15):
        for q in (.20,.40,.60):
            n=math.ceil((1.959963984540054+0.8416212335729143)**2*(q-delta**2)/delta**2)
            power.append({'minimum_true_difference':delta,'discordance_assumption':q,
                          'independent_bases_approx_80pct_power_two_sided_05':n,
                          'warning':'planning approximation; finite-sample clustered simulation required before any launch'})
    result={'version':'em1_g0_descriptive_v1','complete':True,'interventions':len(rows),
            'episodes':len(by),'independent_bases':len(bias),'families':len(per_family),
            'twin_rollouts':sum(r['n'] for r in rows),'new_plant_rollouts':0,'model_calls':0,
            'base_equal_mean_residual':mean(list(bias.values())),
            'base_cluster_bootstrap95_residual':bootstrap(list(bias.values())),
            'base_equal_mean_squared_prediction_error':mean(list(mse.values())),
            'base_equal_aggregate_bernoulli_brier':mean(list(base_mean(rows,'aggregate_bernoulli_brier').values())),
            'bias_by_base':bias,'residuals_by_family':per_family,
            'original_engine_base_mean_walking_regret':mean(list(original_regret.values())),
            'original_engine_walking_regret_bootstrap95':bootstrap(list(original_regret.values())),
            'twin_only_audit_ranker_base_mean_walking_regret':mean(list(raw_regret.values())),
            'episodes_with_at_least_two_checked_designs':sum(len(v)>=2 for v in by.values()),
            'episodes_where_twin_only_audit_ranker_changes_submission':sum(r['twin_changes_submission'] for r in comparisons),
            'twin_only_audit_ranker_choices_without_full_labels':sum(r['unknown_full_for_twin_choice'] for r in comparisons),
            'unsubmitted_interventions_without_full_labels':sum(not r['full_known'] for r in rows),
            'known_original_full':sum(r['known_full'] for r in rows if r['original_submission']),
            'sum_worker_h':sum(r['worker_s'] for r in rows)/3600,
            'power_sensitivity':power,'candidate_comparisons':comparisons,
            'record_sha256':{str(f.relative_to(root)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files.values())},
            'interpretation':'Retrospective model-error audit only; no correction learner, causal recovery contrast, prospective evaluation or Nemotron test.'}
    write_new(root/'g0_analysis.json',result)
    write_new(root/'paired_aggregate_rows.json',rows)
    print(json.dumps({k:v for k,v in result.items() if k not in ('record_sha256','candidate_comparisons','bias_by_base')},indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();analyze(a.root)
