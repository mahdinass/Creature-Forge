"""Read-only H3 evidence inventory. Stdlib only; explicit development paths.

No physics, fitting, candidate generation, sealed loaders or cloud operations.
"""
import argparse
import collections as C
import hashlib
import json
import statistics
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
FULL='FULL_RECOVERY'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def audit(root=ROOT,prior_root=None):
    root=Path(root);sources={}
    p=root/'scripts/h3_saved_audit.py'
    sources['scripts/h3_saved_audit.py']={'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size}
    def read(path):
        p=root/path;raw=p.read_bytes();sources[path]={'sha256':digest(raw),'bytes':len(raw)}
        return json.loads(raw)
    matrix='experiments/causal_engineer/dev/rl1/rl1_matrix.tgz'
    raw=(root/matrix).read_bytes()
    assert digest(raw)=='9b740a946231d7bf98967d28a641de320831e346048a59da5eaff89434c96b2a'
    sources[matrix]={'sha256':digest(raw),'bytes':len(raw)}
    with tarfile.open(root/matrix) as t:
        for line in t.extractfile('SHA256SUMS').read().decode().splitlines():
            h,n=line.split(None,1);assert digest(t.extractfile(n.lstrip('*').strip()).read())==h
        cells=[json.loads(line) for line in t.extractfile('matrix.jsonl')]
    byid=C.defaultdict(list)
    for c in cells:byid[c['instance_id']].append(c)
    families=C.defaultdict(lambda:C.Counter())
    for iid,cs in byid.items():
        f=families[cs[0]['family']];f['instances']+=1
        f['any_full']+=any(c['status']==FULL for c in cs)
        f['no_full']+=not any(c['status']==FULL for c in cs)
    rl1={'cells':len(cells),'instances':len(byid),'bases':len({c['base_id'] for c in cells}),
         'no_full_instances':sum(not any(c['status']==FULL for c in cs) for cs in byid.values()),
         'train4_full':sum(c['status']==FULL and c['train_walking']==4 for c in cells),
         'train4_total':sum(c['train_walking']==4 for c in cells),'families':dict(families)}
    cases=read('experiments/causal_engineer/dev/repair_strategy_r0/cases.json')
    cby={c['instance_id']:c for c in cases}
    rawdir=root/'artifacts/r0_ops/r0_run_20261025'
    manifest={n:h for h,n in (line.split('  ',1) for line in (rawdir/'SHA256SUMS').read_text().splitlines())}
    rows=[];arms=C.defaultdict(lambda:C.Counter());restarts=C.Counter()
    for p in sorted((rawdir/'units').glob('*.json')):
        assert digest(p.read_bytes())==manifest['units/'+p.name]
        r=read(p.relative_to(root).as_posix());rows.append(r)
        a=arms[r['action']+'/'+r['objective']];a['runs']+=1;a['full']+=r['verification']['status']==FULL
        a['policy_rollouts']+=r['result']['ledger']['used']
        restarts['searches']+=len(r['result']['searches'])
        restarts['optimizer_restarts']+=sum(len(s['restarts']) if isinstance(s['restarts'],list) else s['restarts'] for s in r['result']['searches'])
    assert len(rows)==324
    # H1's complete640 candidates x3 panels. Do not invent missing physiology.
    study='experiments/causal_engineer/dev/h1/'
    for stage in ('a','b'):
        d=root/f'artifacts/h1_ops/h1_stage_{stage}_v1'
        for line in (d/'SHA256SUMS').read_text().splitlines():
            h,n=line.split(None,1);assert digest((d/n.strip().lstrip('*')).read_bytes())==h
    candidates=read(study+'candidates.json');cc={c['key']:c for c in candidates}
    known=read(study+'known.json')
    panel=C.defaultdict(list);primary=C.Counter();missing_rich=0
    requirement=C.Counter();family_results=C.defaultdict(lambda:C.Counter())
    original={}
    for r in rows:
        z=r['result'];iid=r['instance_id'];v=r['verification']
        bodyhash=digest(json.dumps(z['design'],sort_keys=True,separators=(',',':')).encode())
        k=next(c['key'] for c in candidates if c['instance_id']==iid and c['candidate_sha256']==bodyhash)
        original[k]=v
    for p in sorted((root/'artifacts/h1_ops/h1_stage_a_v1/outcomes').glob('*.json')):
        r=read(p.relative_to(root).as_posix());original[r['key']]=r['verification']
    assert len(original)==640
    for k,v in original.items():panel[k].append(v)
    for p in sorted((root/'artifacts/h1_ops/h1_stage_b_v1/outcomes').glob('*.json')):
        r=read(p.relative_to(root).as_posix());panel[r['candidate_key']].append(r['verification'])
    for k,vv in panel.items():
        assert len(vv)==3
        c=cc[k];f=family_results[cby[c['instance_id']]['family']]
        f['candidates']+=1;f['all_three_full']+=all(v['status']==FULL for v in vv)
        f['any_full_panel']+=any(v['status']==FULL for v in vv)
        for v in vv:
            f['candidate_panels']+=1;f['full_panels']+=v['status']==FULL
            requirement['improvement_failure']+=v['validation']['verdict']['status']!='VERIFIED_IMPROVEMENT'
            requirement['validation_walking_failure']+=v['validation']['aggregate']!='PASS'
            if v['confirmation']['run']:
                requirement['confirmation_observed']+=1
                for name,x in v['confirmation']['checks'].items():requirement['confirmation_'+name+'_failure']+=not x['passed']
            else:requirement['confirmation_missing']+=1
            for row in v['validation']['candidate']:
                primary[row.get('label','UNKNOWN')]+=1
                missing_rich+=not all(name in row for name in ('demand','tau','phase','q','qd','slip'))
    baseopp=[]
    for case in cases:
        keys=[k for k,c in cc.items() if c['base_id']==case['base_id']]
        baseopp.append({'base_id':case['base_id'],'family':case['family'],'candidate_count':len(keys),
          'any_candidate_any_panel_full':any(any(v['status']==FULL for v in panel[k]) for k in keys),
          'any_candidate_all_three_full':any(all(v['status']==FULL for v in panel[k]) for k in keys)})
    # Older development controller-class evidence: do not open confirmatory raw.
    mdir='experiments/walk_recovery/oracle/results/m1/'
    mm=read(mdir+'MANIFEST.json')['sha256']
    for n,h in mm.items():assert digest((root/mdir/n).read_bytes())==h
    m1=read(mdir+'summary.json')
    m1counts={k:len(v) for k,v in m1['recovered_by'].items()}
    m1rows=[]
    for p in sorted((root/mdir).glob('shard*.jsonl')):
        sources[p.relative_to(root).as_posix()]={'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size}
        m1rows += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    raw_m1=C.defaultdict(set)
    for r in m1rows:
        cond=r['condition']['id'];raw_m1[cond]
        last=r['checkpoints'][max(r['checkpoints'],key=int)]
        if last['status']==FULL:raw_m1[cond].add(r['creature'])
    assert {k:len(v) for k,v in raw_m1.items()}==m1counts
    # Recorded studies with richer evidence not present locally remain qualified.
    prior={}
    for name,paths in {
      'EM1':['experiments/causal_engineer/dev/em1/results/gate.json'],
      'DI1':['experiments/causal_engineer/dev/di1/results/gate.json'],
      'VEL1':['experiments/causal_engineer/dev/vel1/results/feasibility.json'],
      'VEL2':['experiments/causal_engineer/dev/vel2/results/native/analysis.json']}.items():
        prior[name]={p:read(p) for p in paths if (root/p).exists()}
    # Recompute published VEL1 base-equal Brier from saved cross-fit predictions.
    pp=read('experiments/causal_engineer/dev/vel1/results/predictions.json')
    def brier(name):
        gg=C.defaultdict(list)
        for r in pp:
            if not r['apparent']:continue
            pred=r['predictions'][name]
            loss=sum((p-r['failed'])**2 for p in pred)/len(pred) if isinstance(pred,list) else (pred-r['failed'])**2
            gg[r['group']].append(loss)
        return sum(sum(v)/len(v) for v in gg.values())/len(gg)
    prior['VEL1']={'rows':len(pp),'apparent':sum(r['apparent'] for r in pp),
      'apparent_base_groups':len({r['group'] for r in pp if r['apparent']}),
      'base_equal_brier':{k:brier(k) for k in ('V1_physical','V2_experience','V3_shuffled')}}
    signatures=read('experiments/causal_engineer/dev/vel1/results/fresh_v5_rows.json')
    pred_by_id={r['id']:r for r in pp}
    prior['saved_initial_physical_signatures']={}
    for failed in (0,1):
        selected=[r for r in signatures if r['apparent'] and pred_by_id[r['id']]['failed']==failed]
        medians={}
        for key in ('initial_ankle_saturation','initial_slip','initial_capture','initial_walking'):
            values=[r['features'][key] for r in selected if r['features'].get(key) is not None]
            medians[key]={'n':len(values),'median':statistics.median(values) if values else None}
        prior['saved_initial_physical_signatures']['failed' if failed else 'not_failed']={
          'instances':len(selected),'bases':len({r['group'] for r in selected}),'features':medians,
          'interpretation':'Descriptive initial-fault probe summaries, not candidate control traces or causal attribution.'}
    vc=read('experiments/causal_engineer/dev/vel2/stage_a_cases.json');stable=0
    for i,c in enumerate(vc):
        states=[c['original_verification']['status']==FULL]
        for panel_id in range(2):
            v=read(f'experiments/causal_engineer/dev/vel2/results/native/panels/{i:02}_{panel_id}.json')
            assert v['base_id']==c['base_id'];states.append(v['verification']['status']==FULL)
        stable+=len(set(states))==1
    prior['VEL2_raw_recount']={'independent_bases':len(vc),'stable_three_panels':stable}
    if prior_root:
        prior_root=Path(prior_root)
        def old(path):
            raw=(prior_root/path).read_bytes()
            sources['prior-worktree/'+path]={'sha256':digest(raw),'bytes':len(raw)}
            return json.loads(raw)
        er=old('artifacts/em1_ops/em1_g0_v2/paired_aggregate_rows.json')
        eg=C.defaultdict(list)
        for r in er:eg[r['instance_id']].append(r)
        regret=[]
        for rr in eg.values():
            original=[r for r in rr if r['original_submission']]
            assert len(original)==1
            regret.append(max(r['observed'] for r in rr)-original[0]['observed'])
        prior['EM1_raw_recount']={'rows':len(er),'independent_bases':len({r['base'] for r in er}),
            'measurement_units':len(eg),'mean_predicted_minus_observed':sum(r['predicted']-r['observed'] for r in er)/len(er),
            'observed_walking_regret_mean':sum(regret)/len(regret),
            'unlabelled_alternative_full':sum(not r['full_known'] for r in er)}
        dr={}
        for version in ('v1','v2'):
            base='artifacts/di1_ops/extracted/di1_pilot_'+version
            counts=C.Counter();states={}
            for p in sorted((prior_root/base).glob('*/complete.json')):
                bid=p.parent.name
                complete=old(f'{base}/{bid}/complete.json')
                if not complete.get('eligible',True):
                    counts['ineligible']+=1;continue
                states[bid]={}
                for arm in ('baseline','raw_eig','random'):
                    r=old(f'{base}/{bid}/{arm}.json');full=r['verification']['status']==FULL
                    counts[arm+'_full']+=full;states[bid][arm]=r['verification']['status']
                counts['bases']+=1
            dr[version]={'counts':dict(counts),'per_base_status':states}
        prior['DI1_raw_recount']=dr
    else:prior['external_raw']='EM1/DI1 raw not supplied; pass --prior-root to inspect existing prior workspace'
    return {'version':'h3-saved-audit-v1','new_physics':0,'new_training':0,'sealed_raw_read':False,
      'rl1':rl1,'r0':{'units':len(rows),'bases':18,'arms':dict(arms),'optimizer':dict(restarts)},
      'h1':{'candidate_identities':640,'candidate_panels':1920,'bases':18,'family_support':dict(family_results),
            'base_support':baseopp,'requirement_failures_overlap':dict(requirement),
            'validation_primary_labels':dict(primary),'validation_candidate_rows_without_full_control_traces':missing_rich,
            'warning':'Primary labels overlap/priority-mask causes. No demand/reference/phase traces imply no causal controller diagnosis.'},
      'm1':{'raw_units':len(m1rows),'bases':12,'final_any_replicate_full_by_class':m1counts,
            'warning':'Unequal replicate counts and optimizer noise; old development association, not a new causal result.'},
      'prior_small_results':prior,'sources':sources}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--prior-root');a=p.parse_args();dest=Path(a.out)
    if dest.exists():raise ValueError('refusing overwrite')
    r=audit(prior_root=a.prior_root);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('x',encoding='utf-8',newline='\n') as f:json.dump(r,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({k:r[k] for k in ('version','new_physics','rl1','r0','m1')},indent=2))
