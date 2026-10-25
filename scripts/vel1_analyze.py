"""Fixed lightweight VEL-1 grouped risk feasibility, without simulator calls.

Weighted Newton logistic regression follows hdb_stop_calibration.fit_logistic,
adding base-equal weights and numerical safeguards in this isolated utility.
No installed sklearn/scipy or production learning system is required.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vel1_audit import FEATURES,read
from r0_experiment import write_new

SEED=2026102601
SMALL=('robust_fraction','robust_n')


def weights(groups):
    counts=Counter(groups)
    return np.array([1/counts[g] for g in groups],float)


def sigmoid(z):return 1/(1+np.exp(-np.clip(z,-35,35)))


class Logistic:
    def __init__(self,features):self.features=tuple(features)

    def raw(self,rows):return np.array([[np.nan if r['features'][f] is None else r['features'][f] for f in self.features] for r in rows],float)

    def transform(self,rows):
        raw=self.raw(rows);missing=np.isnan(raw)
        imputed=np.where(missing,self.median,raw)
        x=(imputed-self.mean)/self.scale
        return np.column_stack([np.ones(len(rows)),x,missing.astype(float)])

    def fit(self,rows):
        y=np.array([r['target']['failed'] for r in rows],float);w=weights([r['group'] for r in rows])
        raw=self.raw(rows)
        self.median=np.array([np.median(c[np.isfinite(c)]) if np.isfinite(c).any() else .5 for c in raw.T])
        x=np.where(np.isnan(raw),self.median,raw);self.mean=np.average(x,axis=0,weights=w)
        self.scale=np.sqrt(np.average((x-self.mean)**2,axis=0,weights=w));self.scale[self.scale<1e-8]=1.
        X=self.transform(rows);self.coef=np.zeros(X.shape[1]);self.constant=None
        self.converged=True
        if y.min()==y.max():
            self.constant=(float(np.dot(w,y))+.5)/(w.sum()+1);return self
        penalty=np.ones(X.shape[1]);penalty[0]=0
        def objective(c):
            z=X@c
            return float(np.dot(w,np.logaddexp(0,z)-y*z)+.5*np.dot(penalty*c,c))
        self.converged=False
        for it in range(80):
            p=sigmoid(X@self.coef)
            g=X.T@(w*(p-y))+penalty*self.coef
            H=X.T@(X*(w*p*(1-p))[:,None])+np.diag(penalty)+1e-9*np.eye(X.shape[1])
            step=np.linalg.solve(H,g);scale=1.;old=objective(self.coef)
            while scale>1e-6 and objective(self.coef-scale*step)>old+1e-12:scale*=.5
            self.coef-=scale*step
            if np.max(np.abs(scale*step))<1e-8:self.converged=True;break
        if not self.converged:raise ValueError('logistic numerical convergence failed')
        return self

    def predict(self,rows):
        return np.full(len(rows),self.constant) if self.constant is not None else sigmoid(self.transform(rows)@self.coef)


def constant(rows):
    w=weights([r['group'] for r in rows]);y=np.array([r['target']['failed'] for r in rows],float)
    return float((np.dot(w,y)+.5)/(w.sum()+1))


def beta_failure(k,n):
    # Exact version of the existing Beta(1+k,1+n-k) walking-tail heuristic.
    return 1-sum(math.comb(n+1,j)*.8**j*.2**(n+1-j) for j in range(k+1))


def metrics(rows,p):
    p=np.asarray(p,float);valid=np.isfinite(p)
    rows=[r for r,v in zip(rows,valid) if v];p=p[valid]
    if not rows:return {'n':0,'groups':0}
    y=np.array([r['target']['failed'] for r in rows],float);w=weights([r['group'] for r in rows]);w/=w.sum()
    p=np.clip(p,1e-6,1-1e-6);bins=np.minimum((p*5).astype(int),4);cal=[]
    for b in range(5):
        take=bins==b
        if take.any():cal.append({'bin':b,'n':int(take.sum()),'weight':float(w[take].sum()),
                                  'predicted':float(np.average(p[take],weights=w[take])),
                                  'observed':float(np.average(y[take],weights=w[take]))})
    pos=y==1;neg=~pos;auroc=None
    if pos.any() and neg.any():
        pair=(p[pos,None]>p[None,neg])+.5*(p[pos,None]==p[None,neg])
        auroc=float(np.sum(pair*w[pos,None]*w[None,neg])/(w[pos].sum()*w[neg].sum()))
    alarm=p>=.5;tp=float(w[alarm&pos].sum());fp=float(w[alarm&neg].sum())
    selective=[]
    for threshold in (.1,.25,.5):
        keep=p<threshold;cov=float(w[keep].sum())
        selective.append({'risk_threshold':threshold,'coverage':cov,
                          'remaining_failure_risk':float(np.dot(w[keep],y[keep])/cov) if cov else None,
                          'successful_repair_fraction_rejected':float(w[~keep&neg].sum()/w[neg].sum()) if neg.any() else None})
    rank=[];order=sorted(range(len(rows)),key=lambda i:(p[i],rows[i]['id']))
    for target in (.5,.8,.9,1.):
        mass=fail=0.
        for i in order:
            use=min(float(w[i]),max(0,target-mass));mass+=use;fail+=use*y[i]
            if mass>=target-1e-12:break
        rank.append({'coverage':target,'failure_risk':fail/mass})
    return {'n':len(rows),'groups':len({r['group'] for r in rows}),'failure_rate':float(np.dot(w,y)),
            'brier':float(np.dot(w,(p-y)**2)),
            'log_loss':float(-np.dot(w,y*np.log(p)+(1-y)*np.log1p(-p))),
            'ece5':sum(b['weight']*abs(b['predicted']-b['observed']) for b in cal),'calibration':cal,
            'auroc':auroc,'warning_precision_at_0_5':tp/(tp+fp) if tp+fp else None,
            'warning_recall_at_0_5':tp/float(w[pos].sum()) if pos.any() else None,
            'false_alarm_rate_at_0_5':fp/float(w[neg].sum()) if neg.any() else None,
            'risk_threshold_coverage':selective,'descriptive_rank_coverage':rank}


def paired(rows,loss_a,loss_b):
    """Positive gain means model B has lower Brier than model A."""
    buckets={}
    for r,a,b in zip(rows,loss_a,loss_b):
        if math.isfinite(a) and math.isfinite(b):buckets.setdefault(r['group'],[]).append(float(a-b))
    v=np.array([np.mean(x) for _,x in sorted(buckets.items())])
    if not len(v):return {'groups':0,'gain':None,'descriptive95':None}
    rng=np.random.default_rng(SEED);boot=rng.choice(v,size=(5000,len(v)),replace=True).mean(axis=1)
    return {'groups':len(v),'gain':float(v.mean()),'descriptive95':[float(x) for x in np.quantile(boot,[.025,.975])],
            'bases_worse':int((v<0).sum()),'bases_better':int((v>0).sum()),'per_group':dict(zip(sorted(buckets),v.tolist()))}


class Grouped:
    def __init__(self,rows):self.rows=rows;self.cache={};self.proofs=[]

    def fit_predict(self,train,test,feats):
        if not train:raise ValueError('empty grouped training set')
        if set(r['group'] for r in train)&set(r['group'] for r in test):raise ValueError('physical base leakage')
        return Logistic(feats).fit(train).predict(test)

    def inner_residuals(self,train):
        residual=[]
        for row in train:
            key=(tuple(sorted(r['id'] for r in train)),row['group'])
            if key not in self.cache:
                te=[r for r in train if r['group']==row['group']];tr=[r for r in train if r['group']!=row['group']]
                pred=self.fit_predict(tr,te,FEATURES)
                self.cache[key]={r['id']:r['target']['failed']-float(p) for r,p in zip(te,pred)}
            residual.append(self.cache[key][row['id']])
        return np.array(residual)

    def predict_fold(self,train,test,experience=False):
        if set(r['group'] for r in train)&set(r['group'] for r in test):raise ValueError('outer base leakage')
        p=Logistic(FEATURES).fit(train);full=p.predict(test)
        result={'constant':np.full(len(test),constant(train)),
                'V1a_robust_calibration':self.fit_predict(train,test,SMALL),'V1_physical':full}
        self.proofs.append({'test_ids':[r['id'] for r in test],'test_groups':sorted({r['group'] for r in test}),
                            'training_groups':sorted({r['group'] for r in train}),
                            'training_families':sorted({r['family_evaluator_only'] for r in train})})
        if not experience:return result
        resid=self.inner_residuals(train);bank=p.transform(train)[:,1:];queries=p.transform(test)[:,1:]
        groups=sorted({r['group'] for r in train});ix={g:[i for i,r in enumerate(train) if r['group']==g] for g in groups}
        v2=[];v3=[]
        permutations=[np.random.default_rng(SEED+s).permutation(len(groups)) for s in range(20)]
        for q,base in zip(queries,full):
            dist=np.mean((bank-q)**2,axis=1)
            reps=[min(ix[g],key=lambda i:(dist[i],train[i]['id'])) for g in groups]
            nearest=sorted(range(len(groups)),key=lambda i:(dist[reps[i]],groups[i]))[:5]
            rr=resid[reps];shrink=len(nearest)/(len(nearest)+5)
            v2.append(float(np.clip(base+shrink*np.mean(rr[nearest]),1e-6,1-1e-6)))
            v3.append([float(np.clip(base+shrink*np.mean(rr[perm[nearest]]),1e-6,1-1e-6)) for perm in permutations])
        result['V2_experience']=np.array(v2);result['V3_shuffled']=np.array(v3)
        return result

    def crossfit(self,dual=False,experience=False):
        arrays={k:np.zeros(len(self.rows)) for k in ('constant','V1a_robust_calibration','V1_physical')}
        if experience:arrays.update(V2_experience=np.zeros(len(self.rows)),V3_shuffled=np.zeros((len(self.rows),20)))
        buckets={}
        for i,r in enumerate(self.rows):buckets.setdefault((r['group'],r['family_evaluator_only'] if dual else None),[]).append(i)
        for (group,family),indices in sorted(buckets.items()):
            train=[r for r in self.rows if r['group']!=group and (family is None or r['family_evaluator_only']!=family)]
            test=[self.rows[i] for i in indices];pred=self.predict_fold(train,test,experience)
            if dual and any(r['family_evaluator_only']==family for r in train):raise ValueError('family leakage')
            for k,v in pred.items():arrays[k][indices]=v
        arrays['V0_walking']=np.array([1-r['features']['robust_fraction'] for r in self.rows])
        arrays['V0_beta']=np.array([beta_failure(round(r['features']['robust_fraction']*r['features']['robust_n']),int(r['features']['robust_n'])) for r in self.rows])
        arrays['V0_map_confidence']=np.array([1-r['features']['map_mass'] for r in self.rows])
        arrays['V0_legacy_stopmap']=np.array([np.nan if r['legacy_map_failure_probability'] is None else r['legacy_map_failure_probability'] for r in self.rows])
        return arrays


def evaluate(rows,arrays,subset):
    ix=[i for i,r in enumerate(rows) if subset=='all' or r['apparent']];rs=[rows[i] for i in ix]
    y=np.array([r['target']['failed'] for r in rs]);out={};loss={};shuffle=None
    for k,raw in arrays.items():
        p=raw[ix]
        if p.ndim==2:
            shuffle=(p-y[:,None])**2
            out[k]={'mean_prediction_metrics':metrics(rs,p.mean(axis=1)),
                    'individual_shuffle_brier':[metrics(rs,p[:,j])['brier'] for j in range(p.shape[1])],
                    'control_note':'Primary shuffled comparison uses mean loss over20 base-pairing permutations, not ensemble loss.'}
            loss[k]=shuffle.mean(axis=1)
        else:out[k]=metrics(rs,p);loss[k]=(p-y)**2
    contrasts={}
    for ref,new in [('constant','V1_physical'),('V0_walking','V1_physical'),('V1a_robust_calibration','V1_physical'),
                    ('V0_legacy_stopmap','V1_physical'),('V1_physical','V2_experience'),('V3_shuffled','V2_experience')]:
        if ref in loss and new in loss:contrasts[f'{new}_vs_{ref}']=paired(rs,loss[ref],loss[new])
    out['paired_brier_improvement']=contrasts
    return out


def run(a):
    rows=[r for r in read(a.rows) if r['target']['failed'] is not None]
    if any(set(r['features'])!=set(FEATURES) for r in rows):raise ValueError('unregistered features')
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('duplicate row IDs')
    grouped=Grouped(rows);lobo=grouped.crossfit(experience=a.experience)
    result={'stage':'historical feasibility, not prospective validation','plan_commit':'63df2c1',
            'environment':{'python':platform.python_version(),'numpy':np.__version__,'executable':sys.executable},
            'independent_groups':len({r['group'] for r in rows}),'rows':len(rows),
            'experience_analyzed':a.experience,'data_sha256':hashlib.sha256(Path(a.rows).read_bytes()).hexdigest(),
            'lobo':{sub:evaluate(rows,lobo,sub) for sub in ('all','apparent')}}
    if a.family:
        dual=grouped.crossfit(dual=True,experience=a.experience)
        result['dual_base_family_out']={sub:evaluate(rows,dual,sub) for sub in ('all','apparent')}
        result['per_family']={f:evaluate([r for r in rows if r['family_evaluator_only']==f],
             {k:v[[i for i,r in enumerate(rows) if r['family_evaluator_only']==f]] for k,v in dual.items()},'apparent')
             for f in sorted({r['family_evaluator_only'] for r in rows})}
    predictions=[]
    for i,r in enumerate(rows):
        pred={k:(v[i].tolist() if np.ndim(v[i]) else None if not math.isfinite(v[i]) else float(v[i])) for k,v in lobo.items()}
        if a.family:pred['dual_base_family_out']={k:(v[i].tolist() if np.ndim(v[i]) else None if not math.isfinite(v[i]) else float(v[i])) for k,v in dual.items()}
        predictions.append({'id':r['id'],'group':r['group'],'apparent':r['apparent'],'failed':r['target']['failed'],'predictions':pred})
    out=Path(a.out);write_new(out/'analysis.json',result);write_new(out/'predictions.json',predictions)
    write_new(out/'fold_proofs.json',grouped.proofs)
    print(json.dumps({'rows':len(rows),'groups':result['independent_groups'],'experience':a.experience,
                     'lobo_apparent_brier':{k:v.get('brier',v.get('individual_shuffle_brier')) for k,v in result['lobo']['apparent'].items() if k!='paired_brier_improvement'},
                     'paired':result['lobo']['apparent']['paired_brier_improvement']},indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--rows',required=True);p.add_argument('--out',required=True)
    p.add_argument('--experience',action='store_true');p.add_argument('--family',action='store_true');run(p.parse_args())


if __name__=='__main__':main()
