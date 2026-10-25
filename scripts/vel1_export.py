"""Compact immutable VEL-1 report/evidence publication; no new science or physics."""
import argparse
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vel1_audit import read,sha,FEATURES
from r0_experiment import write_new


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    root=Path(a.root);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    mapping={'audit.json':'audit_v2/audit.json','fresh_v5_rows.json':'audit_v2/fresh_v5_rows.json',
             'di1_rows.json':'audit_v2/di1_rows.json','duplicates.json':'audit_v2/duplicates.json',
             'analysis.json':'analysis_experience/analysis.json','predictions.json':'analysis_experience/predictions.json',
             'fold_proofs.json':'analysis_experience/fold_proofs.json','preliminary_analysis.json':'analysis_v1/analysis.json',
             'report_diagnostics.json':'report_closeout/report_diagnostics.json','V1_fold_models.json':'report_closeout/V1_fold_models.json',
             'integrity.json':'report_closeout/integrity.json','initial_control_plane.json':'initial_control_plane.json',
             'final_control_plane.json':'final_control_plane.json','guard_tests.txt':'guard_tests.txt',
             'reanalysis_receipt.json':'reanalysis_receipt.json','analysis_stdout.json':'experience_stdout.json',
             'analysis_repeat_stdout.json':'reanalysis_stdout.json'}
    for name,path in mapping.items():
        src=root/path;dst=out/name
        if dst.exists():
            if src.read_bytes()!=dst.read_bytes():raise ValueError(f'immutable export changed {name}')
        else:shutil.copyfile(src,dst)
    analysis=read(out/'analysis.json');pre=read(out/'preliminary_analysis.json')
    for mode in ('lobo','dual_base_family_out'):
        for subset in ('all','apparent'):
            for model in ('constant','V0_walking','V0_beta','V0_map_confidence','V0_legacy_stopmap','V1a_robust_calibration','V1_physical'):
                assert pre[mode][subset][model]==analysis[mode][subset][model]
    assert (out/'analysis_stdout.json').read_bytes()==(out/'analysis_repeat_stdout.json').read_bytes()
    initial,final=(read(out/f'{stage}_control_plane.json') for stage in ('initial','final'))
    assert all(x['state']=='STOPPED' for r in (initial,final) for x in r['states'].values())
    assert all(initial['ledger']['profiles'][k]['compute_h']==final['ledger']['profiles'][k]['compute_h'] for k in ('main','batch'))
    write_new(out/'resources.json',{'new_VM_starts':0,'new_physical_rollouts':0,'new_model_calls':0,
              'additional_compute_usd':0,'token_factory_usd':0,'paid_feasibility_measurement':False,
              'initial_ledger_usd':initial['ledger']['usd'],'final_ledger_usd':final['ledger']['usd'],
              'ledger_difference_usd':round(final['ledger']['usd']-initial['ledger']['usd'],6),
              'compute_hours_unchanged':True,'both_VM_states_STOPPED':True,'final_checked_epoch':final['checked_epoch'],
              'caveat':'No new compute/inference; pre-existing disk storage accrues. Local ledger is not provider invoice/current credit.'})
    audit=read(out/'audit.json');app=analysis['lobo']['apparent']
    write_new(out/'decision.json',{'study':'VEL-1 feasibility only','date':'2026-10-26','verdict':'INSUFFICIENT EVIDENCE',
              'recommendation':'Do not implement/deploy complete experience learning; no follow-on experiment initiated.',
              'target_identifiable':True,'primary_body_groups':18,'apparent_body_groups':17,
              'apparent_submissions':115,'apparent_failures':27,'apparent_failure_groups':14,
              'V1_brier':app['V1_physical']['brier'],'V2_brier':app['V2_experience']['brier'],
              'V1_gain_over_simple_calibration':app['paired_brier_improvement']['V1_physical_vs_V1a_robust_calibration'],
              'V2_gain_over_V1':app['paired_brier_improvement']['V2_experience_vs_V1_physical'],
              'V2_gain_over_shuffled':app['paired_brier_improvement']['V2_experience_vs_V3_shuffled'],
              'main_plan_screen_passed':False,'experience_screen_passed':False,
              'counterfactual_FULL_action_effect_identified':False,'Nemotron_adaptation_tested':False,
              'reasons':['Richer risk signal beyond simple calibration lacks a positive paired-base interval.',
                         'Relevant residual memory does not outperform V1 or shuffled memory.',
                         'Independent family transfer/replicate-label stability and compatible warning-action FULL outcomes are insufficient.'],
              'preliminary_model_scores_unchanged':True,'canonical_repeat_exact':True,
              'postfit_diagnostic':'Context-matched training prevalence and fold coefficient/source audit only; main methods unchanged.'})
    def blob(rev,path):return subprocess.check_output(['git','show',f'{rev}:{path}'])
    core=['creature_forge/belief_engine.py','creature_forge/hdb_workbench.py','creature_forge/hdb_bench.py','creature_forge/eng_tools.py',
          'creature_forge/recovery.py','creature_forge/hidden_plant.py','scripts/hdb_vs_run.py','scripts/hdb_stop_calibration.py',
          'scripts/rl1_matrix.py','scripts/r0_experiment.py','creature_forge/r0_repair.py','scripts/di1_study.py']
    source={'plan_commit':subprocess.check_output(['git','rev-parse','63df2c1'],text=True).strip(),
            'fitted_model_source_commit':subprocess.check_output(['git','rev-parse','8c65b44'],text=True).strip(),
            'plan_sha256':sha(blob('63df2c1','docs/VEL1_FEASIBILITY_PLAN.md')),
            'model_audit_test_git_blob_sha256':{f:sha(blob('8c65b44',f)) for f in ('scripts/vel1_analyze.py','scripts/vel1_audit.py','tests/test_vel1.py')},
            'inherited_timing_verifier_method_source_git_blob_sha256':{f:sha(blob('8c65b44',f)) for f in core},
            'report_export_helpers_sha256_lf':{f:sha(Path(f).read_bytes().replace(b'\r\n',b'\n')) for f in ('scripts/vel1_report.py','scripts/vel1_export.py')},
            'data_source_index':'audit.json sources and prepared row source hashes',
            'environment':analysis['environment'],'no_claim_of_cross_version_bit_exact_replay':True}
    write_new(out/'source_provenance.json',source)
    table=io.StringIO(newline='');writer=csv.writer(table)
    writer.writerow(['cohort','distinct_candidates','body_groups','instances','full','nonfull','apparent','apparent_nonfull'])
    for k,r in audit['cohorts'].items():writer.writerow([k,*[r[f] for f in ('labeled','independent_body_groups','damage_instances','full','nonfull','apparent_decisions','apparent_failures')]])
    dst=out/'cohorts.csv';data=table.getvalue().encode()
    if dst.exists():assert dst.read_bytes()==data
    else:dst.write_bytes(data)
    print(json.dumps({'exported_files':len(mapping),'primary_counts':audit['cohorts']['fresh_v5'],
                      'decision':'INSUFFICIENT EVIDENCE','resources':read(out/'resources.json')},indent=2))


if __name__=='__main__':main()
