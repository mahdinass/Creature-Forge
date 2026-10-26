"""Reconstruct screened R0 designs from saved search winners/tail coordinates; no imports of project modules."""
import ast
import collections as C
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
if '--out' in sys.argv:
    OUT=(ROOT/Path(sys.argv[sys.argv.index('--out')+1])).resolve()
    assert OUT.is_relative_to(ROOT/'artifacts')
    OUT.mkdir(exist_ok=False)

def literal(path,name):
    tree=ast.parse((ROOT/path).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):return ast.literal_eval(node.value)
    raise ValueError(name)

def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

NAMES=literal('creature_forge/r3.py','PARAM_NAMES')+('fp_kd','fp_kv')
CTRL=literal('creature_forge/phasegait.py','BOUNDS')|literal('creature_forge/phasegait_init.py','INIT_BOUNDS')|literal('creature_forge/phasegait_fp.py','FP_BOUNDS')
BODY=literal('creature_forge/morphology.py','BOUNDS')

def decode(start,space,x):
    # Literal numerical transformation in pinned walk_opt.decode/_log_interval;
    # full_body adds explicit right-leg fields and pose, and r2.reflect folds x.
    b=dict(start['body']);v=list(start['vector'])
    for k in ('thigh_length','shank_length','foot_length'):
        if b.get(k+'_r') is None:b[k+'_r']=b[k]
    b['pose']=list(b.get('pose') or [0.]*7)
    if len(v)==15:v += [0.,0.]
    u=[a%2 if a%2<=1 else 2-a%2 for a in x]
    for j,p in enumerate(space['ctrl_params']):
        lo,hi=CTRL[p];v[NAMES.index(p)]=min(hi,max(lo,lo+(hi-lo)*u[j]))
    k=len(space['ctrl_params'])
    for j,p in enumerate(space['body_params']):
        fields=(p,p+'_r') if p in ('thigh_length','shank_length','foot_length') else (p,)
        lb,hb=BODY[p];lo=math.log(space['body_ratio'][0]);hi=math.log(space['body_ratio'][1])
        for f in fields:lo=max(lo,math.log(lb/float(b[f])));hi=min(hi,math.log(hb/float(b[f])))
        lo+=1e-9;hi-=1e-9
        ratio=math.exp(lo+float(u[k+j])*(hi-lo))
        for f in fields:b[f]=float(b[f])*ratio
    return {'body':b,'vector':[float(z) for z in v]}

def main():
    counts=C.Counter();failures=[];recovered={};rows=[]
    for p in sorted((ROOT/'artifacts/r0_ops/r0_run_20261025/units').glob('*.json')):
        r=json.loads(p.read_text());z=r['result'];search={s['source']:s for s in z['searches']}
        rejected={f['tail'] for f in z['refusals'] if 'tail' in f}
        tailids=[i for i in range(z['tail_candidates']) if i not in rejected]
        assert len(tailids)==len(z['tail_log'])
        tails=dict(zip(tailids,z['tail_log']))
        for i,s in enumerate(z['selection']):
            source=s['source']
            if source in search:
                best=search[source]['best'];d={k:best[k] for k in ('body','vector')};kind='search_winner'
            else:
                assert source.startswith('tail:')
                log=tails[int(source[5:])];plan=z['tail_plans'][log['plan']]
                space=next(t['space'] for t in z['searches'] if t['groups']==plan['groups'])
                d=decode(plan['start'],space,log['x']);kind='tail'
            ok=digest(d)==s['design_hash'];counts[kind+'_entries']+=1;counts[kind+'_hash_exact']+=ok
            if not ok:failures.append({'unit':r['unit_id'],'slot':i,'source':source,'selected':i==z['selected']})
            else:recovered[(r['instance_id'],s['design_hash'])]=d
            rows.append({'unit':r['unit_id'],'slot':i,'kind':kind,'hash_exact':ok,'selected':i==z['selected']})
    result={'counts':dict(counts),'failed_entries':failures,'distinct_exact_candidates':len(recovered),
            'note':'Pure source-derived numerical reconstruction; no physics, no new candidate generation, no outcome inference.'}
    for name,value in [('reconstruction.json',result),('reconstructed_candidates.json',[{'iid':k[0],'candidate_sha256':k[1],'design':v} for k,v in recovered.items()])]:
        with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,sort_keys=True,separators=(',',':'));f.write('\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
