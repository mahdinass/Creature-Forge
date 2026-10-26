"""H1 identity, missing-data, grouped gate and hard-budget guards; no physics."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import h1_counterfactual as h
import h1_ops as ops


class H1Guards(unittest.TestCase):
    def test_exact_frozen_cohort(self):
        p,cc,pairs,known=h.load(h.STUDY)
        self.assertEqual((len(cc),len(pairs),len(known),len(p['missing_keys'])),(640,324,320,320))
        self.assertEqual(set(cc)-set(known),set(p['missing_keys']))
        self.assertEqual(len({r['base_id'] for r in pairs}),18)
        for c in cc.values():
            self.assertFalse(set(c['seeds']['validate']) & set(c['seeds']['confirm']))
            self.assertEqual(len(c['seeds']['validate']),24)

    def test_no_outcomes_is_not_evaluable(self):
        with patch.object(Path,'exists',return_value=False):
            result=h.analyze(h.STUDY,ROOT/'artifacts/nonexistent-h1-tests')
        self.assertEqual(result['stage_a_signal'],'NOT EVALUABLE')
        self.assertIsNone(result['base_equal_oracle_gain'])
        self.assertEqual(result['new_equivalents'],0)
        self.assertEqual(result['reverse_screens'],1)

    def test_unexecuted_confirmation_is_missing(self):
        v={'status':'NOT_RECOVERED','validation':{'verdict':{'status':'WORSE'},'aggregate':'FAIL'},'confirmation':{'run':False}}
        c=h.components(v)
        self.assertIsNone(c['confirmation_walking_frac'])
        self.assertIsNone(c['confirmation_body_contact'])
        self.assertFalse(c['improvement'])

    def test_errors_are_not_failures(self):
        self.assertIsNone(h.components({'status':'INCONCLUSIVE_ERROR'}))
        self.assertIsNone(h.components({'status':h.FULL,'errors':['seed failure']}))

    def test_condition_is_part_of_identity(self):
        d={'body':{},'vector':[]};s={'validate':[1],'confirm':[2]}
        self.assertNotEqual(h.key('x',d,s,{}),h.key('x',d,{'validate':[3],'confirm':[2]},{}))
        self.assertNotEqual(h.key('x',d,s,{}),h.key('y',d,s,{}))

    def test_runtime_money_and_reserve_are_cumulative(self):
        c={'initial_spend_usd':123,'first_start_epoch':1000,'credit':{'available_usd':21.04}}
        hrs,money=ops.limits(c,125,4600)
        self.assertAlmostEqual(hrs,4.5);self.assertAlmostEqual(money,14.04)
        self.assertEqual(ops.limits(c,125,1000+6*3600)[0],0)
        with self.assertRaises(ValueError):ops.limits(c,float('nan'),4600)

    def test_malformed_full_arrays_are_rejected(self):
        import h1_audit
        p,cc,_,_=h.load(h.STUDY);c=next(iter(cc.values()))
        v={'status':h.FULL,'rule':'full_recovery_v1','seeds':c['seeds'],'variation':c['variation'],
           'validation':{'original':[],'candidate':[]}}
        with self.assertRaises(AssertionError):h1_audit.check(v,c)


if __name__=='__main__':unittest.main()
