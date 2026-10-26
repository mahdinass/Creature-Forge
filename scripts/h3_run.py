"""Frozen H3 pilot preparation / future execution. No VM or model-call code.

`plan` is non-physics. gate/qualify/case require --execute and a fresh explicit
human authorization receipt. Never manufacture that receipt from H1 permission.
"""
import argparse
from functools import partial
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STUDY = ROOT/'experiments/causal_engineer/dev/h3'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_sha(path):
    # Explicit source normalization only. Plans, outcomes and historical evidence
    # retain exact bytes. Windows source CRLF and Linux LF compile identically.
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def save(path, obj):
    from creature_forge.optimize import jsonable
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(jsonable(obj), f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def append_event(path,event):
    from creature_forge.optimize import jsonable
    with Path(path).open('a',encoding='utf-8') as f:
        f.write(json.dumps(jsonable(event),sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def make_plan():
    import numpy as np
    from creature_forge.creature_gen import sample_body
    from creature_forge.creature_walk import R2_WINNER
    from creature_forge.arena import VARIATION_PRESET
    history_file='experiments/causal_engineer/dev/h1/candidates.json'
    history=json.loads((ROOT/history_file).read_text(encoding='utf-8'))
    def body_hash(body):
        return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    historical_bodies={body_hash(c['original']['body']) for c in history}
    draws = []
    for i in range(48):
        s = 1930000000 + 1000*i
        body = sample_body(np.random.default_rng(202610260300+i))
        if body_hash(body) in historical_bodies:raise ValueError('exact historical body collision; amend before qualification')
        draws.append({'id': f'h3-new-{i:03}', 'draw': i, 'body': body,
            'vector': list(R2_WINNER)+[.5,.5], 'side': 'left' if i % 2 == 0 else 'right',
            'plant': {'deviation': [{'kind': 'actuator_strength', 'target': 'left' if i%2==0 else 'right',
                                      'params': {'factor': .4}}]},
            'qual_healthy10': list(range(s,s+8)), 'qual_healthy20': list(range(s+8,s+16)),
            'qual_damaged': list(range(s+16,s+24)),
            'train': [list(range(s+100+4*r,s+104+4*r)) for r in range(2)],
            'select': [list(range(s+200+8*r,s+208+8*r)) for r in range(2)],
            'panels': [{'validate': list(range(s+300+48*p,s+324+48*p)),
                        'confirm': list(range(s+324+48*p,s+348+48*p))} for p in range(3)],
            'healthy_guard': list(range(s+500,s+508)), 'diagnostic': [s+600,s+601],
            'optimizer': [1030000000+2*i,1030000001+2*i]})
    assert len({json.dumps(d['body'],sort_keys=True) for d in draws}) == 48
    sources = ['creature_forge/h3_capability.py','scripts/h3_run.py','scripts/h3_analyze.py',
               'docs/H3_EXPERIMENTAL_PROTOCOL.md','creature_forge/hidden_plant.py',
               'creature_forge/phasegait.py','creature_forge/phasegait_init.py',
               'creature_forge/phasegait_fp.py','creature_forge/creature_gen.py',
               'creature_forge/walk_opt.py','creature_forge/recovery.py',
               'creature_forge/challenges.py','creature_forge/locomotion.py','scripts/h1_independent_stdlib.py',
               'creature_forge/morphology.py','creature_forge/contact.py','creature_forge/arena.py',
               'experiments/walk_recovery/r2/selection.json']
    # R2's actual path is resolved from the existing implementation.
    from creature_forge import r2
    sources[-1] = r2.SELECTION.relative_to(ROOT).as_posix()
    sources=sorted(set(sources+['pyproject.toml',history_file]+[p.relative_to(ROOT).as_posix()
        for p in (ROOT/'creature_forge').rglob('*.py')]))
    return {'version':'h3-pilot-v1','draws': draws,'required_per_side':6,'variation':dict(VARIATION_PRESET),
            'historical_body_hashes_checked':sorted(historical_bodies),
            'case_cap_equivalents':25836,'gate_cap_equivalents':240,
            'qualify_cap_equivalents':1536,'total_cap_equivalents':311808,
            'max_batch_hours':3,'cloud_cap_usd':8,'token_factory_cap_usd':0,
            'source_hash_policy':'sha256 of source bytes with CRLF normalized to LF; evidence/plan hashes exact',
            'sources': {p:source_sha(ROOT/p) for p in sources}}


def check_plan(plan):
    if (plan.get('version')!='h3-pilot-v1' or len(plan.get('draws',[]))!=48
        or [plan.get(k) for k in ('case_cap_equivalents','gate_cap_equivalents','qualify_cap_equivalents',
                                 'total_cap_equivalents','max_batch_hours','cloud_cap_usd','token_factory_cap_usd')]
        != [25836,240,1536,311808,3,8,0]):
        raise ValueError('frozen H3 plan schema/budgets differ')
    for p,h in plan['sources'].items():
        if source_sha(ROOT/p) != h: raise ValueError('frozen H3 source differs: '+p)


def seal_unit(root):
    root=Path(root)
    rows=[f'{sha(p)}  {p.relative_to(root).as_posix()}' for p in sorted(root.rglob('*')) if p.is_file()]
    with (root/'SHA256SUMS').open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(rows)+'\n')


def check_unit(root,plan_path,phase):
    root=Path(root);listed={}
    for line in (root/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h,name=line.split('  ',1);p=(root/name).resolve()
        if not p.is_relative_to(root.resolve()) or name in listed:raise ValueError('invalid unit manifest path')
        if sha(p)!=h:raise ValueError('unit evidence hash mismatch: '+name)
        listed[name]=h
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    if set(listed)!=actual:raise ValueError('unit manifest coverage mismatch')
    r=json.loads((root/'result.json').read_text(encoding='utf-8'))
    if r['plan_sha256']!=sha(plan_path) or r['phase']!=phase:raise ValueError('unit identity drift')
    return r


def qualified_ids(plan,q):
    """Validate independent-lineage membership and balanced side labels."""
    accepted=q.get('accepted',{})
    ids=sum(accepted.values(),[])
    if (set(accepted)!={'left','right'} or any(len(accepted[s])!=6 for s in accepted)
        or len(set(ids))!=12):raise ValueError('six unique lineages per side required')
    byid={d['id']:d for d in plan['draws']}
    for side,items in accepted.items():
        if any(i not in byid or byid[i]['side']!=side for i in items):raise ValueError('qualification lineage/side drift')
    return ids


def require_authorization(path, plan_path, phase, campaign):
    if not path: raise ValueError('fresh human H3 authorization receipt required')
    a = json.loads(Path(path).read_text(encoding='utf-8'))
    now = time.time()
    if (a.get('study') != 'h3-pilot-v1' or a.get('protocol_sha256') != sha(plan_path)
        or phase not in a.get('phases', []) or not a.get('human_message_reference')
        or not 0 <= now-a['authorized_epoch'] <= 86400
        or not now < a['deadline_epoch'] <= a['authorized_epoch']+3*3600
        or a.get('cloud_cap_usd') != 8 or a.get('token_factory_cap_usd') != 0
        or Path(a.get('campaign_directory','')).resolve() != Path(campaign).resolve()):
        raise ValueError('authorization is missing, stale, mismatched or outside the frozen envelope')
    return a


def rich_job(job):
    import numpy as np
    from creature_forge import hidden_plant as hp
    from creature_forge.h3_capability import controller_scope, split_vector
    from creature_forge.optimize import jsonable
    base,gains = split_vector(job['vector'])
    if gains is None:
        tr = hp.plant_rollout(job['plant'],job['body'],base,job['seed'],duration=job['duration'],rich=True)
        samples=[]
    else:
        with controller_scope(gains,log=True) as made:
            tr = hp.plant_rollout(job['plant'],job['body'],base,job['seed'],duration=job['duration'],rich=True)
        samples=made[0].samples
    for key in ('t','x','z','pitch','q','qd','tau','demand'):
        if not np.all(np.isfinite(tr[key])):raise ValueError('nonfinite physical trace: '+key)
    # Null represents undefined rich fields (e.g. COP while airborne), never a success.
    clean = {k: np.where(np.isfinite(v), v, np.nan).tolist() for k,v in tr.items() if k!='meta'}
    def nulls(x):
        if isinstance(x,list): return [nulls(v) for v in x]
        return None if isinstance(x,float) and not np.isfinite(x) else x
    return {'trace': {k:nulls(v) for k,v in clean.items()}, 'meta':jsonable(tr['meta']),
            'controller_pre_step':jsonable(samples)}


def gate(plan,pool):
    # New draw, no qualification/search. Exact raw trace equality at zero gains.
    from creature_forge import recovery as rc
    from creature_forge.h3_capability import seed_job
    rows=[]
    d=plan['draws'][0]
    for plant in ({},d['plant']):
        for seed in d['qual_healthy10'][:3]:
            jobs=[{'body':d['body'],'vector':d['vector']+extra,'plant':plant,'seed':seed,'duration':10.}
                  for extra in ([],[0.,0.])]
            rr=[r for _,r in pool.imap(rich_job,jobs)]
            if rr[0]['trace'] != rr[1]['trace']: raise RuntimeError('native zero-gain identity FAIL')
            rows.append({'seed':seed,'plant':plant,'trace_equal':True})
        kwargs={'pool':pool,'job_fn':partial(seed_job,plant=plant)}
        a=rc.run_walk_seeds(d['body'],d['vector'],d['qual_healthy10'][:3],**kwargs)
        b=rc.run_walk_seeds(d['body'],d['vector']+[0.,0.],d['qual_healthy10'][:3],**kwargs)
        if a!=b or any(r.get('error') for r in a+b):raise RuntimeError('native seed-job identity FAIL')
    return {'passed':True,'zero_gain_native':rows,'seed_job_identity':True}


def qualify(plan,pool,out):
    from creature_forge import recovery as rc
    from creature_forge.h3_capability import seed_job
    accepted={'left':[],'right':[]}; records=[]
    for d in plan['draws']:
        if all(len(v)==6 for v in accepted.values()): break
        if len(accepted[d['side']])==6: continue
        healthy10=rc.run_walk_seeds(d['body'],d['vector'],d['qual_healthy10'],pool=pool)
        healthy20=rc.run_walk_seeds(d['body'],d['vector'],d['qual_healthy20'],duration=20,pool=pool)
        damaged=rc.run_walk_seeds(d['body'],d['vector'],d['qual_damaged'],pool=pool,
                                  job_fn=partial(seed_job,plant=d['plant']))
        rows=healthy10+healthy20+damaged
        if any(r.get('error') for r in rows): raise RuntimeError('qualification simulation error')
        keep=(sum(r['walking'] for r in healthy10)>=7 and sum(r['walking'] for r in healthy20)>=7
              and sum(r['walking'] for r in damaged)<=1)
        rec={'id':d['id'],'accepted':keep,'healthy10':healthy10,'healthy20':healthy20,'damaged':damaged}
        save(out/(d['id']+'.json'),rec);records.append(rec)
        if keep: accepted[d['side']].append(d['id'])
    return {'accepted':accepted,'passed':all(len(v)==6 for v in accepted.values()),'records':records}


def case(plan,case_id,pool,out):
    from creature_forge import recovery as rc
    from creature_forge.h3_capability import search,seed_job
    d=next(d for d in plan['draws'] if d['id']==case_id)
    original={'body':d['body'],'vector':d['vector']}
    policies=[]
    for rep in range(2):
        for arm,expanded,budget in [('current',False,3000),('residual',True,3000),('current2x',False,6000)]:
            s=search(d['body'],d['vector'],d['plant'],expanded=expanded,budget=budget,
                     seeds=d['train'][rep],selection=d['select'][rep],noise_seed=d['optimizer'][rep],pool=pool,
                     progress=lambda event,path=out/f'{arm}_{rep}_progress.jsonl':append_event(path,event))
            save(out/f'{arm}_{rep}_search.json',s)
            policies.append((arm,rep,s['candidate']))
    # All candidates frozen before FULL labels. No verifier-driven reselection.
    results=[]
    for arm,rep,candidate in policies:
        panels=[rc.assess(original,candidate,p['validate'],p['confirm'],pool=pool,
                         job_fn=partial(seed_job,plant=d['plant'])) for p in d['panels']]
        if any(p.get('errors') or p['status']=='INCONCLUSIVE_ERROR' for p in panels): raise RuntimeError('verifier inconclusive')
        healthy=rc.run_walk_seeds(candidate['body'],candidate['vector'],d['healthy_guard'],duration=20.,
                                 pool=pool,job_fn=seed_job)
        if any(r.get('error') for r in healthy): raise RuntimeError('healthy guard error')
        # Both arms get the same diagnostic wrapper, including current zero gains.
        vector=candidate['vector'] if len(candidate['vector'])==19 else candidate['vector']+[0.,0.]
        jobs=[{'body':d['body'],'vector':vector,'plant':d['plant'],'seed':s,'duration':10.}
              for s in d['diagnostic']]
        for i,r in pool.imap(rich_job,jobs): save(out/f'{arm}_{rep}_trace{i}.json',r)
        rec={'id':case_id,'arm':arm,'rep':rep,'candidate':candidate,'panels':panels,'healthy':healthy}
        save(out/f'{arm}_{rep}_verification.json',rec);results.append(rec)
    return {'id':case_id,'results':results}


def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=('plan','gate','qualify','case'))
    p.add_argument('--plan',default=str(STUDY/'plan.json'));p.add_argument('--out',required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--authorization');p.add_argument('--case')
    p.add_argument('--gate-receipt');p.add_argument('--qualification');p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();out=Path(a.out)
    if a.phase=='plan': save(out,make_plan());print('Plan written; no physics executed');return
    if not a.execute: raise ValueError('execution disabled: explicit --execute and fresh H3 approval required')
    plan=json.loads(Path(a.plan).read_text());check_plan(plan)
    auth=require_authorization(a.authorization,a.plan,a.phase,out)
    if not 1 <= a.workers <= 6: raise ValueError('1..6 workers per shard')
    if a.phase!='gate':
        if Path(a.gate_receipt).resolve()!=(out/'gate/result.json').resolve():raise ValueError('canonical gate receipt required')
        g=check_unit(out/'gate',a.plan,'gate')
        if not g.get('passed') or not g.get('seed_job_identity'): raise ValueError('native gate absent')
    if a.phase=='case':
        if Path(a.qualification).resolve()!=(out/'qualify/result.json').resolve():raise ValueError('canonical qualification receipt required')
        q=check_unit(out/'qualify',a.plan,'qualify')
        if not q.get('passed') or a.case not in qualified_ids(plan,q):
            raise ValueError('12 independent qualified lineages required')
    if a.phase=='case' and a.case not in {d['id'] for d in plan['draws']}: raise ValueError('unknown case')
    out=out/('cases/'+a.case if a.phase=='case' else a.phase)
    out.mkdir(parents=True,exist_ok=False)  # canonical unit directory prevents budget-reset replay
    save(out/'claim.json',{'phase':a.phase,'case':a.case,'plan_sha256':sha(a.plan),'authorization':auth})
    run_started=time.perf_counter()
    def reserve(rollouts,eq):
        if time.time() >= auth['deadline_epoch']-120: raise RuntimeError('shutdown margin reached')
        with (out/'reserved.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'epoch':time.time(),'rollouts':rollouts,'equivalents':eq})+'\n');f.flush();os.fsync(f.fileno())
    from creature_forge.forge_pool import ForgePool
    from creature_forge.h3_capability import BudgetPool
    cap=plan[{'gate':'gate_cap_equivalents','qualify':'qualify_cap_equivalents','case':'case_cap_equivalents'}[a.phase]]
    with ForgePool(max_workers=a.workers) as inner:
        pool=BudgetPool(cap,cap,inner=inner,on_reserve=reserve)
        try:
            if a.phase=='gate': result=gate(plan,pool)
            elif a.phase=='qualify': result=qualify(plan,pool,out)
            else: result=case(plan,a.case,pool,out)
        except Exception as exc:
            save(out/'failure.json',{'phase':a.phase,'case':a.case,'plan_sha256':sha(a.plan),
                'error':f'{type(exc).__name__}: {exc}','rollouts_reserved':pool.rollouts,
                'equivalents_reserved':pool.equivalents,'wall_s':time.perf_counter()-run_started})
            raise
        import mujoco,numpy as np
        result.update({'plan_sha256':sha(a.plan),'phase':a.phase,'rollouts_reserved':pool.rollouts,
                       'equivalents_reserved':pool.equivalents,'wall_s':time.perf_counter()-run_started,
                       'environment':{'python':sys.version,
                       'platform':platform.platform(),'numpy':np.__version__,'mujoco':mujoco.__version__}})
        save(out/'result.json',result)
        seal_unit(out)


if __name__=='__main__': main()
