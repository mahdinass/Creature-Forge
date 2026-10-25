"""DI-1 limits over existing service-account lifecycle; no new IAM or VM."""
import argparse
import json
import math
from pathlib import Path
import time
import r0_nebius as ops

HARD_STOP = 1793098800  # 2026-10-27 11:00 UTC / 12:00 Europe/Oslo


def limits(c, spend, now):
    if not all(math.isfinite(float(x)) for x in (spend, now, c['first_start_epoch'], c['initial_spend_usd'], c['cloud_credit_usd'])):
        raise ValueError('nonfinite resource state')
    return max(0, min(6-(now-c['first_start_epoch'])/3600-5/60, (HARD_STOP-now)/3600)), \
        min(12,c['cloud_credit_usd'])-max(0,spend-c['initial_spend_usd'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--ops-root',required=True)
    p.add_argument('--campaign',default='artifacts/di1_ops/campaign.json')
    p.add_argument('cmd',choices=('status','start','stop'));p.add_argument('--hours',type=float,default=1)
    p.add_argument('--credit',type=float);a=p.parse_args()
    fc=ops.cloud(a.ops_root,'batch');st=ops.states(fc);spend=fc.spend_all()
    if a.cmd=='status':
        receipt={'checked_epoch':time.time(),'states':st,'ledger':spend,'rate':fc.costs()}
        print(json.dumps(receipt,indent=2));return
    if a.cmd=='stop':
        if st['batch']['state']!='STOPPED':fc.cmd_stop()
        print(json.dumps(ops.states(fc),indent=2));return
    path=Path(a.campaign)
    if not path.exists():
        if a.credit!=23.28:raise ValueError('requires owner-verified current DI1 Cloud credit')
        if st['main']['state']!='STOPPED' or st['batch']['state']!='STOPPED':raise ValueError('no active workload takeover')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'first_start_epoch':time.time(),'initial_spend_usd':spend['usd'],
          'cloud_credit_usd':a.credit,'token_credit_usd':47.,'cloud_cap_usd':12.,'token_cap_usd':2.,
          'max_hours':6.,'hard_stop_epoch':HARD_STOP,
          'credit_source':'Owner confirmed current DI-1 balances in chat 2026-10-25'},indent=2))
    c=json.loads(path.read_text());hours,dollars=limits(c,spend['usd'],time.time())
    if not math.isfinite(a.hours) or not 0<a.hours<=hours or a.hours*fc.costs()['total_usd_per_h']+.5>dollars:
        raise ValueError('requested run exceeds DI1 time/credit authorization')
    if st['main']['state']!='STOPPED' or st['batch']['state']!='STOPPED':raise ValueError('no active workload takeover')
    fc.SPEND_CAP_USD=c['initial_spend_usd']+min(12,c['cloud_credit_usd'])
    fc.CFG['default_deadline_h']=a.hours;fc.cmd_start()
    print(json.dumps({'states':ops.states(fc),'campaign':c,'deadline_epoch':fc.load()['deadline_epoch']},indent=2))


if __name__=='__main__':main()
