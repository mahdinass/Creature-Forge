"""Verify BOTH control-plane states, reconcile a native API stop, save receipt.

Only normal existing ledger state is updated, after explicit STOPPED reads.
Does not stop or take over an unrelated workload. A running VM is an error.
"""
import argparse
import json
from pathlib import Path
import time
import r0_nebius as ops
from r0_experiment import write_new


def main():
    p=argparse.ArgumentParser();p.add_argument('--ops-root',required=True)
    p.add_argument('--campaign',default='artifacts/di1_ops/campaign.json');p.add_argument('--out',required=True)
    a=p.parse_args();fc=ops.cloud(a.ops_root,'batch');st=ops.states(fc);now=time.time()
    if any(s['state']!='STOPPED' for s in st.values()):raise ValueError('both VMs must be API STOPPED')
    c=json.loads(Path(a.campaign).read_text());fc.SPEND_CAP_USD=c['initial_spend_usd']+min(12,c['cloud_credit_usd'])
    events=fc.spend_events(fc.SPEND)
    last_start=max((e['epoch'] for e in events if e['event']=='start'),default=0)
    last_stop=max((e['epoch'] for e in events if e['event']=='stop'),default=0)
    if last_start>last_stop:
        if last_start<c['first_start_epoch']-5:raise ValueError('last start is not DI1')
        fc.spend_record('stop',epoch=now,by='di1_native_stop_control_plane_observed')
    ledger=fc.spend_all();elapsed=(now-c['first_start_epoch'])/3600
    receipt={'checked_epoch':now,'states':st,'ledger':ledger,'rate':fc.costs(),
             'additional_cloud_estimate_usd':round(ledger['usd']-c['initial_spend_usd'],3),
             'conservative_paid_batch_hours':round(ledger['profiles']['batch']['compute_h']-46.112,3),
             'elapsed_campaign_hours':elapsed,'token_factory_usd':0.,
             'limits':{'cloud_usd':12,'token_usd':2,'paid_vm_hours':6,'hard_stop_epoch':c['hard_stop_epoch']},
             'credit_evidence':c['credit_source'],
             'billing_caveat':'Conservative local start-to-observed-API-stop estimates, not invoice or current balance.'}
    write_new(a.out,receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
