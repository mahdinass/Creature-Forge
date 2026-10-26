"""Independent per-seed H1 audit; never simulates or fits a model."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import h1_counterfactual as h


def check(v,c):
    if v.get('errors') or v['status']=='INCONCLUSIVE_ERROR':
        raise ValueError('simulator error is not physical failure')
    assert v['rule']=='full_recovery_v1' and v['seeds']==c['seeds'] and v['variation']==c['variation']
    a,b=v['validation']['original'],v['validation']['candidate']
    for rr in (a,b):
        assert len(rr)==24 and [r['seed'] for r in rr]==c['seeds']['validate']
        assert all(r['outcome']!='ERROR' and not r.get('error') for r in rr)
        assert all(r['walking']==(r['outcome']=='PASS') for r in rr)
    from creature_forge.verdict import verdict
    rec=verdict('walk',[r['score'] for r in a],[r['score'] for r in b],
                original_pass=[r['walking'] for r in a],candidate_pass=[r['walking'] for r in b])
    assert rec==v['validation']['verdict']
    walking=sum(r['walking'] for r in b)>=20
    assert walking==(v['validation']['aggregate']=='PASS')
    assert v['validation']['walking_frac']==sum(r['walking'] for r in b)/24
    improve=rec['status']=='VERIFIED_IMPROVEMENT'
    conf=v['confirmation'];assert conf['run']==(improve and walking)
    if conf['run']:
        rr=conf['per_seed'];assert len(rr)==24 and [r['seed'] for r in rr]==c['seeds']['confirm']
        assert all(r['outcome']!='ERROR' and not r.get('error') for r in rr)
        from creature_forge.recovery import _confirm
        assert _confirm(c['candidate'],rr)==conf
    expected=h.FULL if conf.get('passed') else ('PARTIAL_IMPROVEMENT' if improve else 'NOT_RECOVERED')
    assert v['status']==expected
    n=24 if conf['run'] else 0
    assert v['rollouts']=={'validation':48,'confirmation':n,'confirmation_rollout_equivalents':2*n}
    return 48+2*n


def audit(study,out):
    p,cc,pairs,known=h.load(study);out=Path(out)
    assert {f.stem for f in (out/'outcomes').glob('*.json')}==set(p['missing_keys'])
    eq=0
    for k in p['missing_keys']:
        row=h.read(out/'outcomes'/f'{k}.json')
        assert row['key']==k and row['candidate_sha256']==cc[k]['candidate_sha256']
        eq+=check(row['verification'],cc[k])
    result=h.read(out/'analysis.json');assert h.analyze(study,out)==result
    # Independent count of each original pair's binary oracle gain.
    full={k:v['status']==h.FULL for k,v in known.items()}
    full.update({k:h.read(out/'outcomes'/f'{k}.json')['verification']['status']==h.FULL for k in p['missing_keys']})
    missed=[];reverse=[]
    for pair in pairs:
        a,b=[full[pair['keys'][i]] for i in (pair['selected'],1-pair['selected'])]
        if b and not a:missed.append(pair['base_id'])
        if a and not b:reverse.append(pair['base_id'])
    assert len(missed)==result['missed_full_screens'] and len(reverse)==result['reverse_screens']
    assert len(set(missed))==result['missed_full_bases']
    gain=len(missed)/324 # exactly 18 screens on every base
    gate=len(set(missed))>=3 and gain>=.05
    assert gate==(result['stage_a_signal']=='ADVANCE_TO_B')
    assert eq==result['new_equivalents'] and eq<=30720
    return {'independent_gate_matches':True,'verdict_confirmation_replayed':320,
            'new_equivalents':eq,'gate':gate,'source_hashes':h.validate_sources(study)}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--study',default=str(h.STUDY));ap.add_argument('--out',required=True)
    a=ap.parse_args();r=audit(a.study,a.out);h.write_new(Path(a.out)/'independent_audit.json',r);print(r)
