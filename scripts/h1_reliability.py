"""Conditional H1 Stage B: complete-cohort matched disjoint repeat panels.

No learner, feature search, optimizer, model calls, or policy changes.
"""
import argparse
import collections
from pathlib import Path
import random
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import h1_counterfactual as h

STUDY=h.STUDY/'stage_b'


def prepare(stage_a,out):
    stage_a=Path(stage_a);out=Path(out)
    a=h.read(stage_a/'analysis.json');audit=h.read(stage_a/'independent_audit.json')
    if a['stage_a_signal']!='ADVANCE_TO_B' or not audit['gate'] or not audit['independent_gate_matches']:
        raise ValueError('Stage A audited advancement prerequisite failed')
    p,cc,_,_=h.load(h.STUDY)
    used={s for c in cc.values() for ss in c['seeds'].values() for s in ss}
    for c in h.read(h.ROOT/'experiments/causal_engineer/dev/repair_strategy_r0/cases.json'):
        used.update(s for ss in c['seeds'].values() for s in ss)
    for c in h.read(h.ROOT/'experiments/causal_engineer/dev/vel2/stage_a_cases.json'):
        for panel in c['panels']:
            used.update(s for ss in panel.values() for s in ss)
    panels={};old=len(used)
    for base in sorted({c['base_id'] for c in cc.values()}):
        panels[base]=[]
        for j in range(2):
            panel={}
            for role in ('validate','confirm'):
                ss=[int(h.sha(f'h1-reliability-20261026-v1:{base}:{j}:{role}:{i}'.encode())[:8],16) for i in range(24)]
                if len(set(ss))!=24 or set(ss)&used:raise ValueError('new panel seed collision')
                used.update(ss);panel[role]=ss
            panels[base].append(panel)
    jobs=[]
    for k,c in sorted(cc.items()):
        for j,seeds in enumerate(panels[c['base_id']]):
            jobs.append({'key':h.sha(h.canonical([k,j,seeds])),'candidate_key':k,'panel':j+1,'seeds':seeds})
    h.write_new(out/'jobs.json',jobs)
    h.write_new(out/'protocol.json',{'version':'h1-stage-b-v1','n_candidates':640,'n_jobs':1280,'n_bases':18,
      'new_unique_seeds':len(used)-old,'jobs_sha256':h.sha((out/'jobs.json').read_bytes()),
      'stage_a_analysis_sha256':h.sha((stage_a/'analysis.json').read_bytes()),
      'stage_a_audit_sha256':h.sha((stage_a/'independent_audit.json').read_bytes()),
      'stage_a_outcome_sha256':{k:h.sha((stage_a/'outcomes'/f'{k}.json').read_bytes()) for k in p['missing_keys']},
      'max_equivalents':122880,'no_outcome_conditioned_sampling':True,
      'prediction_rules':['incumbent','walking_keep_incumbent_ties','fitness_keep_incumbent_ties','survival_walking_fitness','first_training_rank','walking_first_training_tie'],
      'gate':{'persistent_missed_bases':3,'fresh_panel_oracle_gain':.05,
        'physical_rule_net_gain':.05,'positive_whole_base_lower95':True},
      'power_assumptions':{'alpha_two_sided':.05,'power':.8,'useful_full_gain':.10,'discordance_sensitivity':[.2,.4]},
      'interpretation':'Preliminary reliability on18 known bases; three panels are not precise per-candidate probabilities.'})
    return {'jobs':len(jobs),'new_unique_seeds':len(used)-old}


def load(study):
    p=h.read(Path(study)/'protocol.json');raw=(Path(study)/'jobs.json').read_bytes()
    if h.sha(raw)!=p['jobs_sha256']:raise ValueError('frozen Stage B jobs changed')
    return p,h.read(Path(study)/'jobs.json')


def source_check(study):
    h.validate_sources(h.STUDY)
    for n,digest in h.read(Path(study)/'source_hashes.json').items():
        if h.sha((h.ROOT/n).read_bytes().replace(b'\r\n',b'\n'))!=digest:raise ValueError('Stage B source changed')


def run(study,out,shard):
    source_check(study)
    from creature_forge.hidden_plant import verify
    from creature_forge.forge_pool import ForgePool
    _,jobs=load(study);_,cc,_,_=h.load(h.STUDY);i,n=map(int,shard.split('/'))
    if n!=8 or not 0<=i<8:raise ValueError('requires fixed eight shards')
    out=Path(out)
    h.write_new(out/f'execution_{i}.json',{'epoch':time.time(),'shard':shard,'python':sys.version})
    with ForgePool(max_workers=6) as pool:
        for job in jobs[i::n]:
            c=cc[job['candidate_key']];dest=out/'outcomes'/f"{job['key']}.json"
            if dest.exists():raise ValueError('no selective rerun')
            t=time.perf_counter();ss=job['seeds']
            v=verify(c['plant'],c['original'],c['candidate'],ss['validate'],ss['confirm'],pool=pool)
            h.write_new(dest,{**job,'candidate_sha256':c['candidate_sha256'],'verification':v,'wall_s':time.perf_counter()-t})
            if h.components(v) is None:raise ValueError('error preserved; stop')


def interval(values):
    rng=random.Random(2026102612)
    boot=sorted(sum(rng.choices(values,k=len(values)))/len(values) for _ in range(10000))
    return [boot[249],boot[9749]]


def analyze(study,stage_a,out):
    p,jobs=load(study);_,cc,pairs,known=h.load(h.STUDY);out=Path(out);stage_a=Path(stage_a)
    if h.sha((stage_a/'analysis.json').read_bytes())!=p['stage_a_analysis_sha256'] or h.sha((stage_a/'independent_audit.json').read_bytes())!=p['stage_a_audit_sha256']:
        raise ValueError('Stage A audited prerequisite changed')
    vv={k:[None,None,None] for k in cc};eq=rows=0
    # Original complete panel:320 previous selected labels plus320 Stage A arrays.
    for k,v in known.items():vv[k][0]=v
    for k in h.read(h.STUDY/'protocol.json')['missing_keys']:
        if h.sha((stage_a/'outcomes'/f'{k}.json').read_bytes())!=p['stage_a_outcome_sha256'][k]:
            raise ValueError('audited Stage A outcome bytes changed')
        original=h.read(stage_a/'outcomes'/f'{k}.json');v=original['verification']
        if original['key']!=k or original['candidate_sha256']!=cc[k]['candidate_sha256'] or v['seeds']!=cc[k]['seeds']:
            raise ValueError('original Stage A candidate identity changed')
        vv[k][0]={'status':v['status'],'components':h.components(v)}
    requirement=collections.defaultdict(lambda:collections.Counter());rawstatus=collections.Counter()
    for job in jobs:
        r=h.read(out/'outcomes'/f"{job['key']}.json");v=r['verification'];k=job['candidate_key']
        if any(r[x]!=job[x] for x in job) or v['seeds']!=job['seeds'] or v['variation']!=cc[k]['variation'] or r['candidate_sha256']!=cc[k]['candidate_sha256'] or v['rule']!='full_recovery_v1':
            raise ValueError('new panel identity mismatch')
        comp=h.components(v)
        if comp is None:raise ValueError('incomplete/error cohort; not evaluable')
        vv[k][job['panel']]={'status':v['status'],'components':comp};rawstatus[v['status']]+=1
        eq+=v['rollouts']['validation']+v['rollouts']['confirmation_rollout_equivalents']
        rows+=48+len(v['confirmation'].get('per_seed',[]))
        for name,value in comp.items():requirement[name]['missing' if value is None else ('pass' if value else 'fail')]+=1
    stable=sum(len({v['status']==h.FULL for v in vals})==1 for vals in vv.values())
    stability_by_base=collections.defaultdict(list);agreement=collections.defaultdict(lambda:collections.defaultdict(list))
    for k,vals in vv.items():
        base=cc[k]['base_id'];stability_by_base[base].append(int(len({v['status']==h.FULL for v in vals})==1))
        for name in vals[0]['components']:
            for i,j in ((0,1),(0,2),(1,2)):
                a,z=vals[i]['components'][name],vals[j]['components'][name]
                if a is not None and z is not None:agreement[name][base].append(int(a==z))
    pairrows=[];by=collections.defaultdict(list);effects=collections.defaultdict(lambda:collections.defaultdict(list))
    reqeffects=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.Counter()))
    reqranks=collections.defaultdict(lambda:collections.Counter())
    for pair in pairs:
        x,y=pair['keys'];sel=pair['selected'];values=[[int(v['status']==h.FULL) for v in vv[k]] for k in (x,y)]
        gains=[values[1-sel][j]-values[sel][j] for j in range(3)]
        persistent=all(g>0 for g in gains)
        by[pair['base_id']].append(sum(max(0,g) for g in gains[1:])/2)
        scores=pair['preverification']
        choices={'incumbent':sel,'walking_keep_incumbent_ties':max((sel,1-sel),key=lambda i:scores[i]['walking_count']),
          'fitness_keep_incumbent_ties':max((sel,1-sel),key=lambda i:scores[i]['mean_fitness']),
          'survival_walking_fitness':max((sel,1-sel),key=lambda i:(scores[i]['survival_count'],scores[i]['walking_count'],scores[i]['mean_fitness'])),
          'first_training_rank':0,'walking_first_training_tie':max(range(2),key=lambda i:(scores[i]['walking_count'],-i))}
        for name in vv[x][0]['components']:
            diffs=[]
            for panel in range(3):
                a,z=vv[x][panel]['components'][name],vv[y][panel]['components'][name]
                if a is not None and z is not None:diffs.append(int(z)-int(a))
            reqranks[name]['complete_three_panel_pairs']+=len(diffs)==3
            reqranks[name]['at_least_two_observed_panels']+=len(diffs)>=2
            reqranks[name]['strict_reversals']+=bool(diffs and min(diffs)<0<max(diffs))
            reqranks[name]['tie_panels']+=diffs.count(0)
        for name,choice in choices.items():
            effects[name][pair['base_id']].append(sum(values[choice][j]-values[sel][j] for j in (1,2))/2)
            for requirement_name in vv[x][1]['components']:
                for panel in (1,2):
                    a=vv[pair['keys'][choice]][panel]['components'][requirement_name]
                    b=vv[pair['keys'][sel]][panel]['components'][requirement_name]
                    stats=reqeffects[name][requirement_name]
                    if a is None or b is None:stats['unobserved_pair']+=1
                    else:
                        stats['observed_pair']+=1;stats['wins']+=a>b;stats['losses']+=a<b
        pairrows.append({'unit_id':pair['unit_id'],'base_id':pair['base_id'],'difference_alternative_minus_incumbent':gains,
          'strict_rank_reversal':min(gains)<0<max(gains),'persistent_miss':persistent,'choices':choices})
    controls={}
    for name,data in effects.items():
        means=[sum(v)/len(v) for v in data.values()];ci=interval(means)
        controls[name]={'fresh_panel_base_equal_net_full_gain':sum(means)/len(means),'descriptive_whole_base95':ci,
                        'bases_improved':sum(v>0 for v in means),'bases_harmed':sum(v<0 for v in means)}
    missed=len({r['base_id'] for r in pairrows if r['persistent_miss']})
    oracle=sum(sum(v)/len(v) for v in by.values())/len(by)
    physical=any(r['fresh_panel_base_equal_net_full_gain']>=.05 and r['descriptive_whole_base95'][0]>0 for r in controls.values())
    checks={'complete_error_free':True,'persistent_missed_bases':missed>=3,'fresh_panel_oracle_gain':oracle>=.05,'legal_physical_decision_signal':physical}
    stable_means=[sum(v)/len(v) for v in stability_by_base.values()]
    reqagreement={}
    for name,data in agreement.items():
        means=[sum(v)/len(v) for v in data.values() if v]
        reqagreement[name]={'observed_candidate_panel_pairs':sum(len(v) for v in data.values()),'bases_with_observations':len(means),
          'base_equal_agreement':sum(means)/len(means) if means else None,'descriptive_whole_base95':interval(means) if means else None}
    return {'stage_b_signal':'SUPPORTS_FEASIBILITY_REVIEW' if all(checks.values()) else 'NOT EVALUABLE',
      'gate_checks':checks,'n_known_bases':18,'new_lineages':0,'n_candidates':640,'new_assessments':1280,
      'new_equivalents':eq,'new_response_rows':rows,'new_status_counts':dict(rawstatus),
      'requirement_observed_missing':{k:dict(v) for k,v in requirement.items()},
      'three_panel_full_stable_candidates':stable,'strict_pair_rank_reversals':sum(r['strict_rank_reversal'] for r in pairrows),
      'full_stability_base_equal':sum(stable_means)/len(stable_means),'full_stability_whole_base95':interval(stable_means),
      'requirement_repeatability':reqagreement,'requirement_pair_rank_reversals':{k:dict(v) for k,v in reqranks.items()},
      'persistent_missed_bases':missed,'fresh_panel_base_equal_oracle_headroom':oracle,
      'fixed_physical_rules':controls,'pairs':pairrows,
      'requirement_rule_comparisons_conditional':{n:{k:dict(v) for k,v in reqs.items()} for n,reqs in reqeffects.items()},
      'limitations':'Known enriched18 bases; correlated candidates/panels; oracle not policy; no history/Nemotron test; unexecuted confirmation remains missing.'}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('cmd',choices=('prepare','run','analyze'));ap.add_argument('--study',default=str(STUDY));ap.add_argument('--stage-a',required=True);ap.add_argument('--out',default='artifacts/h1_stage_b_v1');ap.add_argument('--shard',default='0/8');ap.add_argument('--analysis-output');a=ap.parse_args()
    if a.cmd=='prepare':r=prepare(a.stage_a,a.study)
    elif a.cmd=='run':run(a.study,a.out,a.shard);sys.exit(0)
    else:
        r=analyze(a.study,a.stage_a,a.out)
        if a.analysis_output:h.write_new(a.analysis_output,r)
    print({k:v for k,v in r.items() if k!='pairs'})
