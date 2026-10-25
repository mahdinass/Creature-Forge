"""VEL-1 read-only reporting diagnostics and independent source integrity.

The context-matched prevalence reference is an explicitly post-fit diagnostic
strengthening the trivial comparator. It does not replace the frozen analysis.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vel1_audit import FEATURES,read,sha,canonical
from vel1_analyze import Logistic,constant,metrics,paired
import numpy as np
from r0_experiment import write_new


def main():
    p=argparse.ArgumentParser();p.add_argument('--audit',required=True);p.add_argument('--analysis',required=True)
    p.add_argument('--r0',required=True);p.add_argument('--di1',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();audit=Path(a.audit);analysis=Path(a.analysis);rows=read(audit/'fresh_v5_rows.json')
    old=read(analysis/'predictions.json');byid={r['id']:r for r in old};out=Path(a.out)
    result={'scope':'Post-fit reporting/stronger trivial comparator, not new primary model selection.',
            'unchanged_main_analysis':sha((analysis/'analysis.json').read_bytes())}
    for mode in ('lobo','dual_base_family_out'):
        probs=[];v1=[];v2=[];legacy=[]
        for r in rows:
            tr=[s for s in rows if s['group']!=r['group'] and
                (mode=='lobo' or s['family_evaluator_only']!=r['family_evaluator_only'])]
            context=[s for s in tr if s['apparent']==r['apparent']]
            probs.append(constant(context or tr))
            pred=byid[r['id']]['predictions']
            if mode!='lobo':pred=pred[mode]
            v1.append(pred['V1_physical']);v2.append(pred['V2_experience'])
            legacy.append(np.nan if r['legacy_map_failure_probability'] is None else r['legacy_map_failure_probability'])
        ix=[i for i,r in enumerate(rows) if r['apparent']];rs=[rows[i] for i in ix]
        cp=np.array(probs)[ix];first=np.array(v1)[ix];second=np.array(v2)[ix]
        y=np.array([r['target']['failed'] for r in rs])
        common=[i for i in ix if math.isfinite(legacy[i])]
        result[mode]={'context_constant_apparent':metrics(rs,cp),
                      'V1_gain_vs_context_constant':paired(rs,(cp-y)**2,(first-y)**2),
                      'V2_gain_vs_context_constant':paired(rs,(cp-y)**2,(second-y)**2),
                      'legacy_common_cases':{'V0_legacy':metrics([rows[i] for i in common],np.array(legacy)[common]),
                                             'V1_physical':metrics([rows[i] for i in common],np.array(v1)[common]),
                                             'V2_experience':metrics([rows[i] for i in common],np.array(v2)[common])}}
    # Retain interpretable fold coefficients, with exact replay of saved V1 predictions.
    models=[]
    for group in sorted({r['group'] for r in rows}):
        tr=[r for r in rows if r['group']!=group];te=[r for r in rows if r['group']==group]
        m=Logistic(FEATURES).fit(tr);pred=m.predict(te)
        if not all(float(p)==byid[r['id']]['predictions']['V1_physical'] for r,p in zip(te,pred)):
            raise ValueError('coefficient export did not reproduce main V1')
        models.append({'test_group':group,'training_groups':sorted({r['group'] for r in tr}),
                       'features':list(FEATURES),'median':m.median.tolist(),'mean':m.mean.tolist(),'scale':m.scale.tolist(),
                       'coefficients_intercept_standardized_missing':m.coef.tolist()})
    result['coefficient_diagnostics']={f:{'median_standardized_coefficient':float(np.median([m['coefficients_intercept_standardized_missing'][1+j] for m in models])),
                                        'positive_folds':sum(m['coefficients_intercept_standardized_missing'][1+j]>0 for m in models)}
                                       for j,f in enumerate(FEATURES)}
    # Source checks are independent of feature/label extraction.
    sources=read(audit/'audit.json')['sources'];r0root=Path(a.r0)
    manifest={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (r0root/'SHA256SUMS').read_text().splitlines()}
    r0checks=[]
    for pth in sorted((r0root/'units').glob('*.json')):
        digest=sha(pth.read_bytes());relative=pth.relative_to(r0root).as_posix()
        if digest!=manifest[relative] or digest!=sources[pth.as_posix()]['sha256']:raise ValueError('R0 source mismatch')
        r=read(pth);roles=r['seeds']
        if any(set(roles[x])&set(roles[y]) for i,x in enumerate(roles) for y in list(roles)[i+1:]):raise ValueError('R0 seed overlap')
        r0checks.append(relative)
    di_checks=[]
    for version in ('v1','v2'):
        root=Path(a.di1)/f'di1_pilot_{version}'
        sums={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (root/'SHA256SUMS').read_text().splitlines()}
        for src,receipt in sources.items():
            path=Path(src)
            if path.is_relative_to(root):
                if sha(path.read_bytes())!=sums[path.relative_to(root).as_posix()]:raise ValueError('DI1 source mismatch')
                di_checks.append(src)
    from creature_forge.hdb_bench import instance_seeds,assert_disjoint
    # Only deterministic seed routing. No plant reconstruction/simulation/loader.
    historical=read(audit/'fresh_v5_rows.json')+read(audit/'legacy_v5_rows.json')
    for r in historical:
        b,f,s=r['instance_id'].rsplit(':',2);assert_disjoint(instance_seeds(b,f,int(s)))
    observed_seed_checks=0;charged_stress_checks=0
    for source in sources:
        path=Path(source)
        if path.name not in ('fresh_A1c5.jsonl','vs5_A1c.jsonl'):continue
        for raw in path.read_bytes().splitlines():
            rec=json.loads(raw)
            if 'engine' not in rec:continue
            b,f,s=rec['instance_id'].rsplit(':',2);roles=instance_seeds(b,f,int(s))
            forbidden=set(roles['validate'])|set(roles['confirm'])
            for experiment in rec['engine']['experiments']:
                if set(experiment.get('seeds',[]))&forbidden:raise ValueError('verifier seeds in decision observations')
            obs=next(e for e in rec['engine']['experiments'] if e['kind']=='observe')
            if obs['seeds']!=roles['obs'][:len(obs['seeds'])]:raise ValueError('observation routing mismatch')
            for step in rec['repair']['log']:
                evidence=step.get('evidence') or {}
                if evidence.get('stress4') is None:continue
                if len(obs['seeds'])!=4:raise ValueError('stress4 denominator mismatch')
                if not any(l['item']=='stress_test' and l['n']==8 and l['detail'].get('design')==step['design'] and
                           l['detail'].get('duration')==20 for l in rec['engine']['ledger']['lines']):
                    raise ValueError('stress feature lacks matching charged20s check')
                charged_stress_checks+=1
            observed_seed_checks+=1
    primary_groups={r['group'] for r in rows}
    for proof in read(analysis/'fold_proofs.json'):
        if set(proof['training_groups'])&set(proof['test_groups']):raise ValueError('fold proof leak')
    gain=read(analysis/'analysis.json')['lobo']['apparent']['paired_brier_improvement']['V2_experience_vs_V1_physical']
    sd=float(np.std(list(gain['per_group'].values()),ddof=1))
    n80=math.ceil(((1.959963984540054+0.8416212335729143)*sd/.005)**2)
    n90=math.ceil(((1.959963984540054+1.2815515655446004)*sd/.005)**2)
    result['normal_reference_power_scenario']={'observed_base_sd':sd,'minimum_Brier_effect':.005,
             'n80_approx':n80,'n90_approx':n90,
             'caveat':'Illustrative normal paired-base planning only; fitted OOF loss differences and17bases do not validate future-design variance or a confirmatory gate.'}
    integrity={'r0_unit_hashes_match_original_manifest':len(r0checks),'di1_submission_hashes_match_original_manifests':len(di_checks),
               'historical_seed_role_routing_disjoint':len(historical),
               'original_observation_seed_routes_match_and_exclude_verifier_seeds':observed_seed_checks,
               'charged_20s_stress4_log_entries_verified':charged_stress_checks,
               'physical_group_aliases_blocked':True,
               'all_outer_fold_proofs_disjoint':True,'V1_exported_fold_predictions_exact':True,
               'features':list(FEATURES),'no_verifier_predictors':True,'primary_body_groups':len(primary_groups),
               'no_new_physics':True,'no_paid_measurement':True}
    write_new(out/'report_diagnostics.json',result);write_new(out/'V1_fold_models.json',models);write_new(out/'integrity.json',integrity)
    print(json.dumps({'integrity':integrity,'power':result['normal_reference_power_scenario'],
                      'context_constant':{k:result[k]['context_constant_apparent']['brier'] for k in ('lobo','dual_base_family_out')}},indent=2))


if __name__=='__main__':main()
