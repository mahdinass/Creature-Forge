"""VEL-2 Stage A: frozen, outcome-blind selection and unchanged physical verification."""
from __future__ import annotations
import argparse
import collections
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from r0_experiment import canonical, sha, read, write_new

NS = 'vel2-repeatability-20261026-v1'
STUDY = ROOT/'experiments/causal_engineer/dev/vel2'
CORE = ('creature_forge/recovery.py', 'creature_forge/verdict.py',
        'creature_forge/hidden_plant.py', 'creature_forge/locomotion.py')


def select(records):
    """Only preverification fields are read. Duplicate candidates get one ticket."""
    groups = collections.defaultdict(dict)
    for r in records:
        z = r['result']; s = z['selection'][z['selected']]
        h = sha(canonical(z['design']))
        if s['design_hash'] != h:
            raise ValueError('selected physical identity mismatch')
        if s.get('error') or s['walking_count'] < 7:
            continue
        key = (r['base_id'], h)
        old = groups[r['base_id']].get(h)
        if old is None or r['unit_id'] < old['unit_id']:
            groups[r['base_id']][h] = r
    return [min(v.values(), key=lambda r: sha(f"{NS}:select:{b}:{sha(canonical(r['result']['design']))}".encode()))
            for b, v in sorted(groups.items())]


def panels(base, used):
    out = []
    for panel in range(2):
        d = {}
        for role in ('validate', 'confirm'):
            d[role] = []
            for i in range(24):
                s = int(sha(f'{NS}:{base}:{panel}:{role}:{i}'.encode())[:8], 16)
                if s in used:
                    raise ValueError('seed collision; freeze cannot proceed')
                used.add(s); d[role].append(s)
        out.append(d)
    return out


def core_hashes():
    return {p: sha((ROOT/p).read_bytes().replace(b'\r\n', b'\n')) for p in CORE}


def prepare(raw, output):
    paths = sorted((Path(raw)/'units').glob('*.json'))
    if len(paths) != 324:
        raise ValueError('incomplete original R0')
    manifest = {line.split('  ', 1)[1]: line.split('  ', 1)[0]
                for line in (Path(raw)/'SHA256SUMS').read_text().splitlines()}
    records = []
    for p in paths:
        if sha(p.read_bytes()) != manifest['units/'+p.name]:
            raise ValueError('original evidence checksum mismatch')
        records.append(read(p))
    cases = read(ROOT/'experiments/causal_engineer/dev/repair_strategy_r0/cases.json')
    bybase = {c['base_id']: c for c in cases}
    selected = select(records)
    used = {s for r in records for ss in r['seeds'].values() for s in ss}
    original_seed_count = len(used)
    frozen = []
    for r in selected:
        c = bybase[r['base_id']]
        if c['instance_id'] != r['instance_id']:
            raise ValueError('case mismatch')
        z = r['result']
        frozen.append({'base_id':r['base_id'], 'instance_id':r['instance_id'],
          'nominal_body_sha256':sha(canonical(c['robot']['body'])),
          'candidate_sha256':sha(canonical(z['design'])), 'unit_id':r['unit_id'],
          'source_sha256':manifest['units/'+r['unit_id']+'.json'],
          'plant':c['plant'], 'original':c['robot'], 'candidate':z['design'],
          'preverification':{'selection':z['selection'][z['selected']], 'seeds':r['seeds'],
                             'ledger':z['ledger'], 'action':r['action'], 'objective':r['objective']},
          'panels':panels(r['base_id'], used),
          'original_verification':r['verification'], 'family_evaluator_only':r['family'], 'cohort':r['cohort']})
    if len(frozen)!=15 or len({c['nominal_body_sha256'] for c in frozen})!=15:
        raise ValueError('unexpected supported independent body groups')
    out=Path(output)
    write_new(out/'stage_a_cases.json',frozen)
    write_new(out/'stage_a_protocol.json',{'namespace':NS,'n_bases':15,'new_panels':2,
      'cases_sha256':sha((out/'stage_a_cases.json').read_bytes()),'unchanged_core_sha256_lf':core_hashes(),
      'original_r0_manifest_sha256':sha((Path(raw)/'SHA256SUMS').read_bytes()),
      'original_unique_seeds':original_seed_count,'new_unique_seeds':len(used)-original_seed_count,
      'gate':{'complete_error_free':True,'all_three_full_labels_agree_at_least':12,
              'pairwise_full_agreement_at_least':.85,'validation_requirement_pair_agreement_at_least':.8,
              'persistent_full_at_least':3,'persistent_nonfull_at_least':3},
      'max_verifier_equivalents':2880,'selection':'unique physical candidate tickets; minimum SHA namespace/base/candidate; alias minimum unit_id',
      'analysis':'base is unit; original plus two new panels; unconditional FULL, conditional confirmation requirements; Wilson reference uncertainty; no population or learning inference',
      'cloud_cap_usd':6,'token_cap_usd':0,'research_cutoff_epoch':1793098800})
    print(json.dumps({'n':len(frozen),'cases_sha256':sha((out/'stage_a_cases.json').read_bytes()),
                      'new_seeds':len(used)-original_seed_count}))


def load(study):
    p=read(Path(study)/'stage_a_protocol.json')
    if sha((Path(study)/'stage_a_cases.json').read_bytes())!=p['cases_sha256'] or core_hashes()!=p['unchanged_core_sha256_lf']:
        raise ValueError('frozen inputs or authoritative verifier changed')
    return p, read(Path(study)/'stage_a_cases.json')


def run(study,out):
    from creature_forge.hidden_plant import verify
    from creature_forge.forge_pool import ForgePool
    p,cases=load(study);out=Path(out); t0=time.perf_counter()
    write_new(out/'execution.json',{'epoch':time.time(),'protocol_sha256':sha((Path(study)/'stage_a_protocol.json').read_bytes()),
      'python':sys.version,'executable':sys.executable,'core':core_hashes(),'workers':6,
      'packages':__import__('r0_experiment').fingerprint()})
    with ForgePool(max_workers=6) as pool:
        for i,c in enumerate(cases):
            for j,seeds in enumerate(c['panels']):
                dest=out/'panels'/f'{i:02d}_{j}.json'
                if dest.exists():
                    raise ValueError('no silent rerun or selective resume')
                start=time.perf_counter()
                v=verify(c['plant'],c['original'],c['candidate'],seeds['validate'],seeds['confirm'],pool=pool)
                row={'base_id':c['base_id'],'candidate_sha256':c['candidate_sha256'],'panel':j,
                     'verification':v,'wall_s':time.perf_counter()-start}
                write_new(dest,row)
                print(json.dumps({'base':c['base_id'],'panel':j,'status':v['status'],'wall_s':row['wall_s']}),flush=True)
                if v.get('errors') or v['status']=='INCONCLUSIVE_ERROR':
                    raise ValueError('simulator error retained; stop and investigate')
    write_new(out/'complete.json',{'panels':30,'wall_s':time.perf_counter()-t0})
    analyze(study,out,out/'analysis.json')


def components(v):
    if v.get('errors') or v['status']=='INCONCLUSIVE_ERROR':
        raise ValueError('simulator error is not a failed physical target')
    d={'full':v['status']=='FULL_RECOVERY',
       'improvement':v['validation']['verdict']['status']=='VERIFIED_IMPROVEMENT',
       'validation_walking':v['validation']['aggregate']=='PASS'}
    for k in ('walking_frac','median_speed_upright','body_contact'):
        d['confirmation_'+k]=v['confirmation']['checks'][k]['passed'] if v['confirmation'].get('run') else None
    return d


def wilson(k,n):
    if not n:return None
    z=1.95996398454; f=k/n; den=1+z*z/n
    mid=(f+z*z/(2*n))/den; half=z*math.sqrt(f*(1-f)/n+z*z/(4*n*n))/den
    return [mid-half,mid+half]


def analyze(study,out,dest):
    p,cases=load(study);out=Path(out); rows=[]; equiv=0; agreements=collections.defaultdict(list)
    for i,c in enumerate(cases):
        vv=[c['original_verification']]
        for j in range(2):
            r=read(out/'panels'/f'{i:02d}_{j}.json')
            if r['base_id']!=c['base_id'] or r['candidate_sha256']!=c['candidate_sha256'] or r['panel']!=j or r['verification']['seeds']!=c['panels'][j]:
                raise ValueError('panel identity or seed mismatch')
            v=r['verification'];vv.append(v)
            equiv+=v['rollouts']['validation']+v['rollouts']['confirmation_rollout_equivalents']
        cc=[components(v) for v in vv]
        for k in cc[0]:
            for a,b in ((0,1),(0,2),(1,2)):
                if cc[a][k] is not None and cc[b][k] is not None:
                    agreements[k].append(int(cc[a][k]==cc[b][k]))
        labels=[x['full'] for x in cc]
        rows.append({'base_id':c['base_id'],'family':c['family_evaluator_only'],'cohort':c['cohort'],
         'unit_id':c['unit_id'],'status':[v['status'] for v in vv],'components':cc,
         'all_agree':len(set(labels))==1,'persistent_full':all(labels),'persistent_nonfull':not any(labels),
         'reasons':[v['reasons'] for v in vv]})
    g=p['gate']; n=len(rows); stable=sum(r['all_agree'] for r in rows)
    agree={k:{'agree':sum(v),'n_observed_pairs':len(v),'fraction':sum(v)/len(v) if v else None} for k,v in agreements.items()}
    checks={'complete_error_free':len(list((out/'panels').glob('*.json')))==30,
      'three_panel_agreement':stable>=g['all_three_full_labels_agree_at_least'],
      'pairwise_agreement':agree['full']['fraction']>=g['pairwise_full_agreement_at_least'],
      'validation_requirements':all(agree[k]['fraction']>=g['validation_requirement_pair_agreement_at_least'] for k in ('improvement','validation_walking')),
      'persistent_failure_support':sum(r['persistent_nonfull'] for r in rows)>=g['persistent_nonfull_at_least'],
      'persistent_success_support':sum(r['persistent_full'] for r in rows)>=g['persistent_full_at_least']}
    result={'n_bases':n,'new_verifications':30,'new_rollout_equivalents':equiv,
      'three_panel_agreement_bases':stable,'discordant_bases':n-stable,
      'stable_fraction_wilson_reference95':wilson(stable,n),'agreement':agree,
      'full_by_panel':[sum(r['components'][j]['full'] for r in rows) for j in range(3)],
      'gate_checks':checks,'stage_a_gate':all(checks.values()),'bases':rows,
      'inference':'fixed selected known development bases; pairwise observations correlated; not transfer, recovery improvement, or learning'}
    write_new(dest,result)
    print(json.dumps({k:v for k,v in result.items() if k!='bases'},indent=2))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=('prepare','run','analyze'))
    p.add_argument('--study',default=str(STUDY));p.add_argument('--raw',default='artifacts/r0_ops/r0_run_20261025')
    p.add_argument('--out',default='artifacts/vel2_stage_a');p.add_argument('--analysis-output')
    a=p.parse_args()
    if a.cmd=='prepare':prepare(a.raw,a.study)
    elif a.cmd=='run':run(a.study,a.out)
    else:analyze(a.study,a.out,a.analysis_output or str(Path(a.out)/'analysis.json'))


if __name__=='__main__':main()
