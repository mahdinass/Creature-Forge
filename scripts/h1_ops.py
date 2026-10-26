"""H1 scoped limits over existing SA lifecycle; no new IAM or services."""
import argparse
import json
import math
from pathlib import Path
import time
import r0_nebius as ops


def limits(c,spend,now):
    vals=(spend,now,c['initial_spend_usd'],c['first_start_epoch'],c['credit']['available_usd'])
    if not all(math.isfinite(float(x)) for x in vals):raise ValueError('nonfinite resource state')
    return max(0,5.5-(now-c['first_start_epoch'])/3600), min(25,c['credit']['available_usd']-5)-max(0,spend-c['initial_spend_usd'])


def main():
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=('status','start','stop'))
    p.add_argument('--ops-root',required=True);p.add_argument('--campaign',default='artifacts/h1_ops/campaign.json')
    p.add_argument('--credit-evidence');p.add_argument('--hours',type=float,default=1);a=p.parse_args()
    fc=ops.cloud(a.ops_root,'batch');st=ops.states(fc);spend=fc.spend_all();root=Path(a.campaign).parent
    root.mkdir(parents=True,exist_ok=True)
    receipt={'checked_epoch':time.time(),'states':st,'ledger':spend,'rate':fc.costs()}
    if a.cmd=='status':
        (root/f'status_{time.time_ns()}.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2));return
    if a.cmd=='stop':
        if st['batch']['state']!='STOPPED':fc.cmd_stop()
        print(json.dumps(ops.states(fc),indent=2));return
    if any(s['state']!='STOPPED' for s in st.values()):raise ValueError('no active workload takeover')
    path=Path(a.campaign)
    if not path.exists():
        credit=json.loads(Path(a.credit_evidence).read_text())
        if not credit.get('source') or not 0<=time.time()-credit['verified_epoch']<=3600 or not math.isfinite(credit['available_usd']) or credit['available_usd']<=5:
            raise ValueError('fresh verified credit and reserve required')
        path.write_text(json.dumps({'first_start_epoch':time.time(),'initial_spend_usd':spend['usd'],
          'credit':credit,'cloud_cap_usd':25,'paid_batch_cap_hours':6,'token_cap_usd':0},indent=2))
    c=json.loads(path.read_text());hours,dollars=limits(c,spend['usd'],time.time())
    if not math.isfinite(a.hours) or not 0<a.hours<=hours or (a.hours+.35)*fc.costs()['total_usd_per_h']+.5>dollars:
        raise ValueError('window plus operational reserve exceeds authorization')
    fc.SPEND_CAP_USD=c['initial_spend_usd']+min(25,c['credit']['available_usd']-5)
    fc.CFG['default_deadline_h']=a.hours;fc.cmd_start()
    receipt={'epoch':time.time(),'states':ops.states(fc),'deadline_epoch':fc.load()['deadline_epoch'],'campaign':c}
    (root/f'start_{time.time_ns()}.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
