"""DI-1 engineering audit and conservative prospective power/resource planning.

Pilot findings are descriptive, never a scientific gate PASS/FAIL. No fitting.
One paired binary outcome per independent generated base.
"""
from __future__ import annotations
import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r0_experiment import write_new


def pmf(k,n,p):
    if p == 0:return float(k==0)
    if p == 1:return float(k==n)
    return math.exp(math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)+k*math.log(p)+(n-k)*math.log1p(-p))


def upper_rate(k,n,alpha=.05):
    if not n:return 1.
    if k==n:return 1.
    lo,hi=0.,1.
    for _ in range(60):
        p=(lo+hi)/2
        cdf=sum(pmf(i,n,p) for i in range(k+1))
        if cdf>alpha:lo=p
        else:hi=p
    return (lo+hi)/2


def rate_interval(k,n):
    if not n:return [0.,1.]
    return [0. if k==0 else 1-upper_rate(n-k,n,.025),upper_rate(k,n,.025)]


def cluster_interval(values):
    if not values:return [None,None]
    rng=random.Random(2026102501)
    draws=sorted(sum(rng.choice(values) for _ in values)/len(values) for _ in range(10000))
    return [draws[249],draws[9749]]


@lru_cache(None)
def critical(d):
    tail=0.
    for s in range(d, d//2, -1):
        tail+=pmf(s,d,.5)
        if tail>.025:return s+1
    return d//2+1


def power(n,q,delta=.1):
    if not delta<=q<=1:raise ValueError('infeasible discordance/effect')
    p=(1+delta/q)/2
    return sum(pmf(d,n,q)*sum(pmf(s,d,p) for s in range(critical(d),d+1)) for d in range(n+1))


def required_n(q,delta=.1,target=.9):
    lo,hi=1,800
    if power(hi,q,delta)<target:return None
    while lo<hi:
        n=(lo+hi)//2
        if power(n,q,delta)>=target:hi=n
        else:lo=n+1
    return lo


def audit_trace(path):
    # Independent implementation: no dependency on decision_trace verifier.
    prev='0'*64;seq=0;batches={};received={};panels=[];errors=[];jobs=0;calls={}
    candidates={'plant':set(),'twin':set()};equiv={'plant':0.,'twin':0.};weigh=0;panel_followed=False
    for line in Path(path).read_text().splitlines():
        r=json.loads(line);digest=r.pop('sha256')
        payload=(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        if r['seq']!=seq or r['previous']!=prev or hashlib.sha256(payload).hexdigest()!=digest:
            raise ValueError(f'broken journal {path}:{seq}')
        if r['kind']=='jobs_before':
            batches[seq]=r;received[seq]=set();jobs+=len(r['jobs'])
            if any('plant' in j for j in r['jobs']):raise ValueError('hidden plant leak')
            role='twin' if any(calls.get(c,'').startswith('twin_') for c in r['scope']) else 'plant'
            for j in r['jobs']:
                candidates[role].add(hashlib.sha256(json.dumps([j['body'],j['vector']],sort_keys=True).encode()).hexdigest())
                equiv[role]+=j.get('duration',10)/10
        elif r['kind']=='call_before':
            calls[seq]=r['method']
            if panels and not panel_followed and r['method']=='experiment_step':
                if r['args'][0]['id']!=panels[0]['selected']['id']:raise ValueError('unregistered panel choice')
                panel_followed=True
        elif r['kind']=='call_after' and r['method']=='weigh_test' and r['result'].get('ok'):
            weigh+=1
        elif r['kind']=='job_after':
            b,i=r['batch'],r['index']
            if b not in batches or not 0<=i<len(batches[b]['jobs']) or i in received[b]:
                raise ValueError('invalid/duplicate/out-of-order outcome')
            received[b].add(i)
            v=r['result']
            if isinstance(v,list) or (isinstance(v,dict) and v.get('ok') is False):errors.append(r)
        elif r['kind']=='panel_frozen_before_plant':panels.append(r)
        prev=digest;seq+=1
    if any(len(received[b])!=len(r['jobs']) for b,r in batches.items()):raise ValueError('missing job outcome')
    if len(panels)>1:raise ValueError('multiple first panels')
    if panels and not panel_followed:raise ValueError('frozen choice never executed')
    return {'records':seq,'jobs':jobs,'errors':len(errors),'panels':len(panels),'last_sha256':prev,
            'unique_simulated_candidates':{k:len(v) for k,v in candidates.items()},
            'physical_rollout_equivalents':equiv,'static_weigh_equivalents':weigh}


def analyze(root):
    root=Path(root);config=json.loads(Path('experiments/causal_engineer/dev/di1/pilot_config.json').read_text())
    rows=[];traces={};excluded=[];equivalences=[]
    for base in config['bases']:
        d=root/base['base_id'];c=json.loads((d/'complete.json').read_text())
        if not c['eligible']:
            excluded.append(c);continue
        eq=json.loads((d/'equivalence.json').read_text())
        if not eq['equal'] or eq['original_sha']!=eq['instrumented_sha']:raise ValueError('equivalence failed')
        equivalences.append(eq)
        arms={m:json.loads((d/f'{m}.json').read_text()) for m in config['arms']}
        for m,r in arms.items():
            traces[f"{base['base_id']}/{m}"]=audit_trace(d/f'{m}.jsonl')
            trace=traces[f"{base['base_id']}/{m}"];ledger=r['scientific']['ledger']
            if r['scientific']['ledger']['used']>700 or r['scientific']['ledger']['twin']['used']>2800:
                raise ValueError('policy over budget')
            if trace['physical_rollout_equivalents']['plant']+trace['static_weigh_equivalents']!=ledger['used']:
                raise ValueError('plant trace/ledger cost mismatch')
            if trace['physical_rollout_equivalents']['twin']!=ledger['twin']['used']:
                raise ValueError('twin trace/ledger cost mismatch')
            if r['verification']['status']=='INCONCLUSIVE_ERROR':raise ValueError('verification error')
        b,p,s=(arms[m] for m in config['arms'])
        y={m:int(r['verification']['status']=='FULL_RECOVERY') for m,r in arms.items()}
        choice={m:(r['first_decision'] or {}).get('selected',{}).get('id') for m,r in arms.items()}
        pre=b['first_decision']
        signals=None
        if pre:
            weights=[p[1] for p in pre['state']['posterior']]
            baseline_eig=pre['candidates'][0][1]
            signals={'posterior_entropy':-sum(w*math.log(w) for w in weights if w),
                     'candidate_count':len(pre['candidates']),
                     'raw_eig_advantage':max(t[1] for t in pre['candidates'])-baseline_eig,
                     'raw_changes_choice':choice['raw_eig']!=choice['baseline']}
        if any(r['first_decision'] is not None for r in arms.values()):
            panels=[r['first_decision'] for r in arms.values()]
            if any(p is None for p in panels):raise ValueError('decision fork missing')
            if any(p['state']!=panels[0]['state'] or p['candidates']!=panels[0]['candidates'] for p in panels):
                raise ValueError('fork predecision state/candidate mismatch')
        rows.append({'base':base['base_id'],'parent':base['parent_dev_base'],'full':y,'choice':choice,
                     'predecision_signals':signals,
                     'distinct_final_interventions':len({hashlib.sha256(json.dumps({k:r['scientific']['selected'][k] for k in ('body','vector')},sort_keys=True).encode()).hexdigest() for r in arms.values()}),
                     'opportunity':int(not y['baseline'] and (y['raw_eig'] or y['random'])),
                     'raw_improvement':y['raw_eig']-y['baseline'], 'predictivity':y['raw_eig']-y['random'],
                     'raw_negative_transfer':int(y['baseline'] and not y['raw_eig']),
                     'policy_s':{m:r['policy_wall_s'] for m,r in arms.items()},
                     'wall_s':c['wall_s'],
                     'plant_used':{m:r['scientific']['ledger']['used'] for m,r in arms.items()},
                     'twin_used':{m:r['scientific']['ledger']['twin']['used'] for m,r in arms.items()},
                     'validation_walking':{m:r['verification']['validation']['walking_frac'] for m,r in arms.items()},
                     'confirmation':{m:r['verification']['confirmation'] for m,r in arms.items()}})
    n=len(rows);opp=sum(r['opportunity'] for r in rows)
    contrasts={}
    for name in ('raw_improvement','predictivity'):
        k=sum(r[name]!=0 for r in rows);q=max(.1,upper_rate(k,n,.025))
        contrasts[name]={'discordant_bases':k,'n':n,'mean':sum(r[name] for r in rows)/n if n else None,
                         'descriptive_base_bootstrap95':cluster_interval([r[name] for r in rows]),
                         'discordance_upper97_5':q,'required_n_90pct_power':required_n(q)}
    # Each contrast90% power => joint power at least80% by union bound.
    q=max(x['discordance_upper97_5'] for x in contrasts.values())
    sensitivity=[{'delta':delta,'discordance':dis,'required_n_90pct_power':required_n(dis,delta)}
                 for delta in (.05,.1,.15) for dis in (.2,.4,.6)]
    summary={'stage':'engineering pilot only','gate':'PENDING_FEASIBILITY','independent_bases':n,
             'attempts':8,'excluded':excluded,'rows':rows,'equivalence_passes':len(equivalences),
             'opportunity_bases':opp,'opportunity_rate':opp/n if n else None,
             'opportunity_exact95':rate_interval(opp,n),'contrasts':contrasts,'power_sensitivity':sensitivity,
             'active_decision_bases':sum(r['choice']['baseline'] is not None for r in rows),
             'raw_changed_choices':sum(r['choice']['raw_eig']!=r['choice']['baseline'] for r in rows),
             'random_changed_choices':sum(r['choice']['random']!=r['choice']['baseline'] for r in rows),
             'full_paths':{m:sum(r['full'][m] for r in rows) for m in config['arms']},
             'distinct_final_interventions':sum(r['distinct_final_interventions'] for r in rows),
             'negative_transfer_exact95':rate_interval(sum(r['raw_negative_transfer'] for r in rows),n),
             'planning_n':max(x['required_n_90pct_power'] or 801 for x in contrasts.values()),
             'traces':traces,'trace_errors':sum(t['errors'] for t in traces.values()),
             'qualification_note':'new body draws conditional on fixed development parent pool; narrow local population',
             'notes':['Not a registered prospective gate result','No learner or Nemotron adaptation tested',
                      'Small-pilot bootstrap intervals can degenerate; exact base-level rate bounds remain reported',
                      'Planning powers only paired contrast tests; full advancement conditions can require more information',
                      'Counterfactual panel is research-only; selected best-of-panel is not a deployable policy',
                      'No sealed cohort accessed; pilot excluded from any future evaluation']}
    if summary['trace_errors']:raise ValueError('physics errors in trace')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    out=analyze(a.root);write_new(a.out,out)
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','traces','excluded')},indent=2))


if __name__=='__main__':main()
