"""Independent stdlib-only replay of H3 T1/T2 saved records, never physics.

Added after acquisition to audit the already frozen entry rule, not to select a
new population or alter a threshold. Reads tar members without extraction.
"""
import argparse
import collections
import hashlib
import gzip
import json
import math
from pathlib import Path, PurePosixPath
import tarfile


def audit(archive,plan_path,expected_sha):
    archive=Path(archive);raw=archive.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('outer archive hash mismatch')
    with tarfile.open(archive,'r:gz') as t:
        data={}
        for m in t.getmembers():
            p=PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='h3_pilot_v1':raise ValueError('unsafe member')
            if m.isdir():continue
            if not m.isfile() or m.name in data:raise ValueError('non-file/duplicate archive member')
            data[m.name]=t.extractfile(m).read()
    prefix='h3_pilot_v1/'
    def read(path):return json.loads(data[prefix+path])
    def manifest(sub):
        base=prefix+sub;items={}
        for line in data[base+'SHA256SUMS'].decode().splitlines():
            sha,name=line.split('  ',1)
            if name in items or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:raise ValueError('manifest path')
            assert hashlib.sha256(data[base+name]).hexdigest()==sha,name
            items[name]=sha
        if sub:
            actual={p[len(base):] for p in data if p.startswith(base) and p!=base+'SHA256SUMS'}
            assert set(items)==actual,'unit manifest coverage'
        return len(items)
    outer_count=manifest('');gate_count=manifest('gate/');qual_count=manifest('qualify/')
    plan=json.loads(Path(plan_path).read_text(encoding='utf-8'))
    plan_sha=hashlib.sha256(Path(plan_path).read_bytes()).hexdigest()
    g,q=read('gate/result.json'),read('qualify/result.json')
    assert g['plan_sha256']==q['plan_sha256']==plan_sha
    assert g['passed'] and g['seed_job_identity'] and len(g['zero_gain_native'])==6
    assert all(r['trace_equal'] for r in g['zero_gain_native'])
    assert (g['rollouts_reserved'],g['equivalents_reserved'])==(24,24)
    accepted={'left':[],'right':[]};counts=collections.Counter();per=[];ri=0
    for d in plan['draws']:
        if all(len(v)==6 for v in accepted.values()):break
        if len(accepted[d['side']])==6:continue
        r=q['records'][ri];ri+=1
        assert r['id']==d['id'] and read('qualify/'+r['id']+'.json')==r
        values=[]
        for key,seed_key in (('healthy10','qual_healthy10'),('healthy20','qual_healthy20'),('damaged','qual_damaged')):
            rows=r[key];assert len(rows)==8 and [x['seed'] for x in rows]==d[seed_key]
            for x in rows:
                assert x['outcome'] in ('PASS','POOR','FAIL') and not x.get('error')
                assert x['walking']==(x['outcome']=='PASS') and math.isfinite(x['score'])
            values.append(sum(x['outcome']=='PASS' for x in rows))
        h10,h20,dam=values;keep=h10>=7 and h20>=7 and dam<=1
        assert r['accepted']==keep
        counts['attempted_roots']+=1;counts[d['side']+'_attempted']+=1
        counts['nominal10_pass']+=h10>=7;counts['nominal20_pass']+=h20>=7
        counts['both_nominal_pass']+=h10>=7 and h20>=7;counts['damaged_failure_entry_pass']+=dam<=1
        counts['eligible']+=keep
        if keep:accepted[d['side']].append(d['id'])
        per.append({'id':d['id'],'side':d['side'],'nominal10_walking':h10,'nominal20_walking':h20,
                    'damaged10_walking':dam,'eligible':keep})
    assert ri==len(q['records']) and accepted==q['accepted']
    passed=all(len(v)==6 for v in accepted.values());assert q['passed']==passed
    assert q['rollouts_reserved']==24*ri and q['equivalents_reserved']==32*ri
    for unit in ('gate','qualify'):
        rows=[json.loads(s) for s in data[prefix+unit+'/reserved.jsonl'].decode().splitlines()]
        previous=(0,0)
        for r in rows:
            assert r['rollouts']>previous[0] and r['equivalents']>previous[1]
            previous=(r['rollouts'],r['equivalents'])
        result=g if unit=='gate' else q
        assert previous==(result['rollouts_reserved'],result['equivalents_reserved'])
    cases=[p for p in data if p.startswith(prefix+'cases/')]
    finish=read('finish.json')
    if not passed:assert not cases and finish['exit_code']==20
    return {'audit_passed':True,'outer_sha256':expected_sha,'outer_manifest_entries':outer_count,
      'gate_manifest_entries':gate_count,'qualification_manifest_entries':qual_count,
      'plan_sha256':plan_sha,'native_gate_passed':True,'qualification_passed':passed,
      'decision':'NO-GO: qualification' if not passed else 'qualification passed; inspect downstream evidence',
      'counts':dict(counts),'accepted':accepted,'per_root':per,'qualification_errors':0,
      'gate_rollouts':24,'qualification_rollouts':q['rollouts_reserved'],
      'total_rollouts':24+q['rollouts_reserved'],'total_ten_second_equivalents':24+q['equivalents_reserved'],
      'optimizer_rollouts':0 if not cases else None,'full_recovery_assessments':0 if not cases else None,
      'native_source_commit':data[prefix+'source_commit.txt'].decode().strip(),
      'interpretation':'Acquisition gate only; residual recovery efficacy and AI learning not evaluated.'}


def main():
    p=argparse.ArgumentParser();group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--archive');group.add_argument('--qualification',help='science-only native qualification JSON.gz; no authorization/account metadata')
    p.add_argument('--plan',required=True);p.add_argument('--sha256',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if a.archive:result=audit(a.archive,a.plan,a.sha256)
    else:
        raw=Path(a.qualification).read_bytes();assert hashlib.sha256(raw).hexdigest()==a.sha256
        q=json.loads(gzip.decompress(raw));plan=json.loads(Path(a.plan).read_text(encoding='utf-8'))
        assert q['plan_sha256']==hashlib.sha256(Path(a.plan).read_bytes()).hexdigest()
        accepted={'left':[],'right':[]};ri=0;rows=0
        for d in plan['draws']:
            if all(len(v)==6 for v in accepted.values()):break
            if len(accepted[d['side']])==6:continue
            r=q['records'][ri];ri+=1;assert r['id']==d['id'];n=[]
            for key,sk in (('healthy10','qual_healthy10'),('healthy20','qual_healthy20'),('damaged','qual_damaged')):
                rr=r[key];assert len(rr)==8 and [x['seed'] for x in rr]==d[sk]
                assert all(not x.get('error') and x['outcome'] in ('PASS','POOR','FAIL') and x['walking']==(x['outcome']=='PASS') and math.isfinite(x['score']) for x in rr)
                rows+=len(rr);n.append(sum(x['outcome']=='PASS' for x in rr))
            keep=n[0]>=7 and n[1]>=7 and n[2]<=1;assert r['accepted']==keep
            if keep:accepted[d['side']].append(d['id'])
        assert ri==len(q['records']) and accepted==q['accepted']
        assert q['rollouts_reserved']==24*ri and q['equivalents_reserved']==32*ri
        passed=all(len(v)==6 for v in accepted.values());assert passed==q['passed']
        result={'audit_passed':True,'mode':'portable science-only entry-rule replay; native archive manifests audited separately',
            'roots':ri,'seed_rows':rows,'accepted':accepted,'qualification_passed':passed,
            'decision':'NO-GO: qualification' if not passed else 'qualification passed',
            'qualification_rollouts':q['rollouts_reserved'],'qualification_equivalents':q['equivalents_reserved']}
    with Path(a.out).open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='per_root'},indent=2))


if __name__=='__main__':main()
