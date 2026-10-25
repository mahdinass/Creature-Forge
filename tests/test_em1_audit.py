"""Identity/chronology guards on synthetic records, never physics evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import em1_audit as em


def fixture():
    return {'instance_id':'base:clock_fault:1','family':'clock_fault','provenance':'NO_AI','map_mass':1.,
            'designs':[{'index':i,'body':{'torso_mass':1.+i},'vector':[0.]} for i in (0,1)],
            'repair':{'design':1,'log':[{'design':1,'check':7}]},
            'verification':{'status':'PARTIAL_IMPROVEMENT'},
            'engine':{'version':'belief_engine_v5',
                      'history':[{'label':'after_observation','top':[{'pid':'p','w':1.}]}],
                      'particles':[{'pid':'p','deviation':[],'loglik':0.}],
                      'experiments':[{'kind':'observe','features':{'1':{'walking':0.}}}],
                      'ledger':{'lines':[{'item':'robustness_check','detail':{'design':1,'n':8}}]}}}


class Audit(unittest.TestCase):
    def run_record(self,r,other=None):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'artifacts') as tmp:
            root=Path(tmp)
            (root/em.ALLOWED[0]).write_text(json.dumps(r)+'\n')
            (root/em.ALLOWED[1]).write_text('' if other is None else json.dumps(other)+'\n')
            result=em.prepare(root,root/'out')
            jobs=json.loads((root/'out/jobs.json').read_text())['jobs']
            return result,jobs

    def test_gold_and_hidden_evaluation_metadata_not_in_predictor(self):
        r=fixture();s,jobs=self.run_record(r)
        self.assertEqual((s['independent_bases'],s['unique_saved_checked_interventions']),(1,1))
        self.assertNotIn('verified_status',jobs[0]['predictor'])
        self.assertNotIn('gold',jobs[0]['predictor'])
        other=copy.deepcopy(r);other['repair']['log'][0]['check']=1
        _,changed=self.run_record(other)
        self.assertEqual(jobs[0]['id'],changed[0]['id'])

    def test_changed_design_changes_identity(self):
        r=fixture();_,a=self.run_record(r)
        r['designs'][1]['body']['torso_mass']=2.5;_,b=self.run_record(r)
        self.assertNotEqual(a[0]['id'],b[0]['id'])

    def test_post_outcome_posterior_rejected(self):
        r=fixture();r['engine']['experiments'].append({'kind':'check'})
        with self.assertRaises(ValueError):self.run_record(r)

    def test_missing_ledger_check_rejected(self):
        r=fixture();r['engine']['ledger']['lines'][0]['detail']['design']=0
        with self.assertRaises(ValueError):self.run_record(r)

    def test_duplicate_episode_rejected(self):
        r=fixture()
        with self.assertRaises(ValueError):self.run_record(r,r)

    def test_invalid_count_rejected(self):
        for y in (-1,9,True,2.5):
            r=fixture();r['repair']['log'][0]['check']=y
            with self.subTest(y=y),self.assertRaises(ValueError):self.run_record(r)

    def test_alternative_has_no_invented_full_label(self):
        r=fixture();r['designs'].append({'index':2,'body':{'torso_mass':3.},'vector':[0.]})
        r['repair']['log'].append({'design':2,'check':8})
        r['engine']['ledger']['lines'].append({'item':'robustness_check','detail':{'design':2,'n':8}})
        s,j=self.run_record(r)
        self.assertEqual(s['alternative_interventions_without_full_verification'],1)
        self.assertIsNone(j[1]['evaluation']['verified_status'])

    def test_task_limits_do_not_reuse_r0_allowance(self):
        import em1_ops
        c={'first_start_epoch':1000.,'initial_spend_usd':100.,'cloud_credit_usd':26.51}
        hours,dollars=em1_ops.limits(c,105.,1000.+3600.)
        self.assertAlmostEqual(hours,5-5/60)
        self.assertEqual(dollars,7.)
        self.assertLess(em1_ops.limits(c,100.,1000.+6*3600)[0],0.)

    def test_worker_error_retains_identity_and_traceback(self):
        from unittest.mock import patch
        with patch.object(em,'predict',side_effect=RuntimeError('sentinel')):
            r=em.measure_one({'id':'bad-job'})
        self.assertEqual(r['id'],'bad-job')
        self.assertIn('RuntimeError: sentinel',r['error'])

    def test_duplicate_design_indices_are_one_physical_intervention(self):
        r=fixture();d=copy.deepcopy(r['designs'][1]);d['index']=2;r['designs'].append(d)
        r['repair']['log'].append({'design':2,'check':7})
        r['engine']['ledger']['lines'].append({'item':'robustness_check','detail':{'design':2,'n':8}})
        s,j=self.run_record(r)
        self.assertEqual((s['logged_check_entries'],len(j)),(2,1))
        self.assertEqual(j[0]['evaluation']['design_indices'],[1,2])
        self.assertTrue(j[0]['evaluation']['is_original_submission'])

    def test_conflicting_duplicate_physics_is_rejected(self):
        r=fixture();d=copy.deepcopy(r['designs'][1]);d['index']=2;r['designs'].append(d)
        r['repair']['log'].append({'design':2,'check':1})
        r['engine']['ledger']['lines'].append({'item':'robustness_check','detail':{'design':2,'n':8}})
        with self.assertRaises(ValueError):self.run_record(r)

    def test_analysis_rejects_incomplete_comparison(self):
        import em1_g0_analyze
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'artifacts') as tmp:
            p=Path(tmp);(p/'jobs.json').write_text(json.dumps({'jobs':[{'id':'missing'}]}))
            with self.assertRaisesRegex(ValueError,'incomplete'):
                em1_g0_analyze.analyze(p)

if __name__=='__main__':unittest.main()
