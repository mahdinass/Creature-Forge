"""Tests of the mechanism-investigation AI director (`creature_forge.mech_director`). No network and no MuJoCo simulation: replies come from a
scripted fixture, `mech_pipelines.run_mech_pipeline` runs with its synthetic `eval_override`, and a stand-in for `creature_forge.mechanisms`
is injected."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from creature_forge import director as dr
from creature_forge import gait_features as gf
from creature_forge import mech_director as md
from creature_forge import mech_pipelines as mpl
from creature_forge.inference_ledger import Caps, InferenceLedger
from creature_forge.investigation import LiveRefused, SCRIPTED_MODEL
from creature_forge.nebius import NebiusError

from tests.test_mech_pipelines import PB, SCREEN_N, SEEDS, STUB, Fake, run

KEY = "sk-test-SECRET-0123456789abcdef"
REF = {"L": 1.2, "foot_to_leg": 0.1}


def hyp(i="H1", ev=("creature.thigh_length", "baseline.froude"), competing=("friction too low",)):
    return {"id": i, "mechanism": "the torso runs ahead of the feet", "evidence": list(ev), "competing": list(competing)}


def mech(mid="good1", hypothesis="H1", terms=("pitch", "d", "v"), target="hip", leg="swing", bound=2.0, revises="none",
         ev=("baseline.froude",), rationale="feedback on the stance offset", expect="improves"):
    return {"id": mid, "hypothesis": hypothesis, "expect": expect, "target": target, "leg": leg, "terms": list(terms),
            "gain_bound": bound, "rationale": rationale, "revises": revises, "evidence": list(ev)}


def inv(hyps=(), refuted=(), mechs=(), probes=(), stop=False):
    return {"hypotheses": list(hyps), "refuted": list(refuted), "mechanisms": list(mechs), "probes": list(probes), "stop": stop}


def fplan(init="start", subs=("timing",), body=(), mechs=(), share=1.0, h="H1", ev=("start.walking_count",)):
    return {"init": init, "ctrl_subspaces": list(subs), "body_params": list(body), "mechanisms": list(mechs), "budget_share": share,
            "hypothesis": h, "prediction": "walking seeds go up", "evidence": list(ev)}


def fin(plans, refuted=(), diagnosis="the stance mechanism helps"):
    return {"refuted": list(refuted), "diagnosis": diagnosis, "plans": list(plans)}


R1 = inv([hyp()], mechs=[mech("good1"), mech("flat1", terms=("pitch_rate",), target="ankle", leg="both", bound=1.0)],
         probes=[{"probe_id": "opt_body", "hypothesis": "H1", "expect": "improves"}])
R2 = inv([hyp("H2")], refuted=["H1"],
         mechs=[mech("good2", "H2", terms=("pitch", "d"), revises="flat1", ev=("mechanisms.flat1.all_gains_near_zero", "mechanisms.good1.delta_walking"),
                     rationale="flat1 gains stayed at zero while good1 helped")], stop=True)
F = fin([fplan("good1", ("timing",), (), ["good1"], 0.6, "H2"), fplan("start", (), (), ["good2"], 0.4, "H2")])
GOOD = [R1, R2, F]


class Base(unittest.TestCase):
    def setUp(self):
        self._prev = mpl._MX_OVERRIDE
        mpl.set_mechanisms_module(STUB)
        self.addCleanup(mpl.set_mechanisms_module, self._prev)

    def make(self, fixture, mode="iterative", **kw):
        return md.MechDirector(mode, fixture=fixture, reference=REF, **kw)

    def go(self, d, **kw):
        return run(d, **kw)


class EndToEnd(Base):
    def test_iterative_with_revision_and_final_plan(self):
        d = self.make(copy.deepcopy(GOOD), order_seed=3)
        rec, fake = self.go(d)
        self.assertEqual(len(d.calls), 3)
        self.assertEqual([x["kind"] for x in d.decisions], ["investigate", "investigate", "final_plan"])
        self.assertEqual([x["status"] for x in d.decisions], ["ok"] * 3)
        r1, r2 = rec["rounds"]
        self.assertEqual([m["probe_id"] for m in r1["mechanisms"]], ["good1", "flat1"])
        self.assertEqual([p["probe_id"] for p in r1["probes"]], ["opt_body"])
        self.assertEqual(r2["mechanisms"][0]["revises"], "flat1")
        self.assertEqual(rec["mechanisms"]["good2"]["mechanism"]["revises"], "flat1")
        self.assertEqual([p["plan_id"] for p in rec["final_step"]["plans"]], ["f0", "f1"])
        # decisions the director returned are exactly what the pipeline recorded
        returned = [x["returned"] for x in d.record()["decisions"]]
        self.assertEqual(returned, [x["returned"] for x in rec["decisions"]])
        self.assertEqual(d.record()["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(d.record()["model"], SCRIPTED_MODEL)
        self.assertEqual(d.record()["refuted_by_round"], {"1": [], "2": ["H1"], "final": []})
        self.assertTrue(d.hypotheses["H1"]["refuted"])
        # the second call shows the measured feedback of round 1 and what the model decided
        msg = d.calls[1]["messages"][1]["content"]
        self.assertIn("mechanisms.good1.delta_walking = ", msg)
        self.assertIn("mechanisms.flat1.all_gains_near_zero = true", msg)
        self.assertIn("mechanisms.good1.gain0_value = ", msg)
        self.assertIn("mechanisms.good1.change.froude = ", msg)
        self.assertIn("mechanism flat1 [round 1", msg)
        self.assertIn("you expected improves", msg)
        self.assertIn("creature.reference.features.L = 1.2", msg)

    def test_one_shot_makes_one_investigation_call_then_the_final_plan(self):
        d = self.make([R1, fin([fplan("good1", ("timing",), (), ["good1"], 1.0)])], mode="one_shot")
        rec, _ = self.go(d, mode="one_shot")
        self.assertEqual(len(d.calls), 2)
        self.assertEqual(len(rec["rounds"]), 1)
        self.assertEqual([x["kind"] for x in d.decisions], ["investigate", "final_plan"])
        self.assertEqual(d.record()["mech_mode"], "one_shot")
        self.assertIn("one shot", d.system)
        self.assertNotIn("iterative", d.system.lower().split("procedure")[1].split("mechanisms (")[0])
        # a second investigate call (never made by the one-shot pipeline) would not reach the model
        d3 = self.make([], mode="one_shot")
        self.assertEqual(d3.investigate({"round": 2}), {"stop": True})
        self.assertEqual(d3.calls, [])

    def test_iterative_call_counts(self):
        d = self.make([inv([hyp()], mechs=[mech("good1")], stop=True), fin([fplan("good1", mechs=["good1"])])])
        rec, _ = self.go(d, max_rounds=4)
        self.assertEqual(len(d.calls), 2)                              # stop ends the investigation: one round, one final call
        self.assertEqual(rec["stopped_by"], "director_stop")
        d = self.make([inv([hyp()], mechs=[mech("good1")]), inv(), inv(), fin([fplan("good1", mechs=["good1"])])])
        rec, _ = self.go(d, max_rounds=3)
        self.assertEqual(len(d.calls), 4)                              # 3 rounds + final
        self.assertEqual(rec["stopped_by"], "max_rounds")

    def test_stop_in_the_first_round_with_nothing_and_no_hypothesis(self):
        d = self.make([inv(stop=True), fin([fplan("start", ("timing",), (), [], 1.0, "none")])])
        rec, _ = self.go(d)
        self.assertEqual(len(rec["rounds"]), 1)
        self.assertEqual(rec["final_step"]["plans"][0]["plan"]["init"], "start")

    def test_hypotheses_ids_do_not_collide(self):
        d = self.make(copy.deepcopy(GOOD))
        self.go(d)
        self.assertEqual(set(d.hypotheses), {"H1", "H2"})


class RepairAndFailure(Base):
    def test_repair_after_an_invalid_mechanism(self):
        bad = copy.deepcopy(R1)
        bad["mechanisms"][0]["terms"] = ["os.getcwd()"]
        d = self.make([bad, R1, R2, F])
        rec, _ = self.go(d)
        dec = d.record()["decisions"]
        self.assertTrue(dec[0]["repaired"])
        self.assertEqual(dec[0]["status"], "ok")
        self.assertTrue(any("unknown name in term" in e for e in dec[0]["first_attempt_errors"]))
        self.assertEqual(d.calls[1]["settings"]["purpose"], "mech_director_repair")
        self.assertIn("unknown name in term", d.calls[1]["messages"][-1]["content"])
        self.assertEqual(len(rec["rounds"][0]["mechanisms"]), 2)

    def test_repair_for_unparseable_reply(self):
        d = self.make(["no json here", R1, R2, F])
        self.go(d)
        self.assertTrue(d.record()["decisions"][0]["repaired"])
        self.assertEqual(d.record()["decisions"][0]["status"], "ok")

    def test_invalid_after_repair_returns_nothing_and_nothing_is_substituted(self):
        bad = copy.deepcopy(R1)
        bad["mechanisms"][0]["terms"] = ["os.getcwd()"]
        d = self.make([bad, bad, inv(stop=True), fin([fplan("start", ("timing",), (), [], 1.0, "none")])])
        rec, _ = self.go(d)
        dec = d.record()["decisions"]
        self.assertEqual((dec[0]["status"], dec[0]["returned"]), ("invalid_after_repair", {}))
        self.assertEqual(rec["decisions"][0]["returned"], {})
        self.assertEqual(rec["rounds"][0]["mechanisms"], [])
        self.assertEqual(rec["rounds"][0]["probes"], [])
        self.assertEqual(len(d.hypotheses), 0)                           # nothing from a rejected reply is registered
        self.assertEqual(dec[0]["calls"], [0, 1])                        # exactly one repair
        self.assertEqual(dec[1]["calls"], [2])

    def test_final_plan_invalid_after_repair_leaves_the_start(self):
        badf = fin([fplan("good1", mechs=["ghost"])])
        d = self.make([inv([hyp()], mechs=[mech("good1")], stop=True), badf, badf])
        rec, _ = self.go(d)
        fd = d.record()["decisions"][-1]
        self.assertEqual((fd["status"], fd["returned"]), ("invalid_after_repair", []))
        self.assertEqual(rec["final_step"]["plans"], [])
        self.assertIn(rec["final"]["source"], ("start", "good1"))        # only measured candidates; no substituted plan
        self.assertNotIn("f0", {c["source"] for c in rec["candidates"]})

    def test_model_failure_is_not_repaired(self):
        class Boom:
            requests = 0

            def __call__(self, *a):
                Boom.requests += 1
                raise NebiusError("HTTP 500: upstream")
        d = md.MechDirector("iterative", source="scripted", transport=Boom())
        rec, _ = self.go(d, max_rounds=2)
        self.assertEqual(Boom.requests, 3)                               # 2 rounds + final, never retried
        self.assertTrue(all(x["status"] == "model_failed" for x in d.record()["decisions"]))
        self.assertEqual(rec["final"]["source"], "start")


class Validators(Base):
    paths = {"creature.thigh_length", "baseline.froude", "mechanisms.good1.delta_walking", "mechanisms.good1.improved",
             "start.walking_count"}

    def inv(self, reply, **kw):
        a = dict(paths=self.paths, new_ids=["H1", "H2", "H3"], live_ids=[], refutable=[], available=["opt_body", "opt_timing"],
                 revisable=set(), used_mech_ids=set(), structures={}, mech_affordable=True, mode="iterative")
        a.update(kw)
        return md.validate_investigate_reply(reply, **a)

    def test_valid(self):
        e, extra = self.inv(inv([hyp()], mechs=[mech()], probes=[{"probe_id": "opt_body", "hypothesis": "H1", "expect": "improves"}]))
        self.assertEqual(e, [])
        self.assertEqual(extra["probes"], ["opt_body"])
        self.assertEqual(extra["mechanisms"][0]["id"], "good1")
        self.assertNotIn("revises", extra["mechanisms"][0])
        self.assertFalse(extra["stop"])

    def test_errors(self):
        def bad(m, **kw):
            return self.inv(inv([hyp()], mechs=[m]), **kw)[0]
        self.assertTrue(bad(mech(terms=["os.getcwd()"])))
        self.assertTrue(bad(mech(bound=9)))
        self.assertTrue(bad(mech(target="elbow")))
        self.assertTrue(bad(mech(hypothesis="H9")))
        self.assertTrue(bad(mech(ev=())))
        self.assertTrue(bad(mech(ev=("not.a.path",))))
        self.assertTrue(bad(mech(rationale="")))
        self.assertTrue(bad(mech(), mech_affordable=False))
        self.assertTrue(bad(mech(), used_mech_ids={"good1"}))
        self.assertTrue(bad(mech("opt_body")))
        self.assertTrue(self.inv(inv([hyp()], mechs=[mech("a"), mech("b", terms=["v"]), mech("c", terms=["d"])]))[0])      # > 2
        self.assertTrue(self.inv(inv([hyp()], mechs=[mech("a"), mech("a", terms=["v"])]))[0])                          # same id twice
        self.assertTrue(self.inv(inv([hyp()], mechs=[mech("a"), mech("b")]))[0])                                       # same structure
        self.assertTrue(self.inv(inv([hyp()], probes=[{"probe_id": "opt_stride", "hypothesis": "H1", "expect": "improves"}]))[0])
        self.assertTrue(self.inv(inv([], mechs=[mech()]))[0])                                                          # no hypothesis at all
        self.assertTrue(self.inv(inv([hyp()], refuted=["H1"]))[0])                                                     # nothing to refute
        e, _ = self.inv(dict(inv([hyp()]), stop="yes"))
        self.assertTrue(e)
        self.assertEqual(self.inv(inv(stop=True))[0], [])

    def test_revision_rules(self):
        rev = dict(revisable={"good1"}, used_mech_ids={"good1"}, live_ids=["H1"], refutable=["H1"])
        ok = mech("good3", revises="good1", terms=["pitch"], ev=("mechanisms.good1.improved",), rationale="gain stayed near zero")
        self.assertEqual(self.inv(inv([hyp("H2")], mechs=[ok]), **rev)[0], [])
        self.assertTrue(self.inv(inv([hyp("H2")], mechs=[mech("good3", revises="ghost", terms=["pitch"], ev=("mechanisms.good1.improved",))]), **rev)[0])
        e, _ = self.inv(inv([hyp("H2")], mechs=[mech("good3", revises="good1", terms=["pitch"], ev=("baseline.froude",))]), **rev)
        self.assertTrue(any("must cite the measured feedback" in x for x in e))                                         # revision must cite its failure
        self.assertTrue(self.inv(inv([hyp("H2")], mechs=[dict(ok, rationale=" ")]), **rev)[0])
        self.assertTrue(self.inv(inv([hyp("H2")], mechs=[ok]), **dict(rev, revisable=set()))[0])
        # a hypothesis refuted in the same reply cannot be tested in it
        e, _ = self.inv(inv([hyp("H2")], refuted=["H1"], mechs=[dict(ok, hypothesis="H1")]), **rev)
        self.assertTrue(any("does not exist or is refuted" in x for x in e))

    def test_final_reply(self):
        a = dict(paths=self.paths, live_ids=["H1"], refutable=["H1"], runs={"opt_body": [], "good1": ["good1"]}, mech_ids={"good1"})
        self.assertEqual(md.validate_final_reply(fin([fplan("good1", mechs=["good1"])]), **a), [])
        self.assertTrue(md.validate_final_reply(fin([fplan("good1", mechs=[])]), **a))                 # init carries good1
        self.assertTrue(md.validate_final_reply(fin([fplan(mechs=["ghost"])]), **a))
        self.assertTrue(md.validate_final_reply(fin([fplan(share=0.7), fplan(share=0.6)]), **a))
        self.assertTrue(md.validate_final_reply(fin([]), **a))
        self.assertTrue(md.validate_final_reply(fin([fplan(body=("leg_density",))]), **a))
        self.assertTrue(md.validate_final_reply(fin([fplan(h="H7")]), **a))
        self.assertTrue(md.validate_final_reply(fin([fplan(ev=())]), **a))
        self.assertTrue(md.validate_final_reply(fin([fplan()], refuted=["H1"]), **a))                  # refuted and pursued


class SchemaAndPrompt(Base):
    def recorded(self, fixture=None, **kw):
        d = self.make(copy.deepcopy(fixture or GOOD), **kw)
        t = Recorder(d.client.transport)
        d.client.transport = t
        rec, fake = self.go(d)
        return d, t, rec, fake

    def test_schema_enums_and_strictness(self):
        d, t, rec, _ = self.recorded()
        self.assertEqual(len(t.bodies), 3)
        for b in t.bodies:
            self.assertTrue(b["response_format"]["json_schema"]["strict"])
        s0 = t.bodies[0]["response_format"]["json_schema"]["schema"]
        props = s0["properties"]
        mi = props["mechanisms"]["items"]["properties"]
        self.assertEqual(mi["target"]["enum"], list(STUB.TARGETS))
        self.assertEqual(mi["revises"]["enum"], ["none"])                                   # nothing probed yet
        self.assertIn("baseline.froude", mi["evidence"]["items"]["enum"])
        self.assertNotIn("mechanisms.good1.delta_walking", mi["evidence"]["items"]["enum"])
        self.assertEqual(props["hypotheses"]["items"]["properties"]["id"]["enum"], ["H1", "H2", "H3"])
        self.assertEqual(props["refuted"]["items"]["enum"], ["(none open)"])
        ids = props["probes"]["items"]["properties"]["probe_id"]["enum"]
        self.assertTrue(set(ids) <= set(mpl.MECH_PROBE_IDS) and "opt_body" in ids)
        self.assertNotIn("opt_placement", ids)
        self.assertNotIn("similarity", ids)
        self.assertEqual(set(props), {"hypotheses", "refuted", "mechanisms", "probes", "stop"})
        s1 = t.bodies[1]["response_format"]["json_schema"]["schema"]
        mi1 = s1["properties"]["mechanisms"]["items"]["properties"]
        self.assertEqual(mi1["revises"]["enum"], ["none", "flat1", "good1"])
        self.assertIn("mechanisms.flat1.all_gains_near_zero", mi1["evidence"]["items"]["enum"])
        self.assertEqual(s1["properties"]["refuted"]["items"]["enum"], ["H1"])
        s2 = t.bodies[2]["response_format"]["json_schema"]["schema"]
        p2 = s2["properties"]["plans"]["items"]["properties"]
        self.assertEqual(p2["mechanisms"]["items"]["enum"], ["flat1", "good1", "good2"])
        self.assertEqual(p2["init"]["enum"], ["start", "flat1", "good1", "good2", "opt_body"])
        self.assertEqual(p2["ctrl_subspaces"]["items"]["enum"], sorted(mpl.SUBSPACES15, key=lambda x: p2["ctrl_subspaces"]["items"]["enum"].index(x)))
        self.assertNotIn("placement", p2["ctrl_subspaces"]["items"]["enum"])
        self.assertEqual(set(p2), {"init", "ctrl_subspaces", "body_params", "mechanisms", "budget_share", "hypothesis", "prediction", "evidence"})

    def test_prompt_content(self):
        s = md.build_system_prompt("iterative")
        for needle in ("80%", "24 held-out seeds", "20 s", "VERIFIED_IMPROVEMENT", "0.5 m", "sign test", "WASTED", "STARTS AT 0",
                       "never choose numeric parameter values", "stopping is not penalised", "mechanism probe", "n_diag", "gain_bound",
                       "(0, 5]", "tanh", "AGAINST the hypothesis", "revis", "rejected with a reason", "same total budget"):
            self.assertIn(needle, s)
        for sig, doc in STUB.SIGNAL_DOCS.items():
            self.assertIn(f"- {sig}: {doc}", s)
        for tgt in STUB.TARGETS:
            self.assertIn(tgt, s)
        for pid in mpl.MECH_PROBE_IDS:
            self.assertIn(f"- {pid}:", s)
        for k in gf.SUMMARY_DOCS:
            self.assertIn(f"baseline.{k}:", s)
        for leak in ("usually", "typically works", "most effective", "recommended", "best subspace"):
            self.assertNotIn(leak, s.lower())
        self.assertEqual(s, md.build_system_prompt("iterative"))
        self.assertNotEqual(s, md.build_system_prompt("one_shot"))

    def test_prompt_contains_no_banned_words(self):
        for mode in md.MODES:
            for seed in (None, 1, 2):
                self.assertEqual(md.check_prompt_neutral(md.build_system_prompt(mode, seed)), [], (mode, seed))
        # the gait-feature docs mention a capture point; the prompt must have it rewritten
        self.assertIn("capture point", " ".join(gf.SUMMARY_DOCS.values()).lower())
        self.assertNotIn("capture point", md.build_system_prompt().lower())
        # a mechanisms module with a non-neutral doc is refused at construction rather than leaking a hint
        import types
        leaky = types.SimpleNamespace(**vars(STUB))
        leaky.SIGNAL_DOCS = dict(STUB.SIGNAL_DOCS, d="use it for foot placement")
        mpl.set_mechanisms_module(leaky)
        with self.assertRaises(ValueError):
            self.make([])

    def test_order_is_shuffled_with_a_recorded_seed(self):
        a, b, c = md.build_system_prompt("iterative", 1), md.build_system_prompt("iterative", 1), md.build_system_prompt("iterative", 2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(sorted(a.splitlines()), sorted(c.splitlines()))
        d = self.make(copy.deepcopy(GOOD), order_seed=5)
        self.assertEqual(d.record()["order_seed"], 5)
        self.assertEqual(d.system, md.build_system_prompt("iterative", 5))

    def test_requests_never_contain_a_screen_seed_or_a_key(self):
        d, t, rec, _ = self.recorded()
        blob = json.dumps(t.bodies)
        for s in SEEDS["screen"]:
            self.assertNotIn(str(s), blob)
        self.assertNotIn(KEY, json.dumps(d.record()))

    def test_user_message_size_is_bounded(self):
        d, t, rec, _ = self.recorded()
        for c in d.calls:
            self.assertLess(len(c["messages"][1]["content"].encode()), 14000)

    def test_returned_decisions_carry_no_numeric_parameter_values(self):
        d = self.make(copy.deepcopy(GOOD))
        self.go(d)
        for x in d.record()["decisions"]:
            if x["kind"] == "final_plan":
                for p in x["returned"]:
                    self.assertEqual(set(p), mpl.FINAL_PLAN_KEYS | mpl.FINAL_PLAN_OPTIONAL)
            else:
                self.assertEqual(set(x["returned"]), {"mechanisms", "probes", "stop"})
                for m in x["returned"]["mechanisms"]:
                    self.assertTrue(set(m) <= {"id", "target", "leg", "terms", "gain_bound", "rationale", "revises"})


class Recorder:
    def __init__(self, inner):
        self.inner, self.bodies = inner, []

    @property
    def requests(self):
        return self.inner.requests

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(copy.deepcopy(body))
        return self.inner(url, headers, body, timeout)


class LedgerAndProvenance(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.jsonl"

    def ledger(self, **caps):
        return InferenceLedger(self.path, prices={SCRIPTED_MODEL: (1e-7, 1e-7), "nvidia/nemotron-3-super-120b-a12b": (3e-7, 9e-7)},
                               caps=Caps(**caps) if caps else None)

    def test_ledger_reservation_and_per_pipeline_investigation_id(self):
        led = self.ledger()
        d = self.make(copy.deepcopy(GOOD), ledger=led, investigation_id="i-abcdef123456", method="AI-MECH-iterative")
        self.go(d)
        rows = [json.loads(x) for x in self.path.read_text().splitlines()]
        self.assertEqual({r["investigation_id"] for r in rows}, {"i-abcdef123456"})
        self.assertEqual(len([r for r in rows if r.get("kind") == "reserve"]), 3)
        self.assertEqual(led.investigation_status("i-abcdef123456")["requests"], 3)
        self.assertEqual(d.record()["method"], "AI-MECH-iterative")
        self.assertGreater(d.record()["cost_usd"], 0)
        # a fresh director gets its own investigation id by default
        self.assertNotEqual(self.make([]).investigation_id, self.make([]).investigation_id)

    def test_call_over_the_cap_is_refused_before_sending(self):
        led = self.ledger(max_requests=2)
        d = self.make(copy.deepcopy(GOOD), ledger=led)
        t = d.client.transport
        rec, _ = self.go(d)
        self.assertEqual(t.requests, 2)
        self.assertEqual([x["status"] for x in d.record()["decisions"]], ["ok", "ok", "model_failed"])
        self.assertTrue(d.calls[2]["budget_refused"])
        self.assertEqual(rec["final_step"]["plans"], [])

    def test_investigation_cap_blocks_extra_repairs(self):
        led = self.ledger(inv_max_requests=1)
        d = self.make(copy.deepcopy(GOOD), ledger=led)
        self.go(d)
        self.assertEqual(sum(1 for c in d.calls if c["sent"]), 1)

    def test_live_gate(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CREATURE_FORGE_ENABLE_LIVE", "NEBIUS_API_KEY")}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(LiveRefused) as cm:
                md.MechDirector("iterative", source="live", ledger=self.ledger())
            self.assertIn("CREATURE_FORGE_ENABLE_LIVE", str(cm.exception))
            os.environ["CREATURE_FORGE_ENABLE_LIVE"] = "1"
            with mock.patch("creature_forge.config.load_env", return_value=False):
                with self.assertRaises(LiveRefused) as cm:
                    md.MechDirector("iterative", source="live", ledger=self.ledger())
            self.assertIn("API key", str(cm.exception))

    def test_live_record_has_no_key_and_injected_transport_is_not_live(self):
        class Leaky:
            n = 0

            def __init__(self):
                self.inner = dr.FixtureTransport(copy.deepcopy(GOOD))

            def __call__(self, url, headers, body, timeout):
                Leaky.n += 1
                assert headers["Authorization"] == f"Bearer {KEY}"
                if Leaky.n == 2:
                    raise NebiusError(f"HTTP 401: invalid key {KEY}")
                return self.inner(url, headers, body, timeout)
        with mock.patch.dict(os.environ, {"CREATURE_FORGE_ENABLE_LIVE": "1", "NEBIUS_API_KEY": KEY}), \
                mock.patch("creature_forge.config.load_env", return_value=False):
            d = md.MechDirector("iterative", source="live", ledger=self.ledger(), transport=Leaky())
            self.go(d)
            rec = d.record()
        text = json.dumps(rec)
        self.assertNotIn(KEY, text)
        self.assertNotIn("Bearer", text)
        self.assertEqual(rec["model"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(rec["provenance"], "SCRIPTED_MOCK")
        self.assertEqual(rec["decisions"][1]["status"], "model_failed")
        self.assertIn("[redacted]", rec["decisions"][1]["validation_errors"][0])

    def test_scripted_is_never_live_and_modes_are_checked(self):
        d = self.make([])
        self.assertEqual(d.record()["provenance"], "SCRIPTED_MOCK")
        with self.assertRaises(ValueError):
            md.MechDirector("iterative", source="scripted")          # no fixture
        with self.assertRaises(ValueError):
            md.MechDirector("sideways", fixture=[])

    def test_record_is_json_safe_and_complete(self):
        d = self.make(copy.deepcopy(GOOD))
        self.go(d)
        rec = d.record()
        json.dumps(rec)
        for k in ("provenance", "model", "settings", "calls", "decisions", "refuted_by_round", "cost_usd", "tokens", "mech_meta", "method",
                  "mech_mode", "system_prompt", "order_seed", "investigation_id"):
            self.assertIn(k, rec)
        self.assertEqual(rec["version"], md.VERSION)
        self.assertEqual(set(rec["mech_meta"]), {"good1", "flat1", "good2"})
        self.assertEqual(rec["mech_meta"]["good2"]["revises"], "flat1")
        self.assertGreater(rec["tokens"]["prompt"], 0)

    def test_determinism(self):
        a, b = self.make(copy.deepcopy(GOOD), order_seed=4), self.make(copy.deepcopy(GOOD), order_seed=4)
        ra, _ = self.go(a)
        rb, _ = self.go(b)
        for r in (ra, rb):
            r.pop("wall_s")
            r.pop("director")
        self.assertEqual(ra, rb)
        self.assertEqual([c["prompt_sha256"] for c in a.calls], [c["prompt_sha256"] for c in b.calls])


if __name__ == "__main__":
    unittest.main()
