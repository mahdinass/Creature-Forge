"""Additional read-only requirement routing, cross-identity and planning descriptions."""
from pathlib import Path
import collections as C
import hashlib
import json
import math
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
def h(d):return hashlib.sha256(json.dumps({k:d[k] for k in ('body','vector')},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def main():
    rows=json.loads((OUT/'validated/rl1_decisions.json').read_text());cells=[c for r in rows for c in r['cells']]
    routes={}
    for name,cc in [('all',cells),('train4',[c for c in cells if c['train_walking']==4])]:
        routes[name]={'n':len(cc),'improvement_fail_inferred_from_NOT_RECOVERED':sum(c['status']=='NOT_RECOVERED' for c in cc),
          'validation_walking_fail':sum(c['walking_frac']<.8 for c in cc),
          'conditional_confirmation_failure_any':sum(c['status']=='PARTIAL_IMPROVEMENT' and c['walking_frac']>=.8 for c in cc),
          'confirmation_not_run_inferred':sum(c['status']=='NOT_RECOVERED' or c['walking_frac']<.8 for c in cc)}
    with tarfile.open(ROOT/'experiments/causal_engineer/dev/rl1/rl1_matrix.tgz') as t:mat=[json.loads(l) for l in t.extractfile('matrix.jsonl')]
    labels={(r['instance_id'],h(r['design'])):r['status'] for r in mat};cross=C.Counter();found=[]
    for line in (ROOT/'artifacts/r0_inputs/fresh_A1c5.jsonl').read_text().splitlines():
        r=json.loads(line)
        if not r.get('verification'):continue
        sel=h(r['designs'][r['repair']['design']]);checks={}
        for e in r['repair']['log']:
            if 'design' not in e:continue
            w,n=(e.get('check16'),16) if e.get('check16') is not None else (e.get('check'),8)
            if w is not None:checks[e['design']]=(w,n)
        hs={h(r['designs'][i]) for i in checks}
        cross['episodes']+=1;cross['checked_distinct_design_episode_entries']+=len(hs);cross['at_least_two_checked']+=len(hs)>=2
        for key in hs-{sel}:
            cross['alternative_checked_design_episode_entries']+=1
            if (r['instance_id'],key) in labels:found.append({'id':r['instance_id'],'hash':key,'label':labels[r['instance_id'],key]})
    rate=.11852767191309818;factor=1.25*rate/8/3600;quote=2.1169
    costs=[]
    for name,eq in [('fill320_original_missing_panels',320*96),('fill320_plus_two_new_panels_all640',320*96+640*2*96)]:
        costs.append({'scenario':name,'max_equivalents':eq,'eight_sixworker_hours_25pct_margin':eq*factor,'cloud_before_ops_usd':eq*factor*quote,
                      'single_sixworker_hours_25pct_margin':eq*factor*8})
    for n in [30,180,337]:
        for yield_ in [.5,.25]:
            healthy=n/yield_*2104;qual=n*72;generation=n*3500;ver=n*2*3*96;eq=healthy+qual+generation+ver
            costs.append({'scenario':'new_independent_lineages','n':n,'assumed_yield_NOT_MEASURED':yield_,
              'healthy_creation_equivalents':healthy,'fault_qualification_equivalents':qual,
              'common_candidate_generation_equivalents':generation,'verifier_equivalents':ver,
              'total_equivalents':eq,'hours25margin':eq*factor,'cloud_before_ops_usd':eq*factor*quote})
    power=[{'delta':delta,'discordance_assumed_NOT_MEASURED':d,'n_approx':math.ceil((1.95996398454+.84162123357)**2*(d-delta**2)/delta**2)} for delta in [.1,.05] for d in [.2,.4]]
    result={'rl1_requirement_routes':routes,'fresh_vs_matrix_identity_crosscheck':{'counts':dict(cross),'matches':found},
      'planning':costs,'approx_power_sensitivity':power,
      'cautions':['Requirement routes inferred from unchanged full_recovery_v1, not recovered per-seed arrays.',
                  'Current raw matrix source omits verifier seeds; crossmatch assumes source-routed equivalence and finds zero matching alternatives anyway.',
                  'Yield and paired discordance scenarios are proposals, not estimates or validated power/cost guarantees.']}
    dest=OUT/'supplement.json'
    if '--out-json' in sys.argv:dest=(ROOT/Path(sys.argv[sys.argv.index('--out-json')+1])).resolve()
    assert dest.is_relative_to(ROOT/'artifacts')
    with dest.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'routes':routes,'crossmatch':dict(cross),'exact_alternative_matches':len(found),'cost_scenarios':len(costs),'power':power},indent=2))

if __name__=='__main__':main()
