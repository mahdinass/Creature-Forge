"""Non-physics H3 contracts. Synthetic inputs are NOT recovery evidence."""
import copy
from functools import partial
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np

from creature_forge import h3_capability as h3, hidden_plant as hp, phasegait_init as factory
from creature_forge.creature_walk import R2_WINNER
from creature_forge.sandbox import SandboxBody

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import h3_run as runner
import h3_analyze as analysis

V=list(R2_WINNER)+[.5,.5]


def synthetic_contract_job(job):
    """Spawn-only controller contract test, never a physical rollout."""
    with patch('mujoco.mj_step',side_effect=AssertionError('no physics')), patch('mujoco.mj_forward',side_effect=AssertionError('no physics')):
        if job.get('fail'):raise RuntimeError('synthetic spawned failure')
        with h3.controller_scope((.2,-.1)):
            c=factory.controller_from_vector(V,body=SandboxBody())
            c.reset(100,200);c.sense(0,[0,0])
            tau=c.torque(.01,0,0,np.zeros(6),np.zeros(6))
        return {'ok':True,'dimension':len(tau),'restored':factory.controller_from_vector(V,body=SandboxBody()).name!='h3_stance_residual_v1'}


class NonPhysics(unittest.TestCase):
    def setUp(self):
        self.patches=[patch('mujoco.mj_step',side_effect=AssertionError('physics forbidden in H3 unit tests')),
                      patch('mujoco.mj_forward',side_effect=AssertionError('physics forbidden in H3 unit tests'))]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def ctrl(self,gains=(0.,0.),log=False):
        c=h3.StanceResidual(factory.controller_from_vector(V,body=SandboxBody()),gains,log=log)
        c.reset(100,200)
        return c

    def test_zero_identity_real_controller_on_synthetic_inputs(self):
        a=factory.controller_from_vector(V,body=SandboxBody());a.reset(100,200)
        b=self.ctrl(log=True)
        for i in range(500):
            t=i*.005
            forces=[100 if i%100<50 else 0,100 if i%100>=50 else 0]
            a.sense(t,forces);b.sense(t,forces)
            args=(t,.02*np.sin(t),.03,np.full(6,.05),np.full(6,.1))
            np.testing.assert_array_equal(a.torque(*args),b.torque(*args))
        self.assertEqual(len(b.samples),500)

    def test_cap_stance_airborne_ramp_and_leg_sign(self):
        c=self.ctrl((1,-1))
        c.base.est.deb=[True,True]
        # Fake only the torque producer, fixing phase to isolate residual gates.
        with patch.object(c.base,'torque',return_value=np.zeros(6)):
            c.base.phi=c.p.duty/2
            tau=c.torque(10,0,0,[0]*6,[0]*6)
            self.assertAlmostEqual(tau[0],15);self.assertAlmostEqual(tau[2],-15)
            c.base.phi=(c.p.duty/2-.5)%1
            tau=c.torque(10,0,0,[0]*6,[0]*6)
            self.assertAlmostEqual(tau[3],-15);self.assertAlmostEqual(tau[5],15)
            c.base.est.deb=[False,False]
            np.testing.assert_array_equal(c.torque(10,0,0,[0]*6,[0]*6),np.zeros(6))
            c.base.est.deb=[True,True]
            np.testing.assert_array_equal(c.torque(0,0,0,[0]*6,[0]*6),np.zeros(6))

    def test_residual_bounds_all_phases_and_reset(self):
        c=self.ctrl((-.8,.7),log=True)
        with patch.object(c.base,'torque',return_value=np.zeros(6)):
            c.base.est.deb=[True,True]
            for phase in np.linspace(0,1,101):
                c.base.phi=phase
                t=c.torque(10,0,0,[0]*6,[0]*6)
                self.assertLessEqual(float(np.abs(t).max()),15+1e-12)
                self.assertEqual(t[1],0);self.assertEqual(t[4],0)
        c.reset(50,200);self.assertEqual(c.samples,[])

    def test_invalid_vectors_and_gains(self):
        for v in (V+[2,0],V+[np.nan,0],V[:-1],[[0]*17]):
            with self.assertRaises(ValueError):h3.split_vector(v)
        for g in ((1.1,0),(np.inf,0),(0,),()):
            with self.assertRaises(ValueError):self.ctrl(g)

    def test_zero_object_identity(self):
        c=self.ctrl();tau=np.zeros(6,dtype=np.float32)
        with patch.object(c.base,'torque',return_value=tau):
            self.assertIs(c.torque(1,0,0,[0]*6,[0]*6),tau)

    def test_bridge_restore_nesting_and_thread_guard(self):
        original=factory.controller_from_vector
        # Model the documented dedicated-worker contract; other suite tests may
        # leave unrelated service threads in the test runner's parent process.
        with patch('threading.active_count',return_value=1), self.assertRaisesRegex(RuntimeError,'sentinel'):
            with h3.controller_scope((0,0)) as made:
                self.assertIsInstance(factory.controller_from_vector(V,body=SandboxBody()),h3.StanceResidual)
                self.assertEqual(len(made),1)
                with self.assertRaisesRegex(RuntimeError,'nested'):
                    with h3.controller_scope((0,0)):pass
                raise RuntimeError('sentinel')
        self.assertIs(factory.controller_from_vector,original)
        with patch('threading.active_count',return_value=2):
            with self.assertRaises(RuntimeError):
                with h3.controller_scope((0,0)):pass

    def test_seed_bridge_keeps_input_and_17_path(self):
        job={'controllers':{'walk':{'vector':V+[.2,-.3]}},'body':{}}
        before=copy.deepcopy(job)
        def fake(j,plant=None):
            self.assertEqual(len(j['controllers']['walk']['vector']),17)
            return {'ok':True}
        with patch('threading.active_count',return_value=1), patch.object(hp,'seed_job',side_effect=fake):
            self.assertTrue(h3.seed_job(job)['ok'])
        self.assertEqual(job,before)
        plain={'vector':V}
        with patch.object(hp,'walk_job',return_value={'ok':True}) as f:
            h3.walk_job(plain);self.assertIs(f.call_args.args[0],plain)

    def test_real_background_thread_is_rejected(self):
        stop=threading.Event();t=threading.Thread(target=stop.wait);t.start()
        try:
            with self.assertRaisesRegex(RuntimeError,'single-thread'):
                with h3.controller_scope((0,0)):pass
        finally:stop.set();t.join()

    def test_budget_reserves_before_dispatch_and_errors(self):
        reservations=[];calls=[]
        pool=h3.BudgetPool(3,4,on_reserve=lambda r,e:reservations.append((r,e)))
        def f(job):
            self.assertTrue(reservations);calls.append(job);return 1
        list(pool.imap(f,[{'duration':20},{'duration':10}]))
        self.assertEqual((pool.rollouts,pool.equivalents),(2,3))
        with self.assertRaises(RuntimeError):list(pool.imap(f,[{'duration':20}]))
        self.assertEqual(len(calls),2)
        with self.assertRaises(ValueError):list(pool.imap(f,[{'duration':float('nan')}]))

    def test_worker_error_reservation_is_not_reset(self):
        pool=h3.BudgetPool(2,2)
        with self.assertRaisesRegex(RuntimeError,'worker error'):
            list(pool.imap(lambda job:{'ok':False,'error':'synthetic'},[{'duration':10}]))
        self.assertEqual((pool.rollouts,pool.equivalents),(1,1))

    def test_spawn_bridge_contract_without_physics(self):
        from creature_forge.forge_pool import ForgePool
        with ForgePool(max_workers=2) as inner:
            pool=h3.BudgetPool(3,3,inner=inner)
            rows=list(pool.imap(synthetic_contract_job,[{'duration':10},{'duration':10}]))
            self.assertEqual(len(rows),2)
            self.assertTrue(all(r['dimension']==6 and r['restored'] for _,r in rows))
            with self.assertRaisesRegex(RuntimeError,'synthetic spawned failure'):
                list(pool.imap(synthetic_contract_job,[{'duration':10,'fail':True}]))
            self.assertEqual(pool.rollouts,3)

    def test_completed_unit_manifest_detects_mutation_and_extra_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=root/'plan.json';plan.write_text('{}');unit=root/'unit';unit.mkdir()
            runner.save(unit/'result.json',{'phase':'gate','plan_sha256':runner.sha(plan),'passed':True})
            runner.seal_unit(unit)
            self.assertTrue(runner.check_unit(unit,plan,'gate')['passed'])
            (unit/'unlisted').write_text('test')
            with self.assertRaisesRegex(ValueError,'coverage'):runner.check_unit(unit,plan,'gate')
            (unit/'unlisted').unlink()
            (unit/'result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):runner.check_unit(unit,plan,'gate')

    def test_search_budget_dimensions_synthetic_only(self):
        counts=[]
        def fake(plant,seeds,pool=None):
            def evaluate(candidates):
                counts.append((len(candidates)*len(seeds),len(candidates[0][1])))
                return [{'walking_count':0,'survival_count':len(seeds),'mean_fitness':-sum(v),'error':None}
                        for b,v in candidates]
            return evaluate
        with patch.object(hp,'make_eval_fn',side_effect=fake):
            for expanded,dim in ((False,17),(True,19)):
                counts.clear()
                r=h3.search({},V,{},expanded=expanded,budget=120,seeds=[1,2,3,4],selection=list(range(8,16)),noise_seed=3,pool=None)
                self.assertEqual(sum(n for n,d in counts),120);self.assertTrue(all(d==dim for n,d in counts))
                self.assertEqual(r['policy_rollouts'],120)

    def test_search_error_stops_synthetic_dispatch(self):
        def fake(*args,**kw):
            return lambda candidates:[{'error':'synthetic worker fault'} for _ in candidates]
        with patch.object(hp,'make_eval_fn',side_effect=fake):
            events=[]
            with self.assertRaisesRegex(RuntimeError,'training errors'):
                h3.search({},V,{},expanded=True,budget=120,seeds=[1,2,3,4],selection=list(range(8,16)),noise_seed=3,pool=None,progress=events.append)
            self.assertEqual([e['stage'] for e in events],['before_train','after_train'])
            self.assertEqual(events[0]['seeds'],[1,2,3,4]);self.assertEqual(len(events[0]['vectors']),1)

    def test_prepared_plan_seed_roles_sources_and_caps(self):
        p=runner.make_plan();runner.check_plan(p)
        self.assertEqual(len(p['draws']),48)
        seen=set()
        for d in p['draws']:
            roles=[d[k] for k in ('qual_healthy10','qual_healthy20','qual_damaged','healthy_guard','diagnostic')]
            roles+=d['train']+d['select']
            roles+=[s for panel in d['panels'] for s in panel.values()]
            seeds=[s for role in roles for s in role]
            self.assertEqual(len(seeds),len(set(seeds)))
            self.assertFalse(seen & set(seeds));seen.update(seeds)
            hp.normalize_plant(d['plant'])
        self.assertEqual(p['total_cap_equivalents'],12*p['case_cap_equivalents']+p['gate_cap_equivalents']+p['qualify_cap_equivalents'])
        broken=copy.deepcopy(p);broken['sources']['scripts/h3_run.py']='0'*64
        with self.assertRaisesRegex(ValueError,'source differs'):runner.check_plan(broken)

    def test_authorization_binds_plan_campaign_time_and_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=root/'plan.json';plan.write_text('{}');receipt=root/'auth.json'
            a={'study':'h3-pilot-v1','protocol_sha256':runner.sha(plan),'phases':['gate'],
               'human_message_reference':'SYNTHETIC UNIT TEST ONLY','authorized_epoch':999,'deadline_epoch':1100,
               'cloud_cap_usd':8,'token_factory_cap_usd':0,'campaign_directory':str(root/'campaign')}
            receipt.write_text(json.dumps(a))
            with patch.object(runner.time,'time',return_value=1000):
                runner.require_authorization(receipt,plan,'gate',root/'campaign')
                with self.assertRaises(ValueError):runner.require_authorization(receipt,plan,'case',root/'campaign')
                with self.assertRaises(ValueError):runner.require_authorization(receipt,plan,'gate',root/'other')
            with patch.object(runner.time,'time',return_value=1101):
                with self.assertRaises(ValueError):runner.require_authorization(receipt,plan,'gate',root/'campaign')

    def test_diagnostic_audit_bound_and_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'cases'/'sample';d.mkdir(parents=True)
            trace={'meta':{'torque_limit':100},'controller_pre_step':[{'base_demand':[0]*6,'residual':[1,0,0,0,0,0]}],
                   'trace':{k:[[0]*6] for k in ('q','qd','tau','demand','force','slip')}}
            for i in range(2):(d/f'residual_0_trace{i}.json').write_text(json.dumps(trace))
            c=[{'id':'sample','results':[{'arm':'residual','rep':0}]}]
            r=analysis.diagnostic_audit(root,c)
            self.assertEqual(r['active_residual_bases'],1);self.assertFalse(r['passed'])
            trace['controller_pre_step'][0]['residual'][0]=16
            (d/'residual_0_trace0.json').write_text(json.dumps(trace))
            with self.assertRaisesRegex(ValueError,'out-of-bound'):analysis.diagnostic_audit(root,c)

    def test_execution_default_refusal(self):
        with patch.object(sys,'argv',['h3_run.py','gate','--out','unused']):
            with self.assertRaisesRegex(ValueError,'execution disabled'):runner.main()
        with self.assertRaises(ValueError):runner.require_authorization(None,'unused','gate','unused')

    def test_save_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.json';runner.save(p,{'x':1})
            with self.assertRaises(FileExistsError):runner.save(p,{'x':2})
            self.assertEqual(json.loads(p.read_text()),{'x':1})

    def test_analysis_rejects_pseudoreplication_missing_lineages(self):
        q={'passed':True,'accepted':{'left':['same']*6,'right':['same']*6}}
        self.assertEqual(analysis.analyze({},q,[])['decision'],'NO-GO')

    def fixture(self):
        """Fabricated unit-test schema, never a research artifact or result."""
        draws=[];cases=[]
        for i in range(12):
            seeds=[{'validate':list(range(24)), 'confirm':list(range(24,48))} for _ in range(3)]
            draws.append({'id':str(i),'side':'left' if i<6 else 'right','panels':seeds,
                          'body':SandboxBody().as_dict(),'healthy_guard':list(range(8))})
            results=[]
            for arm in analysis.ARMS:
                for rep in range(2):
                    panels=[self.fake_panel(arm=='residual',s) for s in seeds]
                    results.append({'arm':arm,'rep':rep,'candidate':{'body':SandboxBody().as_dict(),'vector':V+[0,0] if arm=='residual' else V},
                                    'panels':panels,'healthy':[{'seed':s,'outcome':'PASS','walking':True} for s in range(8)]})
            cases.append({'id':str(i),'results':results})
        q={'passed':True,'accepted':{'left':list(map(str,range(6))),'right':list(map(str,range(6,12)))}}
        from creature_forge.arena import VARIATION_PRESET
        return {'draws':draws,'variation':dict(VARIATION_PRESET)},q,cases

    def fake_panel(self,full,seeds):
        from creature_forge import recovery as rc
        def rows(body,vector,seeds,**kw):
            success=full and len(vector)==19
            return [{'seed':s,'outcome':'PASS' if success else 'POOR','walking':success,'score':1. if success else 0.,
                     'fell':False,'error':None,'speed_upright':1. if success else 0.,'body_contact_frac':0.}
                    for s in seeds]
        original={'body':SandboxBody().as_dict(),'vector':V}
        candidate={**original,'vector':V+[0.,0.]}
        with patch.object(rc,'run_walk_seeds',side_effect=rows):
            return rc.assess(original,candidate,seeds['validate'],seeds['confirm'])

    def test_grouped_analysis_pass_fail_and_harm(self):
        plan,q,cases=self.fixture()
        r=analysis.analyze(plan,q,cases)
        self.assertEqual(r['decision'],'PASS-PILOT')
        self.assertEqual(r['full_contrasts']['current']['descriptive95'],[1.,1.])
        self.assertEqual(r['persistent_rescue_bases'],12)
        bad=copy.deepcopy(cases)
        for c in bad:
            for r in c['results']:
                if r['arm']=='residual':r['healthy']=[{**x,'walking':False,'outcome':'POOR'} for x in r['healthy']]
        self.assertEqual(analysis.analyze(plan,q,bad)['decision'],'FAIL')
        for c in cases:
            for r in c['results']:
                r['panels']=[self.fake_panel(False,p['seeds']) for p in r['panels']]
        self.assertEqual(analysis.analyze(plan,q,cases)['decision'],'FAIL')

    def test_analysis_incomplete_panels_and_seed_drift_refuse(self):
        plan,q,cases=self.fixture()
        cases[0]['results'][0]['panels'].pop()
        with self.assertRaises(ValueError):analysis.analyze(plan,q,cases)
        plan,q,cases=self.fixture()
        cases[0]['results'][0]['panels'][0]['seeds']={'validate':[999], 'confirm':[]}
        with self.assertRaises(ValueError):analysis.analyze(plan,q,cases)

    def test_positive_but_unstable_is_insufficient(self):
        plan,q,cases=self.fixture()
        for c in cases:
            for r in c['results']:
                if r['arm']=='residual':
                    for i in (1,2):r['panels'][i]=self.fake_panel(False,r['panels'][i]['seeds'])
        a=analysis.analyze(plan,q,cases)
        self.assertEqual(a['decision'],'INSUFFICIENT EVIDENCE')
        self.assertEqual(a['first_panel_full_not_stable']['residual'],{'numerator':24,'denominator':24})

    def test_candidate_and_healthy_condition_drift_refused(self):
        plan,q,cases=self.fixture()
        cases[0]['results'][0]['candidate']['body']['torso_mass']+=1
        with self.assertRaisesRegex(ValueError,'candidate body'):analysis.analyze(plan,q,cases)
        plan,q,cases=self.fixture()
        cases[0]['results'][0]['healthy'][0]['seed']=999
        with self.assertRaisesRegex(ValueError,'healthy rows'):analysis.analyze(plan,q,cases)

    def test_case_freezes_six_policies_before_first_verifier_synthetic_only(self):
        from creature_forge import recovery as rc
        plan=runner.make_plan();d=plan['draws'][0];events=[]
        def search(body,vector,plant,**kw):
            events.append('search')
            return {'candidate':{'body':body,'vector':vector+[0,0] if kw['expanded'] else vector}}
        def assess(*args,**kw):events.append('verify');return {'status':'NOT_RECOVERED'}
        class FakePool:
            def imap(self,fn,jobs):
                for i,_ in enumerate(jobs):yield i,{'synthetic_unit_test_only':True}
        with tempfile.TemporaryDirectory() as tmp, patch.object(h3,'search',side_effect=search), patch.object(rc,'assess',side_effect=assess), patch.object(rc,'run_walk_seeds',return_value=[{'walking':True}]*8):
            result=runner.case(plan,d['id'],FakePool(),Path(tmp))
        self.assertEqual(events[:6],['search']*6);self.assertEqual(events.count('verify'),18)
        self.assertEqual(len(result['results']),6)


if __name__=='__main__':unittest.main()
