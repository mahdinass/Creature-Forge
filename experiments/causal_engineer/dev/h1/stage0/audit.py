"""Read-only H1 Stage 0 descriptive audit. Standard library only; no physics/model imports."""
from pathlib import Path
import collections as C
import hashlib
import json
import math
import random
import statistics as st
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE_DIR=Path(__file__).resolve().parent
OUT=SOURCE_DIR
if '--out' in sys.argv:
    OUT=(ROOT/Path(sys.argv[sys.argv.index('--out')+1])).resolve()
    assert OUT.is_relative_to(ROOT/'artifacts')
    OUT.mkdir(exist_ok=False)
PIN='e8d5fa6730ecf6d2db67021a9d3d0f08cce03310'
FULL='FULL_RECOVERY'
TOOLS=('posture','timing','feedback','stride','placement','foot_length','torso_mass','torque_limit','foot_friction','leg_length')
SOURCES={}

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def register(p,expected=None):
    p=Path(p);b=p.read_bytes();h=sha(b)
    if expected:assert h==expected,str(p)
    SOURCES[str(p.resolve())]={'sha256':h,'bytes':len(b)}
    return b
def read(p):return json.loads(register(p))
def phys(d):return sha(canon({k:d[k] for k in ('body','vector')}))
def write(p,x):
    with (OUT/p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')

def summary(vals):
    vals=list(vals)
    return {'n':len(vals),'min':min(vals),'median':st.median(vals),'max':max(vals),'sum':sum(vals)}

def base_stats(rows,value):
    by=C.defaultdict(list)
    for r in rows:by[r['base']].append(value(r))
    return {b:sum(v)/len(v) for b,v in by.items()}

def contrast(rows,left,right):
    by=base_stats(rows,lambda r:r[left]-r[right]);vals=list(by.values());rng=random.Random(2026102607)
    boot=sorted(sum(rng.choice(vals) for _ in vals)/len(vals) for _ in range(5000))
    return {'instance_mean':sum(r[left]-r[right] for r in rows)/len(rows),
      'base_equal_mean':sum(vals)/len(vals),'base_bootstrap95_descriptive':[boot[125],boot[4874]],
      'wins':sum(r[left]>r[right] for r in rows),'losses':sum(r[left]<r[right] for r in rows),
      'bases_with_wins':len({r['base'] for r in rows if r[left]>r[right]}),
      'bases_with_losses':len({r['base'] for r in rows if r[left]<r[right]}),'base_effects':by}

def engine_order(rec):
    ev=rec['engine']['events']
    s=next((e for e in ev if e['kind']=='tool_screen'),None)
    c=next((e for e in ev if e['kind']=='tool_screen_cma'),None)
    order=[r['tool'] for r in (c or s or {'ranking':[]})['ranking']]
    if c and s:order += [r['tool'] for r in s['ranking'] if r['tool'] not in order]
    return order+[t for t in TOOLS if t not in order]

def rl1(fresh):
    p=ROOT/'experiments/causal_engineer/dev/rl1/rl1_matrix.tgz'
    register(p,'9b740a946231d7bf98967d28a641de320831e346048a59da5eaff89434c96b2a')
    with tarfile.open(p) as t:
        manifest=t.extractfile('SHA256SUMS').read().decode()
        hashes={}
        for line in manifest.splitlines():
            h,n=line.split(None,1);n=n.lstrip('*').strip();assert sha(t.extractfile(n).read())==h,n;hashes[n]=h
        mat=[json.loads(l) for l in t.extractfile('matrix.jsonl')]
    cells=C.defaultdict(dict)
    for r in mat:
        assert r['ok'] and 'error' not in r and r['budget']==300 and r['plant_used']<=300
        assert r['tool'] not in cells[r['instance_id']]
        cells[r['instance_id']][r['tool']]=r
    assert len(mat)==2110 and set(cells)==set(fresh)
    rows=[];dedup=0
    for iid,cs in sorted(cells.items()):
        assert set(cs)==set(TOOLS)
        order=engine_order(fresh[iid]);walk=sorted(TOOLS,key=lambda t:(-cs[t]['train_walking'],order.index(t)))
        unique={}
        for t,r in cs.items():
            h=phys(r['design'])
            if h in unique:assert unique[h]==r['status']
            unique[h]=r['status']
        dedup+=len(cs)-len(unique)
        ys={t:int(r['status']==FULL) for t,r in cs.items()}
        wmax=max(r['train_walking'] for r in cs.values())
        rows.append({'id':iid,'base':cs[order[0]]['base_id'],'family':cs[order[0]]['family'],
          'n_unique':len(unique),'full_count_tools':sum(ys.values()),'full_count_unique':sum(s==FULL for s in unique.values()),
          'engine_top1':ys[order[0]],'engine_top2':max(ys[t] for t in order[:2]),
          'train_top1':ys[walk[0]],'train_top2':max(ys[t] for t in walk[:2]),'oracle':max(ys.values()),
          'engine_tool':order[0],'train_tool':walk[0],'train_count_max':wmax,
          'n_max_train_tie':sum(r['train_walking']==wmax for r in cs.values()),
          'train_choice_changed':order[0]!=walk[0],
          'all_same_train_count':len({r['train_walking'] for r in cs.values()})==1,
          'mixed_full':0<sum(ys.values())<len(unique),'all_full':min(ys.values())==1,
          'acquisition_plant_used':sum(r['plant_used'] for r in cs.values()),
          'engine_rank_first_full':min((order.index(t)+1 for t in TOOLS if ys[t]),default=None),
          'cells':[{k:r[k] for k in ('tool','train_walking','plant_used','status','walking_frac')}|{'design_sha256':phys(r['design'])} for r in cs.values()]})
    # mixed_full uses unique successful candidate count, avoiding duplicate-tool artifacts.
    for r in rows:r['mixed_full']=0<r['full_count_unique']<r['n_unique']
    s={'saved_cells':len(mat),'distinct_candidate_iid':len(mat)-dedup,'duplicate_aliases':dedup,
       'independent_bases':len({r['base'] for r in rows}),'fault_instances':len(rows),
       'families':len({r['family'] for r in rows}),'candidate_counts':dict(C.Counter(r['n_unique'] for r in rows)),
       'any_full':sum(r['oracle'] for r in rows),'no_full':sum(not r['oracle'] for r in rows),
       'mixed_full_nonfull':sum(r['mixed_full'] for r in rows),'all_full':sum(r['all_full'] for r in rows),
       'mixed_bases':len({r['base'] for r in rows if r['mixed_full']}),
       'no_full_bases':len({r['base'] for r in rows if not r['oracle']}),
       'verified_full_cells':sum(r['status']==FULL for r in mat),
       'training_counts':dict(C.Counter(r['train_walking'] for r in mat)),
       'physical_rows_missing_detailed_verifier':sum('verification' not in r for r in mat),
       'acquisition_plant_used':summary(r['acquisition_plant_used'] for r in rows),
       'per_cell_plant_used':summary(r['plant_used'] for r in mat),
       'rules':{key:{'full':sum(r[key] for r in rows),'n':len(rows),'base_equal':st.mean(base_stats(rows,lambda r:r[key]).values())}
                for key in ('engine_top1','engine_top2','train_top1','train_top2','oracle')},
       'train_minus_engine_top1':contrast(rows,'train_top1','engine_top1'),
       'train_minus_engine_top2':contrast(rows,'train_top2','engine_top2'),
       'headroom_vs_engine_top1':sum(r['oracle'] and not r['engine_top1'] for r in rows),
       'headroom_vs_engine_top2':sum(r['oracle'] and not r['engine_top2'] for r in rows),
       'headroom_vs_train_top1':sum(r['oracle'] and not r['train_top1'] for r in rows),
       'all_train_counts_tied':sum(r['all_same_train_count'] for r in rows),
       'top_train_ties':summary(r['n_max_train_tie'] for r in rows),
       'changed_choices':sum(r['train_choice_changed'] for r in rows),
       'archive_manifest_entries':len(hashes),
       'full_status_counts':dict(C.Counter(r['status'] for r in mat)),
       'per_family':{f:{'n':len(z:=[r for r in rows if r['family']==f]),'no_full':sum(not r['oracle'] for r in z),
         'engine_top1':sum(r['engine_top1'] for r in z),'train_top1':sum(r['train_top1'] for r in z)} for f in sorted({r['family'] for r in rows})}}
    write('rl1_decisions.json',rows)
    return s

def comp(v):
    assert not v.get('errors') and v['status']!='INCONCLUSIVE_ERROR'
    return {'improvement_failed':v['validation']['verdict']['status']!='VERIFIED_IMPROVEMENT',
      'validation_walking_failed':v['validation']['aggregate']!='PASS',
      'confirmation_run':v['confirmation']['run'],
      **{'confirmation_'+k+'_failed':not v['confirmation']['checks'][k]['passed'] if v['confirmation']['run'] else None
         for k in ('walking_frac','median_speed_upright','body_contact')}}

def r0():
    base=ROOT/'artifacts/r0_ops/r0_run_20261025'
    hashes={n:h for h,n in (line.split('  ',1) for line in register(base/'SHA256SUMS').decode().splitlines())}
    cases=read(ROOT/'experiments/causal_engineer/dev/repair_strategy_r0/cases.json');cases={c['instance_id']:c for c in cases}
    labelmap={};rows=[];generated=[];pool_ties=C.Counter()
    for path in sorted((base/'units').glob('*.json')):
        r=json.loads(register(path,hashes['units/'+path.name]));z=r['result'];v=r['verification'];case=cases[r['instance_id']]
        assert r['seeds']==case['seeds'] and z['ledger']['used']==3000 and z['ledger']['total']==3000
        assert len(z['selection'])==2 and sha(canon(z['design']))==z['selection'][z['selected']]['design_hash']
        key=(r['instance_id'],sha(canon(z['design'])),sha(canon(v['seeds'])),sha(canon(v['variation'])))
        label={'status':v['status'],'full':int(v['status']==FULL),'components':comp(v)}
        if key in labelmap:assert labelmap[key]==label
        labelmap[key]=label
        ss=z['selection'];sel=z['selected']
        for k,rule in {
          'actual':lambda:sel,
          'walking_incumbent_tie':lambda:max(range(2),key=lambda i:(ss[i]['walking_count'],i==sel)),
          'walking_first_index_tie':lambda:max(range(2),key=lambda i:(ss[i]['walking_count'],-i)),
          'survival_first':lambda:max(range(2),key=lambda i:(ss[i]['survival_count'],ss[i]['walking_count'],ss[i]['mean_fitness'],-i)),
          'fitness_only':lambda:max(range(2),key=lambda i:(ss[i]['mean_fitness'],-i))}.items():
            pool_ties['changes_'+k]+=rule()!=sel
        actual=max(range(2),key=lambda i:(ss[i]['walking_count'],ss[i]['survival_count'],ss[i]['mean_fitness'],-i))
        assert actual==sel
        generated.append(z['candidate_count'])
        rows.append({'unit':r['unit_id'],'id':r['instance_id'],'base':r['base_id'],'family':r['family'],'cohort':r['cohort'],
          'action':r['action'],'objective':r['objective'],'replicate':r['replicate'],'selected':sel,'full':int(v['status']==FULL),
          'components':comp(v),'seeds_key':key[2],'variation_key':key[3],'candidates':ss,
          'candidate_count_pre_unique':z['candidate_count'],'searches':len(z['searches'])})
    assert len(rows)==324
    known_alt=bothdistinct=bothmixed=rescue=known_altfull=0;sets_n=C.Counter();alias_entries=0;all_screen=set();known_screen=set()
    rule_rows=[]
    for r in rows:
        ss=r['candidates'];labels=[]
        for s in ss:
            k=(r['id'],s['design_hash'],r['seeds_key'],r['variation_key'])
            all_screen.add(k)
            if k in labelmap:known_screen.add(k)
            labels.append(labelmap.get(k))
        unique=len({s['design_hash'] for s in ss});sets_n[unique]+=1
        r['labels']=labels;r['n_unique']=unique
        alt=1-r['selected']
        if unique==2:
            bothdistinct+=labels[alt] is not None
            if labels[alt] is not None:
                known_alt+=1;known_altfull+=labels[alt]['full']
                bothmixed+=labels[alt]['full']!=r['full']
                rescue+=not r['full'] and labels[alt]['full']
        else:alias_entries+=1
        sidx=r['selected']
        choices={'actual':sidx,'walking_incumbent_tie':max(range(2),key=lambda i:(ss[i]['walking_count'],i==sidx)),
          'walking_first_index_tie':max(range(2),key=lambda i:(ss[i]['walking_count'],-i)),
          'survival_first':max(range(2),key=lambda i:(ss[i]['survival_count'],ss[i]['walking_count'],ss[i]['mean_fitness'],-i)),
          'fitness_only':max(range(2),key=lambda i:(ss[i]['mean_fitness'],-i))}
        rule_rows.append({'unit':r['unit'],'base':r['base'],'actual':r['full'],
          **{k:labels[i]['full'] if labels[i] else None for k,i in choices.items()}})
    rules={}
    for name in ('walking_incumbent_tie','walking_first_index_tie','survival_first','fitness_only'):
        rr=[r for r in rule_rows if r[name] is not None]
        rules[name]={'changed_choices':pool_ties['changes_'+name],'outcome_identified_n':len(rr),
           'unknown_changed_choice_n':len(rows)-len(rr),'identified_full':sum(r[name] for r in rr),
           'identified_wins':sum(r[name]>r['actual'] for r in rr),'identified_losses':sum(r[name]<r['actual'] for r in rr)}
    by=C.defaultdict(list)
    for r in rows:by[r['id']].append(r)
    union=[{'id':iid,'base':rr[0]['base'],'full_any':any(r['full'] for r in rr),'n_selected_distinct':len({ss['design_hash'] for r in rr for ss in [r['candidates'][r['selected']]]}),
      'full_units':sum(r['full'] for r in rr),'cohort':rr[0]['cohort']} for iid,rr in by.items()]
    s={'units':len(rows),'independent_bases':len({r['base'] for r in rows}),'fault_instances':len(by),
       'distinct_verified_candidate_condition':len(labelmap),'verified_full':sum(r['full'] for r in rows),
       'final_screen_unique_count_distribution':dict(sets_n),'selected_index_distribution':dict(C.Counter(r['selected'] for r in rows)),
       'generated_candidates_pre_dedup':summary(generated),'generated_searches':summary(r['searches'] for r in rows),
       'distinct_screened_candidate_condition':len(all_screen),'screened_with_exact_label':len(known_screen),
       'distinct_screened_missing_label':len(all_screen-known_screen),'both_distinct_candidates_labeled_sets':bothdistinct,
       'both_labeled_mixed_sets':bothmixed,'chosen_nonfull_known_full_alternative':rescue,
       'unchosen_known_full':known_altfull,'n_distinct_choice_sets':len({(r['id'],tuple(sorted(s['design_hash'] for s in r['candidates']))) for r in rows}),
       'same_screen_candidate_padded_sets':alias_entries,'simple_rules':rules,
       'nonfull_requirement_failures':{k:sum(r['components'][k] is True for r in rows) for k in rows[0]['components'] if k!='confirmation_run'},
       'confirmation_not_run':sum(not r['components']['confirmation_run'] for r in rows),
       'hypothetical_18_unit_union':{'n':len(union),'any_full':sum(r['full_any'] for r in union),'no_full':sum(not r['full_any'] for r in union),
                                   'policy_cost_per_case':54000,'cases':union},
       'per_condition':{ac+'/'+ob:{'n':len(rr:=[r for r in rows if r['action']==ac and r['objective']==ob]),
          'full':sum(r['full'] for r in rr),'rule_fitness_changed':sum(max(range(2),key=lambda i:(r['candidates'][i]['mean_fitness'],-i))!=r['selected'] for r in rr)}
          for ac in ('single','sequential','joint') for ob in ('frozen','do1')}}
    write('r0_screens.json',rows);write('r0_rule_rows.json',rule_rows)
    return s


def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()==PIN
    register(Path(__file__))
    fresh={}
    b=register(ROOT/'artifacts/r0_inputs/fresh_A1c5.jsonl','3bde2b77676fd3d46592bb9ad50250ecfc8614376d6676b87d59f2a97d2149cb')
    for line in b.splitlines():
        r=json.loads(line)
        if r.get('verification'):fresh[r['instance_id']]=r
    assert len(fresh)==211
    result={'pin':PIN,'definitions_sha256':sha(register(SOURCE_DIR/'AUDIT_DEFINITIONS.md')),
      'rl1':rl1(fresh),'r0':r0(),'sources':SOURCES,
      'notes':['Exploratory fixed rules; no new fitted model, no physics.','RL1 aggregate rule values concern standardized all-tool acquisition, not actual A1 selector.',
               'R0 arm union is an expensive retrospective oracle, never a legal original choice set.']}
    write('results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources',)},indent=2))

if __name__=='__main__':main()
