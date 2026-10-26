"""Independent Stage B row/verdict/confirmation/seed and gate audit."""
import argparse
import copy
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import h1_reliability as b
import h1_audit as a
h=b.h


def audit(study,stage_a,out):
    p,jobs=b.load(study);_,cc,pairs,_=h.load(h.STUDY);out=Path(out)
    assert len(jobs)==1280 and len({j['key'] for j in jobs})==1280
    assert {f.stem for f in (out/'outcomes').glob('*.json')}=={j['key'] for j in jobs}
    old={s for c in cc.values() for ss in c['seeds'].values() for s in ss}
    new={};eq=0;full={}
    for job in jobs:
        k=job['candidate_key'];c=copy.deepcopy(cc[k]);c['seeds']=job['seeds']
        r=h.read(out/'outcomes'/f"{job['key']}.json")
        assert all(r[n]==job[n] for n in job)
        assert r['candidate_sha256']==c['candidate_sha256']
        for role,ss in job['seeds'].items():
            assert not old&set(ss)
            for s in ss:
                owner=(c['base_id'],job['panel'],role)
                if s in new:assert new[s]==owner
                new[s]=owner
        eq+=a.check(r['verification'],c);full[k,job['panel']]=r['verification']['status']==h.FULL
    assert len(new)==1728==p['new_unique_seeds']
    result=h.read(out/'analysis.json');assert b.analyze(study,stage_a,out)==result
    assert eq==result['new_equivalents'] and eq<=122880
    # Recompute fresh-panel oracle without using analyzer summaries.
    opportunities=0
    for pair in pairs:
        selected=pair['keys'][pair['selected']];alt=pair['keys'][1-pair['selected']]
        opportunities+=sum(full[alt,j] and not full[selected,j] for j in (1,2))
    assert abs(opportunities/648-result['fresh_panel_base_equal_oracle_headroom'])<1e-12
    return {'independent_analysis_matches':True,'new_assessments_checked':1280,'new_unique_seeds':len(new),
      'new_equivalents':eq,'all_verdicts_confirmation_replayed':True,'all_new_panels_disjoint':True}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--study',default=str(b.STUDY));ap.add_argument('--stage-a',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
    r=audit(args.study,args.stage_a,args.out);h.write_new(Path(args.out)/'independent_audit.json',r);print(r)
