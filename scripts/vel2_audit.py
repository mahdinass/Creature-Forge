"""Independent post-run evidence audit; no simulation, fitting or outcome selection."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def read(p):return json.loads(Path(p).read_text())


def audit(study,root):
    study=Path(study);root=Path(root)
    cases=read(study/'stage_a_cases.json');p=read(study/'stage_a_protocol.json')
    result=read(root/'analysis.json');used=set();records=[];eq=0;seed_rows=0
    assert len(cases)==15 and len({c['nominal_body_sha256'] for c in cases})==15
    for c in cases:
        for ss in c['preverification']['seeds'].values():used.update(ss)
    old=set(used)
    counts=collections.Counter();stable=success=fail=0;pair_agree=0;requirement=collections.defaultdict(list)
    for i,c in enumerate(cases):
        vv=[c['original_verification']]
        for j in range(2):
            r=read(root/'panels'/f'{i:02d}_{j}.json');v=r['verification'];vv.append(v)
            assert r['base_id']==c['base_id'] and r['candidate_sha256']==c['candidate_sha256'] and r['panel']==j
            assert v['rule']=='full_recovery_v1' and not v.get('errors') and v['status']!='INCONCLUSIVE_ERROR'
            assert v['seeds']==c['panels'][j]
            for ss in v['seeds'].values():
                assert len(ss)==24 and not set(ss)&used
                used.update(ss)
            for arm in ('original','candidate'):
                rr=v['validation'][arm]
                assert [r['seed'] for r in rr]==v['seeds']['validate']
                assert len(rr)==24 and all(r['outcome']!='ERROR' and not r.get('error') for r in rr)
                assert all(r['walking']==(r['outcome']=='PASS') for r in rr)
                seed_rows+=len(rr)
            from creature_forge.verdict import verdict
            a,b=v['validation']['original'],v['validation']['candidate']
            rec=verdict('walk',[x['score'] for x in a],[x['score'] for x in b],
                        original_pass=[x['walking'] for x in a],candidate_pass=[x['walking'] for x in b])
            assert rec==v['validation']['verdict']
            improve=rec['status']=='VERIFIED_IMPROVEMENT'
            walking=sum(x['walking'] for x in b)>=20
            assert v['confirmation']['run']==(improve and walking)
            if v['confirmation']['run']:
                conf=v['confirmation'];rr=conf['per_seed']
                assert [r['seed'] for r in rr]==v['seeds']['confirm'] and len(rr)==24
                assert all(r['outcome']!='ERROR' and not r.get('error') for r in rr)
                from creature_forge.recovery import _confirm
                assert _confirm(c['candidate'],rr)==conf
                seed_rows+=len(rr)
                full=conf['passed']
            else:full=False
            expected='FULL_RECOVERY' if full else ('PARTIAL_IMPROVEMENT' if improve else 'NOT_RECOVERED')
            assert v['status']==expected
            nconf=24 if v['confirmation']['run'] else 0
            assert v['rollouts']=={'validation':48,'confirmation':nconf,'confirmation_rollout_equivalents':nconf*2.0}
            eq+=48+2*nconf;counts[v['status']]+=1
            records.append({'base_id':c['base_id'],'panel':j,'wall_s':r['wall_s'],'equivalents':48+2*nconf})
        labels=[v['status']=='FULL_RECOVERY' for v in vv]
        stable+=len(set(labels))==1;success+=all(labels);fail+=not any(labels)
        for a,b in ((0,1),(0,2),(1,2)):
            pair_agree+=labels[a]==labels[b]
            for key in ('improvement','validation_walking'):
                f=lambda v: v['validation']['verdict']['status']=='VERIFIED_IMPROVEMENT' if key=='improvement' else v['validation']['aggregate']=='PASS'
                requirement[key].append(f(vv[a])==f(vv[b]))
    checks={'complete_error_free':len(list((root/'panels').glob('*.json')))==30,
      'three_panel_agreement':stable>=12,'pairwise_agreement':pair_agree/45>=.85,
      'validation_requirements':all(sum(v)/len(v)>=.8 for v in requirement.values()),
      'persistent_failure_support':fail>=3,'persistent_success_support':success>=3}
    assert checks==result['gate_checks'] and all(checks.values())==result['stage_a_gate']
    assert eq==result['new_rollout_equivalents'] and stable==result['three_panel_agreement_bases']
    assert len(used)-len(old)==1440
    assert (root/'analysis.json').read_bytes()==(root/'analysis_repeat.json').read_bytes()
    verified=0
    for line in (root/'SHA256SUMS').read_text().splitlines():
        h,n=line.split('  ',1)
        assert hashlib.sha256((root/n).read_bytes()).hexdigest()==h,n
        verified+=1
    return {'independent_gate_matches':True,'gate':all(checks.values()),'gate_checks':checks,
      'all_three_agree':stable,'persistent_full':success,'persistent_nonfull':fail,
      'new_status_counts':dict(counts),'new_seed_rows':seed_rows,'new_equivalents':eq,
      'source_manifest_entries_verified':verified,'byte_exact_native_analysis_repeat':True,
      'verdict_and_confirmation_replayed_without_physics':True,'timing':records,
      'all_new_panel_seeds_disjoint':True,'n_independent_known_lineages':15,'new_lineages':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',default='experiments/causal_engineer/dev/vel2')
    p.add_argument('--root',default='artifacts/vel2_stage_a');p.add_argument('--out',required=True);a=p.parse_args()
    r=audit(a.study,a.root)
    from r0_experiment import write_new
    write_new(a.out,r);print(json.dumps({k:v for k,v in r.items() if k!='timing'},indent=2))
