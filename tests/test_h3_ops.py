"""Newly approved H3 operational caps only; no provider or physics calls."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from h3_ops import remaining


class Limits(unittest.TestCase):
    def test_time_money_and_shutdown_lag(self):
        a={'authorized_epoch':1000,'deadline_epoch':11800,'credit':{'available_usd':19.71}}
        c={'first_start_epoch':1100,'initial_spend_usd':125}
        h,d,cutoff=remaining(a,c,127,2800)
        self.assertEqual((h,d,cutoff),(2.25,6,11800))
        self.assertEqual(remaining(a,c,133,11800)[:2],(0,0))

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):remaining({'authorized_epoch':0,'deadline_epoch':10800,'credit':{'available_usd':19.71}}, {'first_start_epoch':0,'initial_spend_usd':0},float('nan'),0)
