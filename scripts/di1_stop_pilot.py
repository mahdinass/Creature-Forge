"""Registered engineering amendment: first stopping decision versus one probe.

Uniformly includes every qualified v1 base, never selects on repair outcome.
V1 baseline/journals are retained byte-exact and referenced as baseline evidence.
No new independent bases, learned policy or prospective evaluation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from creature_forge.forge_pool import ForgePool
from di1_study import run_path,sha
from r0_experiment import write_new


def main():
    p=argparse.ArgumentParser();p.add_argument('--prior',required=True);p.add_argument('--out',required=True)
    p.add_argument('--index',type=int,required=True);a=p.parse_args()
    cfg=json.loads(Path('experiments/causal_engineer/dev/di1/pilot_config.json').read_text());base=cfg['bases'][a.index]
    prior=Path(a.prior)/base['base_id'];out=Path(a.out)/base['base_id'];out.mkdir(parents=True,exist_ok=True)
    complete=json.loads((prior/'complete.json').read_text())
    if not complete['eligible']:
        write_new(out/'complete.json',complete);return
    # Exact copies, never rewritten scientific records or fresh independence.
    refs={}
    for name in ('baseline.json','baseline.jsonl','equivalence.json','instance.json','threshold.json','nominal.json'):
        target=out/name
        if target.exists():raise FileExistsError(target)
        shutil.copyfile(prior/name,target);refs[name]=hashlib.sha256(target.read_bytes()).hexdigest()
    write_new(out/'baseline_reference.json',{'prior':str(prior),'source_commit':'1e0f610',
              'files_sha256':refs,'reuse':'same base, seeds, original policy; not another independent observation'})
    inst=json.loads((prior/'instance.json').read_text())
    stop=json.loads(Path('experiments/causal_engineer/dev/di1/stopmap_dev_v1.json').read_text());t0=time.perf_counter()
    with ForgePool(max_workers=6) as pool:
        if a.index==0:
            again=run_path(inst,'baseline',pool,stop)
            original=json.loads((prior/'baseline.json').read_text())
            equal=again['scientific']==original['scientific'] and again['verification']==original['verification']
            write_new(out/'v2_default_equivalence.json',{'equal':equal,'sha':sha([again['scientific'],again['verification']])})
            if not equal:raise ValueError('v2 default changed original science')
        arms={}
        for mode in ('raw_eig','random'):
            r=run_path(inst,mode,pool,stop,out/f'{mode}.jsonl',force_first=True)
            write_new(out/f'{mode}.json',r);arms[mode]={'status':r['verification']['status'],
                'wall_s':r['wall_s'],'probe':(r['first_decision'] or {}).get('selected',{}).get('id')}
    write_new(out/'complete.json',{'base_id':base['base_id'],'eligible':True,'arms':arms,
              'wall_s':time.perf_counter()-t0,'amendment':'v2_stop_or_probe'})
    print(json.dumps({'index':a.index,'arms':arms}),flush=True)


if __name__=='__main__':main()
