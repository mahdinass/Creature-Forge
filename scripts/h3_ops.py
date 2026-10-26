"""Approved H3 lifecycle envelope over existing SA/deadline operations, no new IAM.

Science sources and frozen plan are untouched. Main must remain STOPPED.
"""
import argparse
import json
import math
from pathlib import Path
import time

import r0_nebius as ops

PLAN_SHA='c5eea6daddaf90c9ed2cef598dce0b45919e6c9bbcef8226b456b0412e988bdd'


def remaining(auth,campaign,spend,now):
    values=(auth['authorized_epoch'],auth['deadline_epoch'],campaign['initial_spend_usd'],
            campaign['first_start_epoch'],auth['credit']['available_usd'],spend,now)
    if not all(math.isfinite(float(x)) for x in values):raise ValueError('nonfinite resource state')
    hard=min(auth['deadline_epoch'],campaign['first_start_epoch']+3*3600)
    hours=max(0,(hard-now-900)/3600)  # independent watchdog's full 15-minute lag
    dollars=min(8,auth['credit']['available_usd']-5)-max(0,spend-campaign['initial_spend_usd'])
    return hours,dollars,hard


def main():
    p=argparse.ArgumentParser();p.add_argument('cmd',choices=('status','start','stop'))
    p.add_argument('--ops-root',required=True);p.add_argument('--authorization',required=True)
    p.add_argument('--campaign',default='artifacts/h3_ops/campaign.json')
    p.add_argument('--hours',type=float,help='optional shorter window, e.g. evidence retrieval only');a=p.parse_args()
    auth=json.loads(Path(a.authorization).read_text(encoding='utf-8'))
    if (auth.get('study')!='h3-pilot-v1' or auth.get('protocol_sha256')!=PLAN_SHA or
        auth.get('cloud_cap_usd')!=8 or auth.get('token_factory_cap_usd')!=0 or not auth.get('human_message_reference')):
        raise ValueError('H3-specific explicit authorization required')
    fc=ops.cloud(a.ops_root,'batch');states=ops.states(fc);spend=fc.spend_all();now=time.time()
    receipt={'checked_epoch':now,'states':states,'ledger':spend,'rate':fc.costs()}
    path=Path(a.campaign);root=path.parent;root.mkdir(parents=True,exist_ok=True)
    if a.cmd=='status':
        if states['batch']['state']=='STOPPED' and fc.spend_events() and fc.spend_events()[-1]['event'] in ('start','extend'):
            fc.spend_record('stop',by='h3_API_STOPPED_observation');receipt['ledger']=fc.spend_all()
        (root/f'status_{time.time_ns()}.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        print(json.dumps(receipt,indent=2));return
    if a.cmd=='stop':
        if states['batch']['state']!='STOPPED':fc.cmd_stop()
        elif fc.spend_events() and fc.spend_events()[-1]['event'] in ('start','extend'):
            fc.spend_record('stop',by='h3_API_STOPPED_observation')
        result={'checked_epoch':time.time(),'states':ops.states(fc),'ledger':fc.spend_all()}
        (root/f'stop_{time.time_ns()}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2));return
    if any(s['state']!='STOPPED' for s in states.values()):raise ValueError('no active-workload takeover')
    credit=auth['credit']
    if not credit.get('source') or not 0<=now-credit['verified_epoch']<=3600 or credit['available_usd']<13:
        raise ValueError('fresh capacity for USD8 plus USD5 reserve required')
    if path.exists():c=json.loads(path.read_text(encoding='utf-8'))
    else:
        c={'study':'h3-pilot-v1','first_start_epoch':now,'initial_spend_usd':spend['usd'],
           'initial_compute_h':{k:v['compute_h'] for k,v in spend['profiles'].items()},'authorization':auth}
        with path.open('x',encoding='utf-8') as f:json.dump(c,f,indent=2)
    hours,dollars,hard=remaining(auth,c,spend['usd'],now)
    if a.hours is not None:
        if not math.isfinite(a.hours) or not 0<a.hours<=hours:raise ValueError('requested window exceeds remaining authorization')
        hours=a.hours
    if hours<.1 or (hours+.25)*fc.costs()['total_usd_per_h']+.3>dollars:raise ValueError('bounded window no longer affordable')
    if fc.auth_horizon(fc.auth_expiry())<hard:raise ValueError('SA lifetime cannot cover hard shutdown')
    fc.SPEND_CAP_USD=c['initial_spend_usd']+min(8,credit['available_usd']-5)
    fc.CFG['default_deadline_h']=hours
    # The independent local watchdog is armed before the start request.
    st=fc.load();st['deadline_epoch']=int(hard-900);fc.save(st)
    if not (root/'initial_provider_state.json').exists():
        (root/'initial_provider_state.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (root/f'prestart_{time.time_ns()}.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    try:
        fc.cmd_start()
        deadline=min(int(hard-900),int(time.time()+hours*3600))
        fc.ssh(f'printf "%s\\n" {deadline} | sudo tee /var/lib/forge/deadline >/dev/null',timeout=45)
        if fc.remote_deadline()!=deadline:raise ValueError('native deadline mismatch')
        st=fc.load();st['deadline_epoch']=deadline;fc.save(st);fc.spend_record('extend',deadline=deadline,by='h3_scoped_guard')
        result={'checked_epoch':time.time(),'states':ops.states(fc),'deadline_epoch':deadline,
                'hard_cutoff_epoch':hard,'ledger':fc.spend_all(),'campaign':c}
        (root/f'start_{time.time_ns()}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    except BaseException:
        fc.cmd_stop();raise


if __name__=='__main__':main()
