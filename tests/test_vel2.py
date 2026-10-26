import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vel2_repeatability as v
import vel2_ops as ops


class Guards(unittest.TestCase):
    def row(self,id='a',base='b'):
        d={'body':{'torso_mass':2},'vector':[1,2]}
        return {'unit_id':id,'base_id':base,'result':{'design':d,'selected':0,
                'selection':[{'walking_count':7,'design_hash':v.sha(v.canonical(d))}]}}

    def test_future_labels_not_selection_inputs(self):
        rows=[self.row('a'),self.row('b','c')];a=v.select(rows)
        for r in rows:r['verification']={'status':'FULL_RECOVERY','hidden_family':'anything'}
        self.assertEqual([r['unit_id'] for r in a],[r['unit_id'] for r in v.select(rows)])

    def test_duplicate_one_ticket_and_base_grouping(self):
        self.assertEqual(len(v.select([self.row(),self.row('z')])),1)
        self.assertEqual(len(v.select([self.row(),self.row('z','c')])),2)

    def test_physical_identity(self):
        r=self.row();r['result']['design']['vector'][0]=3
        with self.assertRaises(ValueError):v.select([r])

    def test_seed_panels_disjoint(self):
        used={1,2,3};a=v.panels('b',used);b=v.panels('c',used)
        self.assertEqual(len(used),195)
        self.assertEqual(a,v.panels('b',{1,2,3}))
        with self.assertRaises(ValueError):v.panels('b',used)

    def test_error_not_nonfull(self):
        with self.assertRaises(ValueError):v.components({'status':'INCONCLUSIVE_ERROR'})

    def test_confirmation_missing(self):
        c=v.components({'status':'NOT_RECOVERED','validation':{'verdict':{'status':'NO_EVIDENCE'},'aggregate':'FAIL'},'confirmation':{'run':False}})
        self.assertIsNone(c['confirmation_body_contact'])

    def test_cost_and_cutoff(self):
        c={'initial_spend_usd':100,'first_start_epoch':ops.CUTOFF-3600,'credit':{'available_usd':21.34}}
        self.assertEqual(ops.limits(c,102,ops.CUTOFF),(0,4))
        self.assertEqual(ops.limits(c,107,ops.CUTOFF)[1],-1)
        with self.assertRaises(ValueError):ops.limits(c,float('nan'),ops.CUTOFF)

    def test_authoritative_full_unchanged(self):
        from creature_forge import recovery as r
        self.assertEqual((r.RECOVERY_RULE,r.VALIDATE_N,r.CONFIRM_N,r.TRAIN_DURATION,r.CONFIRM_DURATION,r.PASS_FRAC),
                         ('full_recovery_v1',24,24,10,20,.8))
        study=v.STUDY
        if (study/'stage_a_protocol.json').exists():v.load(study)


if __name__=='__main__':unittest.main()
