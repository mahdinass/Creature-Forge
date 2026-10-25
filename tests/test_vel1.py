"""Synthetic guard fixtures only; no simulator or physical evidence generation."""
import copy
import json
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path('scripts').resolve()))
from vel1_audit import FEATURES,label,pre_features,dedup
from vel1_analyze import Grouped,metrics,paired,beta_failure


def fixture():
    return {'designs':[{'index':0,'body':{'height':1.},'vector':[0.]},
                       {'index':1,'body':{'height':1.},'vector':[.1]}],
            'repair':{'design':1,'accepted':True,'log':[{'design':1,'check16':15,'train_walking':4,
                                                      'evidence':{'stress4':3,'p_full':.8}}]},
            'engine':{'version':'belief_engine_v5','particles':[{'loglik':0.},{'loglik':-1.}],
                      'ledger':{'used':100,'remaining':600,'lines':[{'item':'robustness_check','detail':{'design':1,'n':16}}]},
                      'experiments':[{'kind':'observe','features':{'1':{'walking':0.,'slip_fraction':.1}}}]},
            'verification':{'status':'FULL_RECOVERY'}}


def rows():
    out=[]
    for b in range(4):
        for i in range(3):
            f={k:float((i+b)%3)/3 for k in FEATURES};f.update(robust_fraction=(14+i)/16,robust_n=16)
            out.append({'id':f'{b}:{i}','group':str(b),'family_evaluator_only':str(i%2),
                        'features':f,'target':{'failed':(b+i)%2},'apparent':i>=1,
                        'legacy_map_failure_probability':None})
    return out


class VEL1Tests(unittest.TestCase):
    def test_verifier_and_hidden_labels_cannot_enter_features(self):
        r=fixture();original=copy.deepcopy(r);a=pre_features(r)
        r['verification']={'status':'NOT_RECOVERED','validation':{'walking_frac':0.},'confirmation':{'secret':99}}
        r.update(family='hidden',severity=100,posterior_mass_on_injected=1.)
        self.assertEqual(pre_features(r),a);self.assertEqual(set(a[0]),set(FEATURES))
        self.assertEqual(original['repair'],r['repair'])

    def test_unpaid_or_outcome_updated_observations_rejected(self):
        r=fixture();r['engine']['ledger']['lines']=[]
        with self.assertRaises(ValueError):pre_features(r)
        r=fixture();r['engine']['experiments'].append({'kind':'check'})
        with self.assertRaises(ValueError):pre_features(r)

    def test_not_run_confirmation_is_missing(self):
        r=label({'status':'NOT_RECOVERED','walking_frac':1.,'rollouts':{'confirmation':0},
                 'reasons':['verdict_v1 is NOT_VERIFIED, not VERIFIED_IMPROVEMENT']})
        self.assertTrue(r['components']['validation_improvement_failed'])
        self.assertIsNone(r['components']['confirmation_walking_failed'])
        self.assertFalse(r['components']['validation_walking_failed'])

    def test_failure_requirements_are_separate(self):
        r=label({'status':'PARTIAL_IMPROVEMENT','walking_frac':1.,'rollouts':{'confirmation':24},
                 'reasons':['confirmation: walking on 75% of seeds at 20 s, needs >= 80%']})
        self.assertFalse(r['components']['validation_improvement_failed'])
        self.assertTrue(r['components']['confirmation_walking_failed'])
        self.assertFalse(r['components']['confirmation_speed_failed'])

    def test_errors_are_not_failed_repairs(self):
        self.assertIsNone(label({'status':'INCONCLUSIVE_ERROR'})['failed'])

    def test_conflicting_duplicate_label_rejected(self):
        a={'instance_id':'a','candidate_sha256':'d','id':'a','target':{'failed':1}}
        b=copy.deepcopy(a);b['id']='b'
        self.assertEqual(len(dedup([a,b])[0]),1)
        b['target']['failed']=0
        with self.assertRaises(ValueError):dedup([a,b])

    def test_heldout_base_labels_never_affect_any_model_or_memory(self):
        r=rows();tr=[x for x in r if x['group']!='0'];te=[x for x in r if x['group']=='0']
        a=Grouped(r).predict_fold(tr,te,True)
        changed=copy.deepcopy(r)
        for x in changed:
            if x['group']=='0':x['target']['failed']=1-x['target']['failed']
        b=Grouped(changed).predict_fold([x for x in changed if x['group']!='0'],
                                     [x for x in changed if x['group']=='0'],True)
        for k in a:np.testing.assert_array_equal(a[k],b[k])

    def test_outer_physical_alias_guard(self):
        r=rows()
        with self.assertRaises(ValueError):Grouped(r).predict_fold(r[:3],r[1:3])

    def test_dual_family_and_base_blocks(self):
        r=rows();g=Grouped(r);g.crossfit(dual=True)
        byid={x['id']:x for x in r}
        for proof in g.proofs:
            self.assertFalse(set(proof['test_groups'])&set(proof['training_groups']))
            fams={byid[i]['family_evaluator_only'] for i in proof['test_ids']}
            self.assertFalse(fams&set(proof['training_families']))

    def test_base_equal_brier_not_episode_weighted(self):
        r=[{'group':'a','id':'1','target':{'failed':1}},
           {'group':'a','id':'2','target':{'failed':1}},
           {'group':'b','id':'3','target':{'failed':0}}]
        self.assertAlmostEqual(metrics(r,[0.,0.,0.])['brier'],.5,places=5)
        self.assertAlmostEqual(metrics(r,[.8,.8,.2])['auroc'],1.)

    def test_cluster_repeats_do_not_increase_independent_n(self):
        r=rows();a=[.4]*len(r);b=[.2]*len(r)
        one=paired(r,a,b);many=paired(r*10,a*10,b*10)
        self.assertEqual(one['groups'],many['groups']);self.assertAlmostEqual(one['gain'],many['gain'])

    def test_beta_tail_extremes(self):
        self.assertAlmostEqual(beta_failure(0,1),.96)
        self.assertAlmostEqual(beta_failure(16,16),.8**17)


if __name__=='__main__':unittest.main()
