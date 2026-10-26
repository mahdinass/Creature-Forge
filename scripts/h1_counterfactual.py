"""Frozen H1 missing-counterfactual measurement; no policy/learning changes.

Preparation and analysis are stdlib-only. Physics is imported only by run.
Every candidate is an existing exact R0 finalist, never a newly searched repair.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from r0_experiment import canonical, read, sha, write_new

PIN = 'e8d5fa6730ecf6d2db67021a9d3d0f08cce03310'
STUDY = ROOT/'experiments/causal_engineer/dev/h1'
FULL = 'FULL_RECOVERY'


def key(iid, design, seeds, variation):
    return sha(canonical([iid, sha(canonical(design)), seeds, variation]))


def prepare(raw, reconstruction, out):
    raw, out = Path(raw), Path(out)
    manifest = dict((line.split('  ', 1)[1], line.split('  ', 1)[0])
                    for line in (raw/'SHA256SUMS').read_text().splitlines())
    designs = {(d['iid'], d['candidate_sha256']): d['design'] for d in read(reconstruction)}
    cases = {c['instance_id']: c for c in read(ROOT/'experiments/causal_engineer/dev/repair_strategy_r0/cases.json')}
    known, candidates, pairs, sources = {}, {}, [], {}
    records = []
    for path in sorted((raw/'units').glob('*.json')):
        digest = sha(path.read_bytes())
        if digest != manifest['units/'+path.name]:
            raise ValueError('R0 source hash mismatch')
        sources[path.name] = digest
        r = read(path); records.append(r)
        c = cases[r['instance_id']]; v = r['verification']; z = r['result']
        if r['base_id'] != c['base_id'] or r['seeds'] != c['seeds'] or v['seeds'] != {k:c['seeds'][k] for k in ('validate','confirm')}:
            raise ValueError('original matched identity/seeds mismatch')
        if v.get('errors') or v['rule'] != 'full_recovery_v1':
            raise ValueError('invalid historical verification')
        k = key(r['instance_id'], z['design'], v['seeds'], v['variation'])
        label = {'status': v['status'], 'components': components(v)}
        if k in known and known[k] != label:
            raise ValueError('inconsistent original aliases')
        known[k] = label
    for r in records:
        c = cases[r['instance_id']]; v = r['verification']; z = r['result']; kk = []
        if len(z['selection']) != 2 or z['selected'] != max(range(2), key=lambda i:(z['selection'][i]['walking_count'],z['selection'][i]['survival_count'],z['selection'][i]['mean_fitness'],-i)):
            raise ValueError('incumbent choice cannot be replayed')
        for s in z['selection']:
            design = designs[r['instance_id'], s['design_hash']]
            if sha(canonical(design)) != s['design_hash']:
                raise ValueError('candidate physical hash mismatch')
            k = key(r['instance_id'], design, v['seeds'], v['variation']); kk.append(k)
            candidates[k] = {'key':k,'base_id':c['base_id'],'instance_id':c['instance_id'],
              'candidate_sha256':s['design_hash'],'candidate':design,'original':c['robot'],
              'plant':c['plant'],'seeds':v['seeds'],'variation':v['variation']}
        if len(set(kk)) != 2:
            raise ValueError('not two distinct exact candidates')
        pairs.append({'unit_id':r['unit_id'],'base_id':c['base_id'],'instance_id':c['instance_id'],
          'action':r['action'],'objective':r['objective'],'replicate':r['replicate'],
          'keys':kk,'selected':z['selected'],'preverification':z['selection']})
    missing = sorted(set(candidates)-set(known))
    if (len(records),len(candidates),len(known),len(missing),len(cases)) != (324,640,320,320,18):
        raise ValueError('unexpected frozen cohort')
    write_new(out/'candidates.json', [candidates[k] for k in sorted(candidates)])
    write_new(out/'pairs.json', pairs); write_new(out/'known.json', known)
    write_new(out/'protocol.json', {'version':'h1-stage-a-v1','evidence_pin':PIN,
      'files':{n:sha((out/n).read_bytes()) for n in ('candidates.json','pairs.json','known.json')},
      'original_unit_sha256':sources,'original_manifest_sha256':sha((raw/'SHA256SUMS').read_bytes()),
      'reconstruction_sha256':sha(Path(reconstruction).read_bytes()),'missing_keys':missing,
      'n_bases':18,'n_pairs':324,'n_candidates':640,'n_missing':320,
      'max_verifier_equivalents':30720,
      'gate':{'complete_error_free':True,'minimum_missed_full_bases':3,'minimum_base_equal_oracle_gain':.05},
      'rule':'full_recovery_v1','cloud_cap_usd':25,'paid_batch_cap_hours':6,'token_cap_usd':0})
    return {'pairs':324,'candidates':640,'missing':320,'bases':18}


def components(v):
    if v.get('errors') or v['status']=='INCONCLUSIVE_ERROR':
        return None
    d = {'improvement':v['validation']['verdict']['status']=='VERIFIED_IMPROVEMENT',
         'validation_walking':v['validation']['aggregate']=='PASS'}
    for k in ('walking_frac','median_speed_upright','body_contact'):
        d['confirmation_'+k] = v['confirmation']['checks'][k]['passed'] if v['confirmation'].get('run') else None
    return d


def load(study):
    study = Path(study); p = read(study/'protocol.json')
    if any(sha((study/n).read_bytes()) != h for n,h in p['files'].items()):
        raise ValueError('frozen input hash mismatch')
    cc = read(study/'candidates.json')
    for c in cc:
        if c['candidate_sha256'] != sha(canonical(c['candidate'])) or c['key'] != key(c['instance_id'],c['candidate'],c['seeds'],c['variation']):
            raise ValueError('candidate identity mismatch')
    return p, {c['key']:c for c in cc}, read(study/'pairs.json'), read(study/'known.json')


def run(study, out, shard):
    validate_sources(study)
    from creature_forge.hidden_plant import verify
    from creature_forge.forge_pool import ForgePool
    p, cc, _, _ = load(study); index,total = map(int,shard.split('/'))
    if total != 8 or not 0 <= index < total:
        raise ValueError('requires eight fixed six-worker shards')
    out = Path(out)
    write_new(out/f'execution_{index}.json', {'epoch':time.time(),'protocol_sha256':sha((Path(study)/'protocol.json').read_bytes()),'shard':shard,'python':sys.version})
    with ForgePool(max_workers=6) as pool:
        for k in p['missing_keys'][index::total]:
            dest = out/'outcomes'/f'{k}.json'
            if dest.exists():
                raise ValueError('no selective resume/rerun')
            c=cc[k]; t=time.perf_counter()
            v=verify(c['plant'],c['original'],c['candidate'],c['seeds']['validate'],c['seeds']['confirm'],pool=pool)
            if v['variation'] != c['variation'] or v['seeds'] != c['seeds']:
                raise ValueError('verifier conditions mismatch')
            write_new(dest, {'key':k,'candidate_sha256':c['candidate_sha256'],'verification':v,'wall_s':time.perf_counter()-t})
            print(json.dumps({'key':k,'status':v['status']}),flush=True)
            if components(v) is None:
                raise ValueError('simulator error preserved; gate not evaluable')


def analyze(study, out):
    p, cc, pairs, labels = load(study); out=Path(out); missing=[]; errors=[]; eq=0; rows=0
    for k in p['missing_keys']:
        path=out/'outcomes'/f'{k}.json'
        if not path.exists(): missing.append(k); continue
        r=read(path); v=r['verification']; c=cc[k]
        if r['key']!=k or r['candidate_sha256']!=c['candidate_sha256'] or v['seeds']!=c['seeds'] or v['variation']!=c['variation'] or v['rule']!='full_recovery_v1':
            raise ValueError('outcome identity mismatch')
        comp=components(v)
        if comp is None: errors.append(k)
        labels[k]={'status':v['status'],'components':comp}
        eq+=v['rollouts']['validation']+v['rollouts']['confirmation_rollout_equivalents']
        rows+=len(v['validation']['original'])+len(v['validation']['candidate'])+len(v['confirmation'].get('per_seed',[]))
    by=collections.defaultdict(list); detail=[]
    for pair in pairs:
        a=labels.get(pair['keys'][pair['selected']]); b=labels.get(pair['keys'][1-pair['selected']])
        valid=bool(a and b and a['components'] is not None and b['components'] is not None)
        miss=valid and a['status']!=FULL and b['status']==FULL
        reverse=valid and a['status']==FULL and b['status']!=FULL
        by[pair['base_id']].append(int(miss) if valid else None)
        detail.append({'unit_id':pair['unit_id'],'base_id':pair['base_id'],'complete':valid,'missed_full':bool(miss),'reverse':bool(reverse)})
    complete=not missing and not errors
    effects={b:sum(v)/len(v) for b,v in by.items()} if complete else None
    gain=sum(effects.values())/len(effects) if complete else None
    bases=len({d['base_id'] for d in detail if d['missed_full']})
    if complete:
        rng=random.Random(2026102611); vals=list(effects.values())
        boot=sorted(sum(rng.choices(vals,k=len(vals)))/len(vals) for _ in range(10000))
        interval=[boot[249],boot[9749]]
    else: interval=None
    checks={'complete_error_free':complete,'headroom_on_three_bases':complete and bases>=3,
            'base_equal_oracle_gain_at_least_5pp':complete and gain>=.05}
    return {'stage_a_signal':'ADVANCE_TO_B' if all(checks.values()) else ('NO-GO' if complete else 'NOT EVALUABLE'),
      'gate_checks':checks,'n_known_bases':18,'new_lineages':0,'n_pairs':324,
      'new_assessments':320-len(missing),'new_response_rows':rows,'new_equivalents':eq,
      'missing':missing,'errors':errors,'missed_full_screens':sum(d['missed_full'] for d in detail),
      'missed_full_bases':bases,'reverse_screens':sum(d['reverse'] for d in detail),
      'reverse_bases':len({d['base_id'] for d in detail if d['reverse']}),
      'base_equal_oracle_gain':gain,'descriptive_whole_base_bootstrap95':interval,
      'base_effects':effects,'pairs':detail,
      'interpretation':'Historical available-candidate oracle headroom; not a deployable selector or experience-learning gain.'}


def validate_sources(study):
    sources=read(Path(study)/'source_hashes.json')
    for name,h in sources.items():
        if sha((ROOT/name).read_bytes().replace(b'\r\n',b'\n')) != h:
            raise ValueError('frozen source changed: '+name)
    return len(sources)


def main():
    ap=argparse.ArgumentParser(__doc__); ap.add_argument('cmd',choices=('prepare','run','analyze'))
    ap.add_argument('--study',default=str(STUDY)); ap.add_argument('--raw',default='artifacts/r0_ops/r0_run_20261025')
    ap.add_argument('--reconstruction',default='artifacts/h1_recovered_reconstruction/reconstructed_candidates.json')
    ap.add_argument('--out',default='artifacts/h1_stage_a'); ap.add_argument('--shard',default='0/8');ap.add_argument('--analysis-output')
    a=ap.parse_args()
    if a.cmd=='prepare':result=prepare(a.raw,a.reconstruction,a.study)
    elif a.cmd=='run':run(a.study,a.out,a.shard);return
    else:
        result=analyze(a.study,a.out)
        if a.analysis_output:write_new(a.analysis_output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('pairs','missing','errors','base_effects')},indent=2))


if __name__=='__main__':main()
