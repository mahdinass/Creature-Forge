import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from creature_forge.decision_trace import Journal, TracePool, verify_journal, plain
from creature_forge.forge_pool import InlinePool


def echo(x):
    return x['value']


class TraceTests(unittest.TestCase):
    def temp(self):
        root = Path('artifacts/di1_test_tmp'); root.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=root)

    def test_jobs_fixed_before_first_outcome_and_exact_order(self):
        with self.temp() as d:
            path=Path(d)/'trace.jsonl'; j=Journal(path)
            out=TracePool(InlinePool(),j).map(echo,[{'value':3,'plant':{'secret':42}}, {'value':1}]); j.close()
            self.assertEqual(out,[3,1]); self.assertEqual(verify_journal(path)['records'],3)
            rows=[json.loads(l) for l in path.read_text().splitlines()]
            self.assertNotIn('secret',path.read_text()); self.assertEqual(rows[0]['kind'],'jobs_before')
            self.assertEqual(len(rows[0]['jobs']),2)

    def test_exclusive_journal(self):
        with self.temp() as d:
            p=Path(d)/'j'; j=Journal(p); j.close()
            with self.assertRaises(FileExistsError): Journal(p)

    def test_tampering_fails(self):
        with self.temp() as d:
            p=Path(d)/'j'; j=Journal(p); j.emit('x',value=4); j.close()
            p.write_text(p.read_text().replace('"value":4','"value":5'))
            with self.assertRaises(ValueError): verify_journal(p)

    def test_hidden_plant_recursive_redaction(self):
        self.assertEqual(plain({'a':[{'plant':{'deviation':[1]},'x':2}]}),{'a':[{'x':2}]})

    def test_ops_rejects_runtime_overrun(self):
        s=importlib.util.spec_from_file_location('di1_ops',Path('scripts/di1_ops.py'))
        import sys
        sys.path.insert(0,str(Path('scripts').resolve()))
        m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        c={'first_start_epoch':1000,'initial_spend_usd':100,'cloud_credit_usd':23.28}
        h,d=m.limits(c,105,1000+6*3600);self.assertEqual(h,0);self.assertEqual(d,7)
        with self.assertRaises(ValueError):m.limits(c,float('nan'),1000)

    def test_exact_power_and_small_sample_uncertainty(self):
        import sys
        sys.path.insert(0,str(Path('scripts').resolve()))
        from di1_analyze import power,upper_rate,rate_interval
        self.assertEqual(power(5,1.,1.),0.)
        self.assertAlmostEqual(power(6,1.,1.),1.)
        self.assertAlmostEqual(upper_rate(0,8),1-.05**(1/8))
        self.assertEqual(rate_interval(0,0),[0.,1.])

    def test_probe_policy_uses_only_frozen_ranked_candidates(self):
        import sys
        sys.path.insert(0,str(Path('scripts').resolve()))
        from di1_study import choose
        scored=[(.3,.3,{'id':'weigh','cost':1}),(.2,.8,{'id':'floor','cost':4}),(.1,.4,{'id':'cf','cost':4})]
        self.assertEqual(choose(scored,'baseline','x')[0]['id'],'weigh')
        self.assertEqual(choose(scored,'raw_eig','x')[0]['id'],'floor')
        r,p=choose(scored,'random','x');self.assertIn(r['id'],('floor','cf'));self.assertEqual(p,.5)
        self.assertEqual(choose(scored,'random','x'),choose(scored,'random','x'))


if __name__=='__main__':unittest.main()
