"""Compact DI-1 evidence export; raw immutable journals remain in archives."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
from r0_experiment import write_new
from r0_integrity import hashes


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def design_hash(record):
    d=record['scientific']['selected']
    return hashlib.sha256(json.dumps({k:d[k] for k in ('body','vector')},sort_keys=True).encode()).hexdigest()


def verify_archive(ops,root,tag):
    receipt=read(ops/f'{tag}_archive_receipt.json')
    archive=ops/Path(receipt['archive']).name
    assert archive.stat().st_size==receipt['bytes'] and digest(archive)==receipt['sha256']
    expected={line.split('  ',1)[1]:line.split('  ',1)[0]
              for line in (root/'SHA256SUMS').read_text().splitlines()}
    assert hashes(root)==expected and len(expected)==receipt['files_verified']
    return {'archive':archive.name,'sha256':receipt['sha256'],'bytes':receipt['bytes'],
            'files_verified':len(expected),'complete_manifest_match':True}


def main():
    p=argparse.ArgumentParser();p.add_argument('--v1',required=True);p.add_argument('--v2',required=True)
    p.add_argument('--audit',required=True);p.add_argument('--ops',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();v1,v2,audit,ops,out=map(Path,(a.v1,a.v2,a.audit,a.ops,a.out));out.mkdir(parents=True,exist_ok=True)
    archives=[verify_archive(ops,root,tag) for root,tag in ((v1,'v1'),(v2,'v2'),(audit,'postaudit'))]
    write_new(out/'archives_verified.json',{'archives':archives,
              'total_manifest_entries_verified':sum(r['files_verified'] for r in archives),
              'note':'File checks, not independent experimental units. Raw archives remain outside Git.'})
    rows=[];equiv=[];unique=0;verifications=0;plant=twin=verification_eq=0;seed_roles=True
    analysis=read(audit/'analysis.json');original=read(audit/'v1_analysis.json')
    for b in read('experiments/causal_engineer/dev/di1/pilot_config.json')['bases']:
        bid=b['base_id'];complete=read(v1/bid/'complete.json')
        if not complete['eligible']:continue
        inst=read(v1/bid/'instance.json');roles=inst['seeds'];keys=list(roles)
        assert all(not set(roles[x])&set(roles[y]) for i,x in enumerate(keys) for y in keys[i+1:])
        eq=read(v1/bid/'equivalence.json');assert eq['equal'] and eq['original_sha']==eq['instrumented_sha'];equiv.append({'base':bid,**eq})
        conditions=[('baseline',v1,'baseline'),('v1_raw',v1,'raw_eig'),('v1_random',v1,'random'),
                    ('v2_raw',v2,'raw_eig'),('v2_random',v2,'random')]
        recs={label:read(root/bid/f'{mode}.json') for label,root,mode in conditions}
        unique+=len({design_hash(r) for r in recs.values()})
        row={'base':bid,'family_evaluator_only':inst['family'],'parent':b['parent_dev_base']}
        for label,r in recs.items():
            row[label+'_status']=r['verification']['status']
            row[label+'_validation_walking']=r['verification']['validation']['walking_frac']
            row[label+'_plant_eq']=r['scientific']['ledger']['used'];row[label+'_twin_eq']=r['scientific']['ledger']['twin']['used']
            f=r['first_decision'];row[label+'_probe']=f['selected']['id'] if f else 'STOP'
            if label.startswith('v2') and f:
                cands=f['candidates'];allowed=[c[2] for c in cands if f['baseline_would_stop'] or c[2]['id']!=cands[0][2]['id']]
                assert f['selected'] in [c[2] for c in cands]
                if label=='v2_random':assert abs(f['inclusion_probability']-1/len(allowed))<1e-15
                else:assert f['selected']==max(cands,key=lambda c:c[1])[2]
            assert row[label+'_plant_eq']<=700 and row[label+'_twin_eq']<=2800
        rows.append(row)
        # Actual executed episodes: five comparison policies, original baseline
        # equivalence repeat, and one additional default-code repeat on base0.
        actual=[*recs.values(),read(v1/bid/'uninstrumented.json')]
        if b['generator_index']==0:
            assert read(v2/bid/'v2_default_equivalence.json')['equal']
            actual.append(recs['baseline'])  # exact recorded equivalence repeat
        for r in actual:
            verifications+=1;plant+=r['scientific']['ledger']['used'];twin+=r['scientific']['ledger']['twin']['used']
            vr=r['verification']['rollouts'];verification_eq+=vr['validation']+vr['confirmation_rollout_equivalents']
    assert len(rows)==5
    generation=read(audit/'generation_replay/proofs.json');overlap=read(audit/'overlap_proof.json')
    assert generation['all_equal'] and generation['physics_errors']==0 and overlap['exact_scientific_matches']==64
    proof={'new_morphology_attempts':8,'eligible_independent_bases':len(rows),'prospective_evaluation_bases':0,
           'distinct_final_designs_across_both_panels':unique,'comparison_path_records_excluding_reused_baseline':25,
           'actual_policy_and_FULL_equivalence_runs':verifications,'policy_charged_plant_equivalents':plant,
           'policy_charged_twin_equivalents':twin,'independent_verification_equivalents':verification_eq,
           'uniform_generation_replay_jobs':sum(r['jobs'] for r in generation['proofs']),
           'retained_failed_audit_overlap_jobs':64,'seed_roles_disjoint':seed_roles,
           'baseline_equivalence':equiv,'v2_default_equivalence':read(v2/'di1-pilot-20261025-v1-000/v2_default_equivalence.json'),
           'registered_source_hashes_match_at_runtime':read(v2/'environment.json')['all_registered_source_bytes_match'],
           'physics_errors_in_policy_traces':analysis['trace_errors']+original['trace_errors'],
           'canonical_analysis_repeat_stdout_identical':(audit/'analysis_stdout.json').read_bytes()==(audit/'analysis_repeat_stdout.json').read_bytes(),
           'original_v1_analysis_repeated_exactly':(audit/'v1_analysis.json').read_bytes()==(v2/'v1_analysis.json').read_bytes(),
           'qualification_replay':generation,'failed_audit_overlap':overlap,
           'independence_note':'Both pilot versions and all repeats use the same five eligible bases; paths/seeds are not independent robots.'}
    write_new(out/'integrity.json',proof)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    target=out/'comparison.csv';data=buf.getvalue().encode()
    if target.exists():assert target.read_bytes()==data
    else:target.write_bytes(data)
    sources={'v1_analysis.json':audit/'v1_analysis.json','analysis.json':audit/'analysis.json',
             'generation_replay_proof.json':audit/'generation_replay/proofs.json','overlap_proof.json':audit/'overlap_proof.json',
             'guard_tests.txt':audit/'guard_tests.txt','environment.json':v2/'environment.json',
             'audit_source_commit.txt':audit/'audit_source_commit.txt',
             'analysis_stdout.json':audit/'analysis_stdout.json',
             'analysis_repeat_stdout.json':audit/'analysis_repeat_stdout.json',
             'campaign.json':ops/'campaign.json',
             'v1_SHA256SUMS':v1/'SHA256SUMS','v2_SHA256SUMS':v2/'SHA256SUMS','postaudit_SHA256SUMS':audit/'SHA256SUMS',
             'final_control_plane.json':ops/'final_control_plane.json','v1_control_plane.json':ops/'v1_control_plane.json',
             'v2_control_plane.json':ops/'v2_control_plane.json','v1_archive_receipt.json':ops/'v1_archive_receipt.json',
             'v2_archive_receipt.json':ops/'v2_archive_receipt.json','postaudit_archive_receipt.json':ops/'postaudit_archive_receipt.json',
             'native_shutdown_log.txt':ops/'postaudit_completion_and_native_stop.txt'}
    for name,src in sources.items():
        dst=out/name
        if dst.exists():assert digest(dst)==digest(src)
        else:shutil.copyfile(src,dst)
    print(json.dumps({k:v for k,v in proof.items() if k not in ('baseline_equivalence','qualification_replay','failed_audit_overlap')},indent=2))


if __name__=='__main__':main()
