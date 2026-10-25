"""Read-only, explicit-development VEL-1 evidence audit. Never runs physics.

Features and evaluator metadata are separate. Compressed historical verifier
records retain labels/reasons, not all per-seed response or confirmation fields.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import tarfile

sys.path.insert(0,str(Path(__file__).resolve().parent))
from r0_experiment import write_new

FULL='FULL_RECOVERY'
FAMILIES=('pitch_sensor_bias','payload_offset','low_ground_friction','short_feet',
          'actuator_weakness','one_side_weakness','heavy_torso','feedback_gain_loss','clock_fault')
SOURCE_SHA={'fresh_A1c5.jsonl':'3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb',
            'vs5_A1c.jsonl':'e2ee1d53cdf81f2395a065c1b017ffc885b045fb533467b04a661429834ea520'}
FEATURES=('robust_fraction','robust_n','train_fraction','twin_fraction','stress_fraction',
          'map_mass','posterior_entropy','probe_count','remaining_fraction','checked_designs',
          'accepted','initial_walking','initial_slip','initial_capture','initial_ankle_saturation',
          'twin_plant_gap')


def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def design(d):return {k:d[k] for k in ('body','vector')}
def physical(d):return sha(canonical(design(d)))
def body_group(d):return sha(canonical(d['body']))


def fraction(k,n):
    if k is None:return None
    if isinstance(k,bool) or not isinstance(k,(int,float)) or not 0<=k<=n:
        raise ValueError(f'invalid walking count {k}/{n}')
    return float(k)/n


def label(ver):
    """Exact logical requirement reconstruction from full or compressed records."""
    status=ver.get('status');reasons=ver.get('reasons',[])
    if not status or 'ERROR' in status:
        return {'status':status,'failed':None,'reasons':reasons,'components':{},'confirmation_run':None}
    if status not in (FULL,'PARTIAL_IMPROVEMENT','NOT_RECOVERED'):raise ValueError('unknown recovery status')
    v=ver.get('validation',{});conf=ver.get('confirmation',{})
    walking=v.get('walking_frac',ver.get('walking_frac'))
    if walking is None or not 0<=walking<=1:raise ValueError('missing validation walking label')
    run=conf.get('run',ver.get('rollouts',{}).get('confirmation',0)>0)
    components={'validation_improvement_failed':status=='NOT_RECOVERED',
                'validation_walking_failed':walking<.8,
                'confirmation_walking_failed':None,
                'confirmation_speed_failed':None,'confirmation_contact_failed':None}
    if run:
        for name,key,token in [('confirmation_walking_failed','walking_frac','confirmation: walking'),
                               ('confirmation_speed_failed','median_speed_upright','confirmation: median upright speed'),
                               ('confirmation_contact_failed','body_contact','confirmation: body contact')]:
            components[name]=(not conf['checks'][key]['passed']) if 'checks' in conf else any(token in r for r in reasons)
    if status==FULL and (not run or any(x is True for x in components.values())):
        raise ValueError('contradictory FULL evidence')
    if status!=FULL and not any(x is True for x in components.values()):
        raise ValueError('unexplained failure')
    return {'status':status,'failed':int(status!=FULL),'reasons':reasons,'components':components,
            'confirmation_run':run,'validation_walking':walking,
            'full_per_seed_verifier_retained':bool(v.get('candidate'))}


def pre_features(r):
    """Only original decision-time fields; never reads r['verification']."""
    e,rep,ds=r['engine'],r['repair'],{d['index']:d for d in r['designs']}
    if e['version']!='belief_engine_v5' or any(x['kind']=='check' for x in e['experiments']):
        raise ValueError('unsupported/outcome-updated engine')
    selected=ds[rep['design']];selected_hash=physical(selected)
    logs=[l for l in rep['log'] if l.get('design') in ds and physical(ds[l['design']])==selected_hash]
    counts=[];train=twin=stress=oldp=None
    for l in logs:
        if l.get('check16') is not None:counts.append((16,l['check16']))
        elif l.get('check') is not None:counts.append((8,l['check']))
        if l.get('train_walking') is not None:train=fraction(l['train_walking'],4)
        if l.get('twin_walking') is not None:twin=fraction(l['twin_walking'],8)
        ev=l.get('evidence') or {}
        if ev.get('stress4') is not None:stress=fraction(ev['stress4'],4)
        if ev.get('p_full') is not None:oldp=float(ev['p_full'])
    n,k=max(counts,default=(0,None))
    # Same physical check on a seed prefix must be consistent, not independent.
    for nn,kk in counts:
        if nn==n and kk!=k:raise ValueError('conflicting same-candidate robustness checks')
        if nn<n and not 0<=k-kk<=n-nn:raise ValueError('inconsistent robustness prefix')
    if n:
        # At least one charged check of a same-identity candidate must support it.
        indices={d['index'] for d in ds.values() if physical(d)==selected_hash}
        if not any(l['item']=='robustness_check' and l['detail'].get('design') in indices and
                   l['detail'].get('n')==n for l in e['ledger']['lines']):raise ValueError('unpaid robustness feature')
    ll=[p['loglik'] for p in e['particles']];mx=max(ll);z=sum(math.exp(x-mx) for x in ll)
    weights=[math.exp(x-mx)/z for x in ll]
    obs=next(x['features'] for x in e['experiments'] if x['kind']=='observe')
    def avg(key):
        vs=[v[key] for v in obs.values() if isinstance(v.get(key),(int,float)) and math.isfinite(v[key])]
        return sum(vs)/len(vs) if vs else None
    ledger=e['ledger'];remaining=ledger.get('remaining',ledger.get('limit',700)-ledger['used'])
    out=dict(zip(FEATURES,[fraction(k,n) if n else None,n,train,twin,stress,max(weights),
             -sum(w*math.log(w) for w in weights if w)/math.log(len(weights)) if len(weights)>1 else 0.,
             sum(x['kind']!='observe' for x in e['experiments']),remaining/700,
             len({physical(ds[l['design']]) for l in rep['log'] if l.get('design') in ds and
                  (l.get('check16') is not None or l.get('check') is not None)}),int(rep['accepted']),
             avg('walking'),avg('slip_fraction'),avg('capture_margin_over_L_mean'),avg('saturation_frac_ankle'),
             abs(k/n-twin) if n and twin is not None else None]))
    if any(v is not None and not math.isfinite(v) for v in out.values()):raise ValueError('nonfinite feature')
    return out,oldp,selected


def engine_row(r,source,line=None):
    if r.get('family') not in FAMILIES or r.get('provenance')!='NO_AI':raise ValueError('non-dev/LLM input')
    features,oldp,selected=pre_features(r);nominal=r['designs'][0]
    bid=r['instance_id'].rsplit(':',2)[0]
    return {'id':sha(canonical([source,line,r['instance_id'],physical(selected)]))[:24],
            'base_id':bid,'group':body_group(nominal),'nominal_sha256':physical(nominal),
            'instance_id':r['instance_id'],'family_evaluator_only':r['family'],
            'candidate_sha256':physical(selected),'source':source,'line':line,'row_sha256':sha(canonical(r)),
            'features':features,'legacy_map_failure_probability':None if oldp is None else 1-oldp,
            'apparent':features['robust_n']==16 and features['robust_fraction']>=15/16,
            'target':label(r['verification'])}


def summary(rows):
    eligible=[r for r in rows if r['target']['failed'] is not None]
    apparent=[r for r in eligible if r['apparent']]
    return {'decision_records':len(rows),'independent_body_groups':len({r['group'] for r in rows}),
            'nominal_base_ids':len({r['base_id'] for r in rows}),
            'damage_instances':len({r['instance_id'] for r in rows}),
            'distinct_instance_candidates':len({(r['instance_id'],r['candidate_sha256']) for r in rows}),
            'labeled':len(eligible),'full':sum(r['target']['failed']==0 for r in eligible),
            'nonfull':sum(r['target']['failed']==1 for r in eligible),'inconclusive':len(rows)-len(eligible),
            'apparent_decisions':len(apparent),'apparent_full':sum(r['target']['failed']==0 for r in apparent),
            'apparent_failures':sum(r['target']['failed']==1 for r in apparent),
            'apparent_groups':len({r['group'] for r in apparent}),
            'apparent_failure_groups':len({r['group'] for r in apparent if r['target']['failed']}),
            'apparent_success_groups':len({r['group'] for r in apparent if r['target']['failed']==0}),
            'failure_components_all':dict(Counter(k for r in eligible for k,v in r['target']['components'].items() if v is True)),
            'failure_components_apparent':dict(Counter(k for r in apparent for k,v in r['target']['components'].items() if v is True)),
            'confirmation_not_run':sum(r['target']['confirmation_run'] is False for r in eligible),
            'confirmation_run_unknown':sum(r['target']['confirmation_run'] is None for r in eligible),
            'failure_component_records_available':sum(bool(r['target']['components']) for r in eligible),
            'per_seed_verifier_records':sum(r['target'].get('full_per_seed_verifier_retained',False) for r in eligible)}


def dedup(rows):
    """Exact physical submission and verification condition identity only."""
    keep={};duplicates=[]
    for r in rows:
        key=(r['instance_id'],r['candidate_sha256'],r.get('verification_seeds_sha256'))
        if key in keep:
            old=keep[key]
            if old['target']!=r['target']:raise ValueError('conflicting duplicate verification')
            duplicates.append({'retained':old['id'],'duplicate':r['id']})
        else:keep[key]=r
    return list(keep.values()),duplicates


def prepare(a):
    out=Path(a.out);sources={};groups={};all_rows={}
    def register(p,expected=None):
        p=Path(p);b=p.read_bytes();h=sha(b)
        if expected and h!=expected:raise ValueError(f'source checksum mismatch {p}')
        sources[str(p).replace('\\','/')]={'sha256':h,'bytes':len(b)}
        return b
    nominal={};excluded={}
    for name,cohort in [('fresh_A1c5.jsonl','fresh_v5'),('vs5_A1c.jsonl','legacy_v5')]:
        raw=register(Path(a.records)/name,SOURCE_SHA[name]);rows=[];excluded[cohort]=0
        for line,b in enumerate(raw.splitlines(),1):
            r=json.loads(b)
            if 'engine' not in r:excluded[cohort]+=1;continue
            row=engine_row(r,name,line);row['source_row_bytes_sha256']=sha(b)
            if r['verification'].get('seeds'):row['verification_seeds_sha256']=sha(canonical(r['verification']['seeds']))
            rows.append(row)
            base=r['instance_id'].rsplit(':',2)[0];d=design(r['designs'][0])
            if base in nominal and nominal[base]!=d:raise ValueError('nominal base changed')
            nominal[base]=d
        rows,duplicates=dedup(rows)
        if duplicates:raise ValueError('unexpected primary/legacy duplicate decisions')
        all_rows[cohort]=rows
    if set(r['group'] for r in all_rows['fresh_v5'])&set(r['group'] for r in all_rows['legacy_v5']):
        raise ValueError('primary/legacy physical body alias')
    stopraw=register(Path(a.records)/'stopcal.jsonl');stop=[json.loads(l) for l in stopraw.splitlines()]
    if {r['base_id'] for r in stop}&{r['base_id'] for r in all_rows['fresh_v5']}:
        raise ValueError('legacy stopping-map training overlaps primary base IDs')
    if not {r['base_id'] for r in stop}<=set(nominal):raise ValueError('unknown stopping-calibration base')
    if {body_group(nominal[r['base_id']]) for r in stop}&{r['group'] for r in all_rows['fresh_v5']}:
        raise ValueError('legacy stopping-map physical nominal aliases primary')
    stop_summary={'rows':len(stop),'base_ids':sorted({r['base_id'] for r in stop}),
                  'full':sum(r['label'] for r in stop),'nonfull':sum(not r['label'] for r in stop),
                  'distinct_indexed_candidates':len({(r['instance_id'],r.get('origin'),r.get('source')) for r in stop}),
                  'physical_candidate_identity_not_serialized':True,'retrospective_features':True,
                  'note':'Separate older dev calibration panel; never pooled with submitted-candidate evaluation.'}
    # RL-1 is an exhaustive fixed-budget tool matrix, not original-engine final submissions.
    matrix=Path('experiments/causal_engineer/dev/rl1/rl1_matrix.tgz')
    protocol=read('experiments/causal_engineer/dev/repair_strategy_r0/protocol.json')
    register(matrix,protocol['sources'][str(matrix).replace('\\','/')]);rl=[]
    with tarfile.open(matrix) as t:
        members={m.name:m for m in t.getmembers()};payload=t.extractfile(members['matrix.jsonl']).read()
        manifest=t.extractfile(members['SHA256SUMS']).read().decode()
        assert any(line.startswith(sha(payload)) and line.endswith('matrix.jsonl') for line in manifest.splitlines())
        for i,line in enumerate(payload.splitlines()):
            r=json.loads(line);bid=r['base_id']
            if bid not in nominal or r['family'] not in FAMILIES:raise ValueError('RL1 outside dev support')
            if not r.get('ok') or r.get('error'):raise ValueError('invalid RL1 cell')
            rl.append({'id':f'rl1:{i}','base_id':bid,'group':body_group(nominal[bid]),'instance_id':r['instance_id'],
                       'family_evaluator_only':r['family'],'candidate_sha256':physical(r['design']),
                       'apparent':fraction(r['train_walking'],4)==1.,'tool_evaluator_only':r['tool'],
                       'features':{'train_fraction':fraction(r['train_walking'],4)},
                       'target':{'status':r['status'],'failed':int(r['status']!=FULL),'reasons':[],
                                 'components':{},'confirmation_run':None}})
    rl_unique,rl_dups=dedup(rl);all_rows['rl1']=rl_unique
    # Frozen R0 records retain full independent verifier responses and pre-verification selections.
    r0=[];r0root=Path(a.r0)
    for p in sorted((r0root/'units').glob('*.json')):
        r=json.loads(register(p));c=r['result'];d=c['design'];selected=c['selection'][c['selected']]
        if selected['design_hash']!=sha(canonical(d)):raise ValueError('R0 selected identity mismatch')
        bid=r['base_id']
        if bid not in nominal or r['family'] not in FAMILIES:raise ValueError('R0 outside dev support')
        r0.append({'id':r['unit_id'],'base_id':bid,'group':body_group(nominal[bid]),
                   'instance_id':r['instance_id'],'family_evaluator_only':r['family'],
                   'candidate_sha256':physical(d),'verification_seeds_sha256':sha(canonical({k:r['seeds'][k] for k in ('validate','confirm')})),
                   'apparent':selected['walking_count']>=7,'features':{'selection_fraction':fraction(selected['walking_count'],8)},
                   'target':label(r['verification']),'action':r['action'],'objective':r['objective']})
    if len(r0)!=324:raise ValueError('R0 incomplete')
    r0_unique,r0_dups=dedup(r0);all_rows['r0']=r0_unique
    # DI1 baseline/equivalence copies are not extra measurements; no journal recomputation needed.
    di=[]
    for version in ('v1','v2'):
        root=Path(a.di1)/f'di1_pilot_{version}'
        for b in read('experiments/causal_engineer/dev/di1/pilot_config.json')['bases']:
            d=root/b['base_id'];complete=read(d/'complete.json')
            if not complete['eligible']:continue
            for mode in ('baseline','raw_eig','random'):
                p=d/f'{mode}.json';r=json.loads(register(p));s=r['scientific']
                source={**s,'instance_id':b['base_id'],'family':read(d/'instance.json')['family'],
                        'provenance':'NO_AI','verification':r['verification']}
                row=engine_row(source,str(p));row['id']=f'di1:{version}:{b["base_id"]}:{mode}'
                row['verification_seeds_sha256']=sha(canonical(r['verification']['seeds']));di.append(row)
    di_unique,di_dups=dedup(di);all_rows['di1']=di_unique
    # Previously reconstructed forecasts were not present before original outcomes.
    ej=json.loads(register(a.em1_jobs));alternatives=[j for j in ej['jobs'] if not j['evaluation']['is_original_submission']]
    report={'analysis_date':'2026-10-26','plan_commit':'63df2c1','sources':sources,
            'cohorts':{k:summary(v) for k,v in all_rows.items()},'ineligible_original_rows':excluded,
            'all_submitted_body_groups_union':len({r['group'] for rs in all_rows.values() for r in rs}),
            'all_unique_damage_instances_union':len({r['instance_id'] for rs in all_rows.values() for r in rs}),
            'stop_calibration':stop_summary,
            'duplicates':{'rl1':len(rl_dups),'r0':len(r0_dups),'di1':len(di_dups)},
            'em1':{'paired_candidates':len(ej['jobs']),'alternative_candidates_missing_FULL':sum(j['evaluation']['verified_status'] is None for j in alternatives),
                   'new_independent_bases':0,'reconstructed_forecasts_available_at_historical_decision':False},
            'primary_feature_missing':{f:sum(r['features'][f] is None for r in all_rows['fresh_v5']) for f in FEATURES},
            'primary_missing_legacy_map_probability':sum(r['legacy_map_failure_probability'] is None for r in all_rows['fresh_v5']),
            'notes':['Independent units are nominal physical bodies, not episodes/seeds/interventions.',
                     'Distinct cohorts are reported separately, not pooled for risk fitting.',
                     'Compressed historical verifier records support component reasons, not unavailable per-seed variance.',
                     'Alternative missing FULL outcomes and confirmation-not-run remain missing.']}
    write_new(out/'audit.json',report)
    for k,rs in all_rows.items():write_new(out/f'{k}_rows.json',rs)
    write_new(out/'duplicates.json',{'rl1':rl_dups,'r0':r0_dups,'di1':di_dups})
    print(json.dumps({k:v for k,v in report.items() if k not in ('sources',)},indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--records',required=True);p.add_argument('--r0',required=True)
    p.add_argument('--di1',required=True);p.add_argument('--em1-jobs',required=True);p.add_argument('--out',required=True)
    prepare(p.parse_args())


if __name__=='__main__':main()
