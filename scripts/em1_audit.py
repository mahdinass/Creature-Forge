"""EM-1 G0 measurement audit. No learner, sealed loader or invented physics.

Only named, pre-existing development v5 records are accepted. Recomputed twin
forecasts are retrospective measurements under the frozen diagnostic posterior,
not a claim that the original forecast was logged prospectively.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from r0_experiment import write_new, canonical  # immutable stdlib publication

VERSION = 'em1_g0_audit_v1'
ALLOWED = ('fresh_A1c5.jsonl', 'vs5_A1c.jsonl')
FAMILIES = ('pitch_sensor_bias','payload_offset','low_ground_friction','short_feet',
            'actuator_weakness','one_side_weakness','heavy_torso','feedback_gain_loss','clock_fault')


def sha(b): return hashlib.sha256(b).hexdigest()


def design(d):
    return {'body': d['body'], 'vector': d['vector']}


def prepare(records_root, out):
    """Read-only source audit; gold observations never enter the predictor input."""
    out = Path(out)
    jobs, sources, counts = [], {}, collections.Counter()
    episodes, bases, families = set(), set(), set()
    for name in ALLOWED:
        p = Path(records_root)/name
        raw = p.read_bytes()
        sources[name] = {'sha256':sha(raw),'bytes':len(raw)}
        for lineno,line in enumerate(raw.splitlines(),1):
            r = json.loads(line)
            counts['source_rows'] += 1
            if 'engine' not in r:
                counts['ineligible_rows'] += 1
                continue
            if r['family'] not in FAMILIES or r.get('provenance') != 'NO_AI':
                raise ValueError('not an approved non-LLM single-mechanism dev record')
            e = r['engine']
            if e['version'] != 'belief_engine_v5' or any(x['kind']=='check' for x in e['experiments']):
                raise ValueError('posterior may have assimilated the repair outcome')
            iid = r['instance_id']
            if iid in episodes:
                raise ValueError('duplicate independent episode source')
            episodes.add(iid); bases.add(iid.rsplit(':',2)[0]); families.add(r['family'])
            ds = {d['index']:d for d in r['designs']}
            if 0 not in ds:
                raise ValueError('missing nominal design')
            # v5 keeps final diagnostic particles unchanged throughout repair.
            top = e['history'][-1]['top']
            parts = {p['pid']:p for p in e['particles']}
            if not top or any(t['pid'] not in parts for t in top):
                raise ValueError('pre-repair posterior cannot be reconstructed')
            hyps=[]; mass=0.
            # Recompute full-precision v5 posterior, not rounded history weights.
            ps=sorted(e['particles'],key=lambda p:-p['loglik'])
            maximum=ps[0]['loglik']
            norm=sum(math.exp(p['loglik']-maximum) for p in ps)
            for part in ps:
                weight=math.exp(part['loglik']-maximum)/norm
                hyps.append({'deviation':part['deviation'],'weight':weight})
                mass+=weight
                if mass>=.8 or len(hyps)>=3:break
            obs=next(x for x in e['experiments'] if x['kind']=='observe')
            # Audit baseline chronology: repair does not add diagnostic snapshots.
            if any('check@' in h['label'] for h in e['history']):
                raise ValueError('outcome-updated posterior cannot be used')
            checks={}
            for step in r['repair']['log']:
                idx=step.get('design')
                if idx not in ds:raise ValueError('repair references missing design')
                if step.get('check16') is not None: n,y=16,step['check16']
                elif step.get('check') is not None: n,y=8,step['check']
                else:continue
                if isinstance(y,bool) or not isinstance(y,int) or not 0<=y<=n:
                    raise ValueError('invalid measured walking count')
                if idx in checks and checks[idx][0]>=n:continue
                checks[idx]=(n,y)
            counts['original_final_verified']+=int(bool(r.get('verification')))
            counts['saved_particle_prediction_cache']+=int(any('seen' in p for p in e['particles']))
            for idx,(n,y) in sorted(checks.items()):
                # Verify the saved ledger really charged this exact robustness check.
                if not any(l['item']=='robustness_check' and l['detail'].get('design')==idx and l['detail'].get('n')==n for l in e['ledger']['lines']):
                    raise ValueError('check has no matching physical ledger entry')
                predictor={'nominal':design(ds[0]),'candidate':design(ds[idx]),'hypotheses':hyps,
                           'instance_key':iid,'n':n,'observation':obs['features'],
                           'map_mass':r['map_mass']}
                # IID is trusted seed routing metadata, stripped from future learner features.
                identity=sha(canonical(predictor))
                jobs.append({'id':identity[:24],'predictor':predictor,
                             'gold':{'walking':y,'n':n},
                             'evaluation':{'instance_id':iid,'base':iid.rsplit(':',2)[0],
                                           'family':r['family'],'design_index':idx,
                                           'is_original_submission':idx==r['repair']['design'],
                                           'verified_status':r['verification']['status'] if idx==r['repair']['design'] else None},
                             'source':{'file':name,'line':lineno,'row_sha256':sha(line)}})
    summary={'version':VERSION,'source_files':sources,'counts':dict(counts),
             'independent_bases':len(bases),'bases':sorted(bases),'families':sorted(families),
             'eligible_episodes':len(episodes),'unique_saved_checked_interventions':len(jobs),
             'matched_aggregate_observation_seed_count':sum(j['gold']['n'] for j in jobs),
             'prospectively_logged_exact_prediction_pairs':0,
             'retrospective_predictions_required':len(jobs),
             'alternative_interventions_without_full_verification':sum(j['evaluation']['verified_status'] is None for j in jobs),
             'note':'No residual labels or recovery counterfactuals are constructed by comparing different designs.'}
    write_new(out/'inventory.json',summary)
    write_new(out/'jobs.json',{'version':VERSION,'sources':sources,'jobs':jobs})
    return summary


def predict(job):
    """Twin-only, same saved candidate/robust seeds/variation/duration/criterion.

    Reuses Episode.ensemble exactly; outcome, family and verifier status are not
    passed. This measurement extends the original model to already checked designs.
    """
    from types import SimpleNamespace
    from creature_forge import belief_engine as be, hdb_bench as hb, hidden_plant as hp
    from creature_forge.arena import VARIATION_PRESET
    p=job['predictor']; iid=p['instance_key']; b,f,s=iid.rsplit(':',2)
    seeds=hb.instance_seeds(b,f,int(s))['robust'][:p['n']]
    if [int(s) for s in p['observation']] != hb.instance_seeds(b,f,int(s))['obs'][:len(p['observation'])]:
        raise ValueError('stored seed campaign does not match the reconstructed namespace')
    hyps=[(SimpleNamespace(deviation=h['deviation']),h['weight']) for h in p['hypotheses']]
    ep=SimpleNamespace(design0=p['nominal'])
    plants=be.Episode.ensemble(ep,hyps,k=8)
    d=p['candidate']; rows=[]; t0=time.perf_counter()
    # The original ensemble evaluator cycles plants by seed index. No extra
    # actual plant access occurs; the model discrepancy is the measurement target.
    for i,s in enumerate(seeds):
        rows+=hp.walk_seeds(plants[i%8],d['body'],d['vector'],[s],variation=VARIATION_PRESET,pool=None)
    if any(not r.get('ok') for r in rows):
        raise ValueError('twin measurement failed; do not count errors as failures')
    return {'version':VERSION,'id':job['id'],'input_sha256':sha(canonical(p)),
            'candidate_sha256':sha(canonical(d)),'seeds':seeds,'duration':10.,
            'variation':VARIATION_PRESET,'n':len(rows),'walking':sum(r['walking'] for r in rows),
            'rows':rows,'wall_s':time.perf_counter()-t0}


def measure(jobs_path,out,workers):
    from concurrent.futures import ProcessPoolExecutor,as_completed
    import multiprocessing as mp
    if not 1<=workers<=6:raise ValueError('max six independent workers')
    data=json.loads(Path(jobs_path).read_text()); out=Path(out)
    with ProcessPoolExecutor(workers,mp_context=mp.get_context('spawn')) as pool:
        fs={pool.submit(predict,{'id':j['id'],'predictor':j['predictor']}):j['id'] for j in data['jobs']}
        for f in as_completed(fs):
            row=f.result();write_new(out/'predictions'/f"{row['id']}.json",row)
    write_new(out/'MEASURE_COMPLETE.json',{'units':len(data['jobs']),'source_jobs_sha256':sha(Path(jobs_path).read_bytes())})


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True)
    x=sub.add_parser('prepare');x.add_argument('--records',required=True);x.add_argument('--out',required=True)
    x=sub.add_parser('measure');x.add_argument('--jobs',required=True);x.add_argument('--out',required=True);x.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    if a.cmd=='prepare':print(json.dumps(prepare(a.records,a.out),indent=2))
    else:measure(a.jobs,a.out,a.workers)

if __name__=='__main__':main()
