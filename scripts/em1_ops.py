"""EM-1 task limits over existing SA lifecycle tooling; no new infrastructure."""
import argparse
import json
from pathlib import Path
import time
import r0_nebius as ops


def limits(c,spend,now):
    return min(6-(now-c['first_start_epoch'])/3600-5/60,
               (1793098800-now)/3600), min(12,c['cloud_credit_usd'])-(spend-c['initial_spend_usd'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--ops-root',required=True)
    p.add_argument('--campaign',default='artifacts/em1_ops/campaign.json')
    p.add_argument('cmd',choices=('status','start','stop'));p.add_argument('--hours',type=float,default=.5)
    p.add_argument('--credit',type=float);a=p.parse_args()
    fc=ops.cloud(a.ops_root,'batch');st=ops.states(fc);spend=fc.spend_all()
    if a.cmd=='status':
        print(json.dumps({'checked_epoch':time.time(),'states':st,'ledger':spend,'rate':fc.costs()},indent=2));return
    if a.cmd=='stop':
        if st['batch']['state']!='STOPPED':fc.cmd_stop()
        print(json.dumps(ops.states(fc),indent=2));return
    path=Path(a.campaign)
    if not path.exists():
        if a.credit!=26.51:raise ValueError('requires owner verified current Cloud credit')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'first_start_epoch':time.time(),'initial_spend_usd':spend['usd'],
          'cloud_credit_usd':a.credit,'token_credit_usd':47.,'cloud_cap_usd':12.,'token_cap_usd':3.,
          'max_hours':6.,'credit_source':'Owner confirmed current balances in EM-1 chat on 2026-10-25'},indent=2))
    c=json.loads(path.read_text());hours,dollars=limits(c,spend['usd'],time.time())
    if not 0<a.hours<=hours or a.hours*fc.costs()['total_usd_per_h']+.5>dollars:
        raise ValueError('requested run exceeds EM1 time/credit authorization')
    if st['main']['state']!='STOPPED' or st['batch']['state']!='STOPPED':
        raise ValueError('do not take over another active workload')
    fc.SPEND_CAP_USD=c['initial_spend_usd']+min(12,c['cloud_credit_usd'])
    fc.CFG['default_deadline_h']=a.hours;fc.cmd_start()
    print(json.dumps({'states':ops.states(fc),'campaign':c,'deadline_epoch':fc.load()['deadline_epoch']},indent=2))

if __name__=='__main__':main()
