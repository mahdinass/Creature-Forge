"""Bounded resource decision after the fixed DI-1 engineering pilot.

No outcome-dependent method selection. Forecasts do not assert that every
conceivable future design is infeasible. Counts/inputs remain reviewable.
"""
import argparse
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from di1_analyze import required_n,upper_rate
from r0_experiment import write_new


def plan(analysis,root,campaign,status):
    root=Path(root);n=analysis['planning_n'];seconds_per_eq=[];qualification=0
    for row in analysis['rows']:
        d=root/row['base']
        th=json.loads((d/'threshold.json').read_text())
        qualification+=8+8*len(th['trace'])+8
        for mode in ('baseline','raw_eig','random'):
            r=json.loads((d/f'{mode}.json').read_text());v=r['verification']['rollouts'];ledger=r['scientific']['ledger']
            eq=ledger['used']+ledger['twin']['used']+v['validation']+v['confirmation_rollout_equivalents']
            seconds_per_eq.append(r['wall_s']/eq)
    if not seconds_per_eq:raise ValueError('no comparable pilot policy runtime')
    # Measured six-worker path seconds/equivalent. Eight such paths fit48 CPUs.
    rate=max(seconds_per_eq);cap=700+2800+96
    # Qualification/generation overhead uses worst allowed64 per attempted base;
    # additional attempts use a conservative binomial-reference acceptance bound.
    qualified=analysis['independent_bases'];accept_lower=1-upper_rate(8-qualified,8,.025) if qualified else 0
    attempts=math.ceil(n/accept_lower) if accept_lower else None
    eq=n*3*cap+(attempts*72 if attempts else 0)
    forecast_h=1.25*rate*eq/8/3600
    spent=status['ledger']['usd']-campaign['initial_spend_usd']
    elapsed_h=(status['checked_epoch']-campaign['first_start_epoch'])/3600
    cost=status.get('rate',status.get('batch_quoted_rate'))['total_usd_per_h']
    remaining_h=max(0,min(6-elapsed_h-5/60,(12-spent-.5)/cost,
                          (campaign['hard_stop_epoch']-status['checked_epoch'])/3600))
    # A bound on population discordance from this small, partially excluded,
    # fixed-family engineering panel is not a validated iid population estimate.
    # Also show the unknown-population (max variance) conservative requirement.
    worst=required_n(1.)
    worst_n=worst if worst is not None else 801
    worst_h=1.25*rate*worst_n*3*cap/8/3600
    fits=forecast_h<=remaining_h and qualified>=1
    return {'stage':'prospective launch feasibility','measured_pilot_path_seconds_per_equivalent_max':rate,
            'planning_independent_eval_bases':n,'three_path_cap_equivalents_per_base':3*cap,
            'qualification_acceptance_reference_lower95':accept_lower,'projected_generation_attempts':attempts,
            'forecast_hours_with25pct':forecast_h,'forecast_additional_cloud_usd':forecast_h*cost,
            'already_conservative_spent_usd':spent,'elapsed_campaign_hours':elapsed_h,
            'remaining_authorized_hours_with_finalization_reserve':remaining_h,
            'working_model_fits':fits,'worst_discordance_required_n':worst or '>800',
            'worst_discordance_forecast_hours_at_least':worst_h,
            'decision':'NE_NO_GO' if not fits else 'REQUIRES_FINAL_REGISTRATION',
            'inference_limit':'Pilot fixed family strata and qualification exclusions do not validate iid population discordance. Binomial rate bounds/power are planning references, not confirmatory population inference.',
            'power_limit':'Contrast-only90% power each gives >=80% joint by union bound. Other practical-effect, prevalence and negative-transfer conditions can need more information.',
            'cost_limit':'Ledger estimates, not invoices/current credit. Rate includes batch compute/disk; reserve covers finalization and other storage.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--analysis',required=True);p.add_argument('--root',required=True)
    p.add_argument('--campaign',required=True);p.add_argument('--status',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();result=plan(*[json.loads(Path(a.analysis).read_text()),a.root,
                                  json.loads(Path(a.campaign).read_text()),json.loads(Path(a.status).read_text())])
    write_new(a.out,result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
