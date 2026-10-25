"""Uniform engineering replay of ALL pilot qualification attempts.

The original HDB threshold helper retains aggregate walking counts only. This
independent audit captures every seed result, including errors, without changing
any frozen enrollment or scientific path. Never replaces a recorded outcome.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from creature_forge import hdb_bench as hb, hidden_plant as hp
from creature_forge.decision_trace import Journal,TracePool
from creature_forge.forge_pool import ForgePool
from di1_study import CAMPAIGN,science
from di1_analyze import audit_trace
from r0_experiment import write_new


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    root=Path(a.root);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads(Path('experiments/causal_engineer/dev/di1/pilot_config.json').read_text())
    proofs=[]
    with ForgePool(max_workers=6) as underlying:
        for base in cfg['bases']:
            d=root/base['base_id'];journal=Journal(out/f"{base['base_id']}.jsonl");pool=TracePool(underlying,journal)
            try:
                nominal=json.loads((d/'nominal.json').read_text())
                rows=hp.walk_seeds({},base['body'],base['vector'],nominal['seeds'],pool=pool)
                if science(rows)!=science(nominal['rows']):raise ValueError('nominal replay mismatch')
                if (d/'threshold.json').exists():
                    th=json.loads((d/'threshold.json').read_text())
                    again=hb.threshold(base,th['family'],th['variant'],pool=pool)
                    if science(again)!=science(th):raise ValueError('threshold replay mismatch')
                if (d/'instance.json').exists():
                    inst=json.loads((d/'instance.json').read_text());again=hb.check_eligibility(inst,pool=pool)
                    if again!=inst:raise ValueError('faulty qualification replay mismatch')
            finally:journal.close()
            audit=audit_trace(out/f"{base['base_id']}.jsonl")
            if audit['errors']:raise ValueError('generation physics error')
            proofs.append({'base':base['base_id'],'exact_scientific_replay':True,**audit})
    write_new(out/'proofs.json',{'attempts':len(proofs),'all_equal':True,'physics_errors':0,'proofs':proofs,
                                'purpose':'uniform reproducibility audit; no replacement or additional independent bases'})
    print(json.dumps({'attempts':len(proofs),'all_equal':True,'jobs':sum(p['jobs'] for p in proofs)}))


if __name__=='__main__':main()
