"""Stage B development-only guards without physics."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import h1_reliability as b


class ReliabilityGuards(unittest.TestCase):
    def test_requires_audited_stage_a_advance(self):
        with patch.object(b.h,'read',return_value={'stage_a_signal':'NO-GO','gate':False}):
            with self.assertRaises(ValueError):b.prepare('never','never')

    def test_full_complete_cohort_matched_panels(self):
        p,jobs=b.load(b.STUDY);_,cc,_,_=b.h.load(b.h.STUDY)
        self.assertEqual(len(jobs),1280)
        self.assertEqual(len({j['candidate_key'] for j in jobs}),640)
        seen={};owners={}
        old={s for c in cc.values() for ss in c['seeds'].values() for s in ss}
        for j in jobs:
            base=cc[j['candidate_key']]['base_id'];k=(base,j['panel'])
            if k in seen:self.assertEqual(j['seeds'],seen[k])
            seen[k]=j['seeds']
            for role,ss in j['seeds'].items():
                self.assertEqual(len(set(ss)),24);self.assertFalse(old&set(ss))
                for s in ss:
                    if s in owners:self.assertEqual(owners[s],(base,j['panel'],role))
                    owners[s]=(base,j['panel'],role)
        self.assertEqual((len(seen),len(owners)),(36,1728))

    def test_whole_base_bootstrap_reproducible(self):
        self.assertEqual(b.interval([0,.1,.2]),b.interval([0,.1,.2]))
        self.assertEqual(b.interval([0]*18),[0,0])


if __name__=='__main__':unittest.main()
