"""H3 pilot analysis of saved results only. No simulator calls, no fitting."""
import argparse
import collections
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FULL='FULL_RECOVERY'
ARMS=('current','residual','current2x')


def analyze(plan, qualification, cases):
    from h1_independent_stdlib import replay
    ids=sum(qualification['accepted'].values(),[])
    if not qualification['passed'] or len(ids)!=12 or len(set(ids))!=12:
        return {'decision':'NO-GO','reason':'fewer than 12 independent lineages (6 per side)'}
    if {c['id'] for c in cases} != set(ids) or len(cases)!=12:
        raise ValueError('complete 12-case panel required; no post-outcome dropping')
    byid={d['id']:d for d in plan['draws']}
    per=[];req=collections.Counter();flips=collections.Counter();first=collections.Counter()
    for c in sorted(cases,key=lambda c:c['id']):
        if {(r['arm'],r['rep']) for r in c['results']} != {(a,r) for a in ARMS for r in range(2)} or len(c['results'])!=6:
            raise ValueError('each base requires all 3 arms x2 replicates')
        row={'id':c['id'],'side':byid[c['id']]['side']}
        for arm in ARMS:
            rr=sorted([r for r in c['results'] if r['arm']==arm],key=lambda r:r['rep'])
            for r in rr:
                if len(r['panels'])!=3 or any(p.get('errors') for p in r['panels']):
                    raise ValueError('incomplete/error verifier panels')
                for p,expected in zip(r['panels'],byid[c['id']]['panels']):
                    if p['seeds'] != expected: raise ValueError('panel seed drift')
                    replay(p,r['candidate'],expected,p['variation'])
                    if p['status'] not in (FULL,'NOT_RECOVERED','PARTIAL_IMPROVEMENT'):
                        raise ValueError('invalid verifier status')
                    for label in ('original','candidate'):
                        if len(p['validation'][label])!=24 or any(x.get('error') for x in p['validation'][label]):
                            raise ValueError('invalid validation rows')
                    req[arm+'/improvement_failure']+=p['validation']['verdict']['status']!='VERIFIED_IMPROVEMENT'
                    req[arm+'/validation_walking_failure']+=p['validation']['aggregate']!='PASS'
                    req[arm+'/confirmation_observed']+=p['confirmation']['run']
                    if p['confirmation']['run']:
                        for k,v in p['confirmation']['checks'].items():req[arm+'/'+k+'_failure']+=not v['passed']
                if len(r['healthy'])!=8 or any(x.get('error') for x in r['healthy']): raise ValueError('healthy rows missing/error')
                first[arm]+=r['panels'][0]['status']==FULL
                flips[arm]+=(r['panels'][0]['status']==FULL and not all(p['status']==FULL for p in r['panels']))
            row[arm]={'full':sum(p['status']==FULL for r in rr for p in r['panels'])/6,
                      'healthy_walking':sum(x['walking'] for r in rr for x in r['healthy'])/16,
                      'harm':sum(p['validation']['verdict']['status']=='WORSE' for r in rr for p in r['panels'])/6,
                      'stable_full_replicates':sum(all(p['status']==FULL for p in r['panels']) for r in rr)}
        per.append(row)
    def contrast(metric,baseline):
        diffs=np.array([r['residual'][metric]-r[baseline][metric] for r in per])
        # Stratified whole-lineage bootstrap; panels/replicates never independent n.
        rng=np.random.default_rng(2026102603)
        strata=[[i for i,r in enumerate(per) if r['side']==side] for side in ('left','right')]
        indices=np.concatenate([rng.choice(s,(10000,len(s)),replace=True) for s in strata],axis=1)
        boot=np.mean(diffs[indices],axis=1)
        return {'mean':float(diffs.mean()),'descriptive90':np.quantile(boot,[.05,.95]).tolist(),
                'descriptive95':np.quantile(boot,[.025,.975]).tolist(),'independent_lineages':12}
    full={a:contrast('full',a) for a in ('current','current2x')}
    health={a:contrast('healthy_walking',a) for a in ('current','current2x')}
    harm={a:contrast('harm',a) for a in ('current','current2x')}
    persistent=sum(r['residual']['stable_full_replicates']>0 and r['current2x']['stable_full_replicates']==0 for r in per)
    healthy_absolute=float(np.mean([r['residual']['healthy_walking'] for r in per]))
    guard=healthy_absolute>=.8 and all(health[a]['mean']>=-.05 and harm[a]['mean']<=.05 for a in full)
    credible=all(full[a]['mean']>=.15 and full[a]['descriptive90'][0]>0 for a in full) and persistent>=3
    decision='PASS-PILOT' if credible and guard else ('FAIL' if not guard or full['current2x']['mean']<=0 else 'INSUFFICIENT EVIDENCE')
    return {'decision':decision,'scope':'engineering pilot only; no AI learning or confirmatory claim',
        'full_contrasts':full,'healthy_contrasts':health,'harm_contrasts':harm,'persistent_rescue_bases':persistent,
        'guardrails_pass':guard,'residual_healthy_walking':healthy_absolute,'per_base':per,'requirement_counts':dict(req),
        'first_panel_full_not_stable':{a:{'numerator':flips[a],'denominator':first[a]} for a in ARMS}}


def diagnostic_audit(root,cases):
    """Audit added demand separately from actuator clipping; no tracking-error claim."""
    active_bases=set();rows=[]
    for c in cases:
        for r in c['results']:
            arm,rep=r['arm'],r['rep']
            for i in range(2):
                p=Path(root)/'cases'/c['id']/f'{arm}_{rep}_trace{i}.json'
                d=json.loads(p.read_text());samples=d['controller_pre_step'];limit=d['meta']['torque_limit']
                if not samples or not all(k in d['trace'] for k in ('q','qd','tau','demand','force','slip')):
                    raise ValueError('rich diagnostic evidence missing')
                base=np.asarray([s['base_demand'] for s in samples]);extra=np.asarray([s['residual'] for s in samples])
                if not np.all(np.isfinite(base)) or not np.all(np.isfinite(extra)) or np.max(np.abs(extra))>.15*limit+1e-9:
                    raise ValueError('invalid or out-of-bound residual')
                active=float(np.mean(np.any(np.abs(extra)>1e-9,axis=1)))
                effective=np.clip(base+extra,-limit,limit)-np.clip(base,-limit,limit)
                if arm=='residual' and active>=.01:active_bases.add(c['id'])
                rows.append({'id':c['id'],'arm':arm,'rep':rep,'trace':i,'active_time_fraction':active,
                    'effective_after_clip_fraction':float(np.mean(np.any(np.abs(effective)>1e-9,axis=1))),
                    'demand_saturation_fraction':float(np.mean(np.abs(base+extra)>=.99*limit)),
                    'mean_recorded_slip':float(np.mean(d['trace']['slip']))})
    return {'passed':len(active_bases)>=4,'active_residual_bases':len(active_bases),'traces':rows,
            'warning':'Demand changes and slip association do not establish a causal saturation/slip mechanism.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--campaign',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();root=Path(a.campaign)
    from h3_run import sha,save
    plan=json.loads(Path(a.plan).read_text());q=json.loads((root/'qualify/result.json').read_text())
    if q['plan_sha256']!=sha(a.plan):raise ValueError('plan drift')
    cases=[json.loads(p.read_text()) for p in sorted((root/'cases').glob('*/result.json'))]
    if any(c['plan_sha256']!=sha(a.plan) for c in cases):raise ValueError('case plan drift')
    result=analyze(plan,q,cases)
    if q['passed']:
        result['diagnostics']=diagnostic_audit(root,cases)
        if not result['diagnostics']['passed']:result['decision']='NO-GO: mechanism not exercised on four bases'
    save(a.out,result)


if __name__=='__main__':main()
