"""Export small VEL-2 evidence without modifying any original or frozen study."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from r0_experiment import write_new
from vel2_audit import audit

ROOT=Path(__file__).resolve().parents[1]


def export():
    raw=ROOT/'artifacts/vel2_ops/extracted/vel2_stage_a'
    ops=ROOT/'artifacts/vel2_ops';study=ROOT/'experiments/causal_engineer/dev/vel2'
    out=study/'results';out.mkdir(exist_ok=True)
    for p in raw.rglob('*'):
        if p.is_file():
            q=out/'native'/p.relative_to(raw);q.parent.mkdir(parents=True,exist_ok=True)
            if q.exists() and q.read_bytes()!=p.read_bytes():raise ValueError('immutable export differs')
            if not q.exists():q.write_bytes(p.read_bytes())
    independent=audit(study,raw)
    write_new(out/'independent_audit.json',independent)
    for name in ('credit.json','campaign.json','initial_control_plane.json','final_control_plane.json',
                 'archive_transfer.json','campaign_ledger_events.json',
                 'vel2_stage_a_launch_error_journal.txt','vel2_stage_a_1792973661593156959.tgz',
                 'status_1792973743692438900.json','status_1792974130681793700.json'):
        p=ops/name;q=out/'operations'/name;q.parent.mkdir(exist_ok=True)
        if q.exists() and q.read_bytes()!=p.read_bytes():raise ValueError('immutable operations export differs')
        if not q.exists():q.write_bytes(p.read_bytes())
    initial=json.loads((ops/'initial_control_plane.json').read_text())
    final=json.loads((ops/'final_control_plane.json').read_text())
    c=json.loads((ops/'campaign.json').read_text())
    write_new(out/'resources.json',{'cloud_quote_ledger_increment_usd':round(final['ledger']['usd']-initial['ledger']['usd'],3),
      'cloud_cap_usd':6,'token_factory_actual_usd':0,'token_factory_calls':0,
      'new_physics_equivalents':independent['new_equivalents'],'new_verifier_panels':30,
      'known_lineages':15,'new_lineages':0,'batch_compute_ledger_hours_increment':round(final['ledger']['profiles']['batch']['compute_h']-initial['ledger']['profiles']['batch']['compute_h'],3),
      'main_compute_ledger_hours_increment':round(final['ledger']['profiles']['main']['compute_h']-initial['ledger']['profiles']['main']['compute_h'],3),
      'physics_wall_s':json.loads((raw/'complete.json').read_text())['wall_s'],
      'first_start_epoch':c['first_start_epoch'],'final_api_checked_epoch':final['checked_epoch'],
      'both_api_stopped':all(x['state']=='STOPPED' for x in final['states'].values()),
      'cost_limit':'Conservative quote-based local ledger, not provider invoice or current available account balance; includes delayed API observation and storage.'})
    write_new(out/'decision.json',{'verdict':'NO-GO','scope':'tested stable single-panel FULL label prerequisite; do not advance frozen design to Stage B',
      'stage_a_gate':False,'stage_b_executed':False,'general_experience_hypothesis':'INSUFFICIENT EVIDENCE; not rejected',
      'predictive_models_evaluated':False,'action_or_recovery_gain_identified':False,'frozen_commit':(raw/'source_commit.txt').read_text().strip()})
    from vel2_repeatability import load
    load(study)
    frozen=json.loads((study/'stage_a_source_hashes.json').read_text())
    for p,h in frozen.items():
        assert hashlib.sha256((ROOT/p).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==h,p
    write_new(out/'source_audit.json',{'frozen_source_files_lf_verified':len(frozen),
      'source_commit':(raw/'source_commit.txt').read_text().strip(),
      'cases_sha256':hashlib.sha256((study/'stage_a_cases.json').read_bytes()).hexdigest(),
      'native_archive_sha256':hashlib.sha256((ops/'stage_a_native.tgz').read_bytes()).hexdigest(),
      'native_manifest_verified':43,'prior_studies_untouched':True})
    print(json.dumps({'export_files':sum(p.is_file() for p in out.rglob('*')),
                      'export_bytes':sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),
                      'source_files_verified':len(frozen),'gate':False},indent=2))


def manifest():
    study=ROOT/'experiments/causal_engineer/dev/vel2'
    paths=[p for p in study.rglob('*') if p.is_file() and p.name!='EVIDENCE_SHA256SUMS']
    paths+=list((ROOT/'docs').glob('VEL2_*.md'))
    paths+=[ROOT/p for p in ('scripts/vel2_repeatability.py','scripts/vel2_ops.py','scripts/vel2_native.sh',
                             'scripts/vel2_audit.py','scripts/vel2_closeout.py','tests/test_vel2.py')]
    receipt=''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in sorted(paths))
    target=study/'EVIDENCE_SHA256SUMS'
    if target.exists() and target.read_text()!=receipt:raise ValueError('manifest already exists with different bytes')
    target.write_text(receipt,encoding='utf-8',newline='\n')
    print('evidence files',len(paths))


if __name__=='__main__':
    if sys.argv[1:]==['manifest']:manifest()
    else:export()
