"""Autonomous Hypothesis-as-Simulation scientist (phase 3, Stage 2): Nemotron directs the investigation, and the deterministic
instruments do the numerics.

Roles (owner's vision, 2026-10-19): Nemotron is the scientist. MuJoCo (plant and twin), the Bayesian belief engine
(`belief_engine.Episode`), expected-information-gain estimates, CMA-ES and the calibrated verification map are its
instruments. Every turn Nemotron reads a lab notebook and calls ONE tool. The notebook holds:
- the measurements;
- the engine's posterior over executable explanations;
- a model check (where the leading explanation fails to reproduce the data);
- the candidate experiments with their EIG and the predictions of the top explanations;
- the repairs so far with their plant evidence and calibrated P(pass);
- the engine's own recommendation;
- relevant dossiers from memory, with deterministic applicability checks.

Nemotron may delegate any phase to the engine. The engine's recommendations are exactly what the engine-only arm (A1c5) would
do, so an agent that always delegates reproduces A1c5's tool calls: attribution compares Nemotron's non-delegated decisions
against that baseline. A failed or invalid model reply falls back to the engine's recommendation (recorded, never hidden).

Tools (all charged to the bench's plant or twin ledger; refusals cost nothing and are recorded):
  experiment      run a plant experiment: an engine candidate, or one Nemotron designs (a design counterfactual
                  `cf:<param>@<level>[&<param>@<level>]`, a floor test `floor_test@x<m>`, `weigh_test`), with a registered prediction
  propose         add executable hypotheses (1-2 DSL primitives each) to the belief (may accompany any action)
  delegate_diagnosis  the engine runs its own EIG experiment loop until its stopping rule holds
  screen_tools    the engine ranks repair tools on the twin under the current belief
  repair          one repair attempt on a tool: `twin` (ensemble-robust twin CMA against the belief, then a plant check) or
                  `plant` (CMA on the plant from a chosen design); optional physically reasoned start edits
  check           robustness check (8 or 16 fresh seeds; plus the 20 s stress test when it qualifies) -> calibrated P(pass)
  assimilate      fold a repaired design's plant check into the belief (a failed repair is evidence about the mechanism)
  apply_dossier / use_learned   add hypotheses from memory or from the learned amortised posterior
  delegate_repair the engine's posterior-robust repair with the remaining budget, then submit (ends the investigation)
  conclude        submit a design for independent verification (ends the investigation)
"""
from __future__ import annotations

import copy
import json
import math

from . import belief_engine as be
from . import scientist_has as sh
from .hdb_workbench import min_budget

VERSION = "has_agent_v3"   # v3: experiment/prediction/hypotheses are required schema fields (optional ones were dropped
                           # under constrained decoding); a missing prediction is recorded, it no longer voids the action
                           # v2 (after pilot 1): delegate_repair takes the scientist's tool order and start edits; accurate
                           # tool costs in the prompt; a failed reply never triggers a terminal fallback
MAX_TURNS = 14
ACTIONS = ("experiment", "propose", "delegate_diagnosis", "screen_tools", "repair", "check", "assimilate", "apply_dossier",
           "use_learned", "delegate_repair", "conclude")
PRED_QUANTITIES = ("n_walking", "time_upright", "pitch_mean")
TWIN_REPAIR_BUDGET = 800


def _r(x, nd=3):
    return None if x is None else round(float(x), nd)


class LabSession:
    """The instruments of one investigation and their trace. Deterministic given the bench, the proposals and the actions."""

    def __init__(self, bench, ep: be.Episode, *, stop_model: dict | None, tau: float = 0.75, memory=None, learned=None,
                 max_experiments: int = 6, confident: float = 0.9):
        self.b, self.ep = bench, ep
        self.stop_model, self.tau = stop_model, tau
        self.needs_stress = bool(stop_model) and "stress4" in stop_model.get("features", [])
        self.memory, self.learned = memory, learned
        self.max_experiments, self.confident = max_experiments, confident
        self.phase = "diagnosis"
        self.n_experiments = 0                      # plant experiments after the first observation
        self.trace: list[dict] = []
        self.evidence: dict[int, dict] = {}         # design index -> plant evidence
        self.tool_ranking: list[dict] | None = None
        self._ranking = None
        self.done, self.conclusion = False, None
        self.notes: list[dict] = []
        self.last_feedback: list[str] = []          # results of the last action, shown on the next turn
        self.predictions: list[dict] = []
        self.dossiers_shown: list[dict] = []
        self.memory_views: list[dict] = []

    # ------------------------------------------------------------------ helpers
    def _usage(self) -> dict:
        return {"plant_used": self.b.budget.used, "twin_used": self.b.twin.used}

    def _log(self, actor: str, action: dict, result: dict, before: dict, turn: int | None = None) -> None:
        after = self._usage()
        self.trace.append({"seq": len(self.trace), "turn": turn, "actor": actor, "action": copy.deepcopy(action), "result": result,
                           "plant_cost": after["plant_used"] - before["plant_used"],
                           "twin_cost": after["twin_used"] - before["twin_used"], **after})

    def ranking(self) -> list[tuple]:
        if self._ranking is None:
            self._ranking = self.ep.rank_experiments()
        return self._ranking

    def _changed(self) -> None:
        self._ranking = None

    def hyps(self, against: str = "belief") -> list:
        post = self.ep.posterior()
        if against == "leading":
            return post[:1]
        out, mass = [], 0.0
        for p, w in post:
            out.append((p, w))
            mass += w
            if mass >= 0.8 or len(out) >= 3:
                break
        return out

    def p_full(self, ev: dict) -> float | None:
        if not self.stop_model:
            return None
        try:
            return be.mapped_p_full(self.stop_model, ev)
        except (KeyError, ValueError):
            return None

    # ------------------------------------------------------------------ engine policy (identical to arm A1c5)
    def recommend(self) -> dict:
        if self.phase == "diagnosis" and self.n_experiments < self.max_experiments and not self.ep.diagnosis_done(self.confident):
            scored = self.ranking()
            if scored:
                return {"action": "experiment", "experiment": scored[0][2]["id"],
                        "why": "engine: highest expected information gain per plant rollout"}
        return {"action": "delegate_repair", "why": "engine: diagnosis stopping rule reached; posterior-robust repair"}

    # ------------------------------------------------------------------ tools
    def begin(self) -> None:
        before = self._usage()
        self.ep.start()
        self._log("engine", {"action": "observe"}, {"posterior": self.top_structures()}, before)

    def design_weigh(self) -> dict:
        """Static mass and centre of mass of the nominal DESIGN (known to the scientist; no plant cost)."""
        if not hasattr(self, "_design_weigh"):
            from .hdb_workbench import static_mass_com
            self._design_weigh = static_mass_com(None, self.ep.design0["body"], design_only=True)
        return self._design_weigh

    def top_structures(self, k: int = 4) -> list:
        return [[[list(x) for x in s], round(w, 4)] for s, w in self.ep.structure_posterior()[:k]]

    def _candidate(self, spec: str) -> tuple[dict | None, str | None]:
        from .eng_tools import parse_counterfactual
        from .fault_bench import apply_changes
        cands = {c["id"]: c for c in self.ep.candidate_experiments()}
        done = {e["id"].split(":", 1)[1] for e in self.ep.experiments if ":" in e["id"]}
        if spec in done:
            return None, f"{spec} was already run (same seeds, nothing new to learn)"
        if spec in cands:
            return cands[spec], None
        d = self.b.best_design()
        base = {"body": d["body"], "vector": d["vector"]}
        if spec.startswith("floor_test@x"):
            try:
                m = float(spec[len("floor_test@x"):])
            except ValueError:
                return None, f"bad floor test {spec!r}"
            if not 0.2 <= m <= 5.0:
                return None, "floor friction multiplier must be in [0.2, 5]"
            return {"id": f"floor_test@x{m:g}", "kind": "floor", "design": base, "friction_mult": m, "cost": self.b.n_obs}, None
        if spec.startswith("cf:"):
            cid = spec[3:]
            try:
                body, vec = apply_changes(base["body"], base["vector"], parse_counterfactual(cid))
            except Exception as exc:   # noqa: BLE001 - reported to the scientist, nothing is clipped
                return None, f"counterfactual {cid!r} rejected: {exc}"
            return {"id": spec, "kind": "counterfactual", "cf": cid, "design": {"body": body, "vector": vec},
                    "cost": self.b.n_obs}, None
        return None, f"unknown experiment {spec!r}"

    def experiment(self, spec: str, *, by: str, prediction=None) -> dict:
        cand, err = self._candidate(spec)
        if cand is None:
            return {"ok": False, "refused": err}
        if self.b.remaining < cand["cost"]:
            return {"ok": False, "refused": f"needs {cand['cost']} plant rollouts, {self.b.remaining} remain"}
        scored = self.ranking()
        listed = {c["id"]: (r, g) for r, g, c in scored}
        eig = listed.get(cand["id"], (None, None))[1]
        if eig is None:
            eig = self.ep.eig(cand, self.ep.posterior()[:self.ep.eig_top])
        best = scored[0][1] if scored else None
        if prediction:
            self.predictions.append({"experiment": cand["id"], "registered_before_run": True, "predictions": prediction})
        res = self.ep.experiment_step(cand, by=by, scored=scored)
        self.n_experiments += 1
        self._changed()
        if not res.get("ok", True):
            return {"ok": False, "refused": res.get("refused")}
        exp = self.ep.experiments[-1]
        out = {"ok": True, "id": exp["id"], "eig": _r(eig), "best_eig": _r(best), "posterior": self.top_structures()}
        if prediction:
            out["measured"] = measured_panel(exp)
        return out

    def propose(self, devs: list, source: str = "nemotron") -> dict:
        added = self.ep.add_particles(devs, source)
        self.ep.fit_structures(added)
        self.ep.refine()
        self.ep.prune()
        self._changed()
        post = {p.pid: (w, i) for i, (p, w) in enumerate(self.ep.posterior())}
        best_ll = max((p.loglik for p in self.ep.particles.values()), default=0.0)
        report = []
        for pid in added:
            st = pid_structure(pid)
            fam = [(q, post[q.pid]) for q in self.ep.particles.values() if q.pid in post and q.structure == st]
            if fam:
                q, (w, rank) = max(fam, key=lambda t: t[0].loglik)
                report.append({"pid": pid, "fitted": q.pid, "weight": _r(w, 4), "rank": rank + 1,
                               "loglik_gap": _r(q.loglik - best_ll, 2)})
            else:
                report.append({"pid": pid, "weight": 0.0, "rank": None, "status": "pruned: far worse than the leaders even "
                                                                                  "after fitting its magnitude"})
        return {"ok": True, "added": report, "not_new": len(devs) - len(added), "posterior": self.top_structures()}

    def delegate_diagnosis(self) -> dict:
        ran = []
        while self.n_experiments < self.max_experiments and not self.ep.diagnosis_done(self.confident):
            scored = self.ranking()
            if not scored:
                break
            self.ep.experiment_step(scored[0][2], by="eig", scored=scored)
            self.n_experiments += 1
            self._changed()
            ran.append(scored[0][2]["id"])
        return {"ok": True, "ran": ran, "posterior": self.top_structures()}

    def screen_tools(self) -> dict:
        hyps = self.hyps("belief")
        ranking = self.ep.screen_tools(hyps)
        ranking = self.ep.screen_tools_cma(hyps, ranking)
        self.tool_ranking = ranking
        return {"ok": True, "ranking": [{k: r.get(k) for k in ("tool", "probe", "score", "cma_walking")} for r in ranking[:6]]}

    def _evaluate(self, idx: int, *, first_n: int, twin_pred: float | None = None) -> dict:
        ev = self.evidence.setdefault(idx, {"twin_pred": twin_pred})
        w = self._check(idx, first_n)
        if w is None:
            return ev
        if first_n == 8 and w >= 7 and self.b.remaining >= 16:
            self._check(idx, 16)
        if self.needs_stress and (ev.get("robust16") or 0) >= 14 and ev.get("stress4") is None and self.b.remaining >= 2 * self.b.n_obs:
            self.b.select(idx)
            t = self.b.stress_test()
            if t.get("ok"):
                ev["stress4"] = int(t["observation"]["n_walking"])
        ev["p_full"] = self.p_full({"robust16": ev.get("robust16"), "stress4": ev.get("stress4")})
        return ev

    def _check(self, idx: int, n: int) -> int | None:
        if self.b.remaining < n:
            return None
        self.b.select(idx)
        c = self.b.robustness_check(n)
        if not c.get("ok"):
            return None
        ev = self.evidence.setdefault(idx, {})
        ev[f"robust{n}"] = int(c["walking"])
        ev.setdefault("checks", {})[str(n)] = list(c["labels"])
        if ev.get("twin_pred") is not None and ev["twin_pred"] >= 0.75 and c["walking"] / n <= 0.5:
            ev["contradiction"] = (f"the belief predicted this design walks ({ev['twin_pred']:.0%} of twin trials); the real robot "
                                   f"walked on {c['walking']}/{n}")
        return int(c["walking"])

    def repair(self, *, tool: str, mode: str, against: str = "belief", start_edits: str | None = None,
               plant_share: float = 0.6, n_train: int = 4, from_design: int | None = None) -> dict:
        from .eng_tools import parse_counterfactual
        from .fault_bench import apply_changes
        self.phase = "repair"
        if from_design is not None and not 0 <= int(from_design) < len(self.b.designs):
            return {"ok": False, "refused": f"no design {from_design}"}
        start_idx = self.b.best_design()["index"] if from_design is None else int(from_design)
        start = self.b.designs[start_idx]
        if start_edits:
            try:
                body, vec = apply_changes(start["body"], start["vector"], parse_counterfactual(start_edits))
            except Exception as exc:   # noqa: BLE001
                return {"ok": False, "refused": f"start edits {start_edits!r} rejected: {exc}"}
            start_idx = self.b.add_twin_design(body, vec, source=f"edit:{start_edits}", parent=start_idx)
            start = self.b.designs[start_idx]
        if mode == "twin":
            hyps = self.hyps(against)
            budget = min(TWIN_REPAIR_BUDGET, self.b.twin.remaining)
            if budget < min_budget(tool, 8):
                return {"ok": False, "refused": f"twin budget left {self.b.twin.remaining} is below the minimum for {tool}"}
            res = self.b.twin_cma(hyps[0][0].deviation, {"body": start["body"], "vector": start["vector"]}, tool, budget,
                                  role="twin", n_train=8, noise_seed=len(self.b.designs), tag=f"agent:{tool}",
                                  ensemble=self.ep.ensemble(hyps))
            if res is None:
                return {"ok": False, "refused": "twin optimisation refused (budget)"}
            best = res["best"]
            idx = self.b.add_twin_design(best["body"], best["vector"], source=f"cma:{tool}", parent=start_idx, tool=tool,
                                         twin_walking=int(best["walking_count"]))
            ev = self._evaluate(idx, first_n=8, twin_pred=int(best["walking_count"]) / 8)
            return {"ok": True, "design": idx, "mode": mode, "tool": tool, "twin_walking": f"{int(best['walking_count'])}/8",
                    "evidence": _ev_view(ev)}
        if mode == "plant":
            avail = self.b.remaining - 16
            budget = int(max(0.0, min(1.0, float(plant_share))) * avail)
            need = min_budget(tool, n_train)
            if budget < need:
                return {"ok": False, "refused": f"plant budget {budget} below the minimum {need} for {tool} (n_train {n_train})"}
            rep = self.b.repair(tool, budget, n_train=n_train, init={"index": start_idx})
            if not rep.get("ok"):
                return {"ok": False, "refused": rep.get("refused")}
            idx = rep["design_index"]
            ev = self._evaluate(idx, first_n=16)
            ev["train"] = f"{rep['best']['train_walking']}/{n_train}"
            return {"ok": True, "design": idx, "mode": mode, "tool": tool, "plant_rollouts": rep["rollouts_used"],
                    "evidence": _ev_view(ev)}
        return {"ok": False, "refused": f"unknown mode {mode!r}"}

    def check(self, design: int, n: int = 16) -> dict:
        if not 0 <= int(design) < len(self.b.designs):
            return {"ok": False, "refused": f"no design {design}"}
        ev = self._evaluate(int(design), first_n=int(n), twin_pred=(self.evidence.get(int(design)) or {}).get("twin_pred"))
        return {"ok": True, "design": int(design), "evidence": _ev_view(ev)}

    def assimilate(self, design: int) -> dict:
        ev = self.evidence.get(int(design)) or {}
        checks = ev.get("checks") or {}
        if not checks:
            return {"ok": False, "refused": f"design {design} has no plant check to learn from"}
        n = max(int(k) for k in checks)
        d = self.b.designs[int(design)]
        out = self.ep.assimilate_check(d, {"design_index": int(design), "labels": checks[str(n)]},
                                       seeds=self.b.view_seeds["robust"][:n])
        self._changed()
        return {"ok": True, **out}

    def apply_dossier(self, did: str) -> dict:
        if self.memory is None:
            return {"ok": False, "refused": "no memory in this arm"}
        devs = self.memory.particles(did, self.ep.design_mass)
        if devs is None:
            return {"ok": False, "refused": f"unknown dossier {did!r}"}
        out = self.propose(devs, source=f"dossier:{did}")
        self.memory.note_use(did, self)
        return out

    def use_learned(self) -> dict:
        if self.learned is None:
            return {"ok": False, "refused": "no learned posterior in this arm"}
        sugg = self.learned.suggest(self.ep)
        return {**self.propose([d for d, _ in sugg], source="learned"), "suggested": [[be._pid(d), _r(p)] for d, p in sugg]}

    def delegate_repair(self, tool_order: list[str] | None = None, start_edits: str | None = None,
                        from_design: int | None = None) -> dict:
        """The engine's posterior-robust repair procedure with the remaining budgets, then it submits. The scientist may set
        the tools to try first (`tool_order`) and a physically reasoned start design (`start_edits` applied to `from_design`
        or the current design); the engine then runs its numerics unchanged."""
        from .eng_tools import parse_counterfactual
        from .fault_bench import apply_changes
        self.phase = "repair"
        if from_design is not None:
            self.b.select(int(from_design))
        if start_edits:
            d = self.b.best_design()
            try:
                body, vec = apply_changes(d["body"], d["vector"], parse_counterfactual(start_edits))
            except Exception as exc:   # noqa: BLE001
                return {"ok": False, "refused": f"start edits {start_edits!r} rejected: {exc}"}
            self.b.select(self.b.add_twin_design(body, vec, source=f"edit:{start_edits}", parent=d["index"]))
        accept = be.calibrated_accept(self.stop_model, self.tau) if self.stop_model else None
        rep = self.ep.robust_repair(twin_budget=TWIN_REPAIR_BUDGET, plant_budget=300, accept_fn=accept,
                                    prefer=list(tool_order) if tool_order else None)
        self.done = True
        self.conclusion = {"design": self.b.best_design()["index"], "by": "engine_repair", "repair": rep}
        return {"ok": True, "accepted": rep.get("accepted"), "design": self.conclusion["design"]}

    def conclude(self, design: int, by: str = "nemotron") -> dict:
        if not 0 <= int(design) < len(self.b.designs):
            return {"ok": False, "refused": f"no design {design}"}
        self.b.select(int(design))
        self.done = True
        self.conclusion = {"design": int(design), "by": by}
        return {"ok": True, "design": int(design)}

    def force_conclude(self, why: str) -> dict:
        """Out of turns or budget: submit the design with the best plant robustness evidence (the engine's rule)."""
        scored = [(ev.get("robust16", -1) / 16 if ev.get("robust16") is not None else (ev.get("robust8", -1) / 8),
                   16 if ev.get("robust16") is not None else 8, i) for i, ev in self.evidence.items()
                  if ev.get("robust16") is not None or ev.get("robust8") is not None]
        idx = max(scored)[2] if scored else self.b.best_design()["index"]
        return self.conclude(idx, by=f"forced:{why}")

    # ------------------------------------------------------------------ dispatch
    def execute(self, act: dict, actor: str, turn: int | None = None) -> dict:
        before = self._usage()
        a = act["action"]
        res: dict = {}
        if act.get("hypotheses_devs"):
            res["proposals"] = self.propose(act["hypotheses_devs"], source="nemotron" if actor == "nemotron" else actor)
        if a == "experiment":
            res.update(self.experiment(act["experiment"], by=actor, prediction=act.get("prediction")))
        elif a == "propose":
            res.setdefault("proposals", {"ok": True, "added": []})
        elif a == "delegate_diagnosis":
            res.update(self.delegate_diagnosis())
        elif a == "screen_tools":
            res.update(self.screen_tools())
        elif a == "repair":
            res.update(self.repair(tool=act["tool"], mode=act.get("mode", "twin"), against=act.get("design_against", "belief"),
                                   start_edits=act.get("start_edits") or None, plant_share=act.get("plant_share", 0.6),
                                   n_train=act.get("n_train", 4), from_design=act.get("design")))
        elif a == "check":
            res.update(self.check(act["design"], act.get("n", 16)))
        elif a == "assimilate":
            res.update(self.assimilate(act["design"]))
        elif a == "apply_dossier":
            res.update(self.apply_dossier(act["dossier"]))
        elif a == "use_learned":
            res.update(self.use_learned())
        elif a == "delegate_repair":
            res.update(self.delegate_repair(act.get("tool_order"), act.get("start_edits") or None, act.get("design")))
        elif a == "conclude":
            res.update(self.conclude(act["design"]))
        self._log(actor, {k: v for k, v in act.items() if k != "hypotheses_devs"}, res, before, turn)
        self.last_feedback = feedback_lines(a, res)
        return res

    def record(self) -> dict:
        return {"version": VERSION, "trace": self.trace, "evidence": {str(k): v for k, v in self.evidence.items()},
                "conclusion": self.conclusion, "notes": self.notes, "predictions": self.predictions,
                "memory_views": self.memory_views, "memory_uses": self.memory.uses if self.memory is not None else None,
                "n_experiments": self.n_experiments,
                "tool_ranking": self.tool_ranking}


def pid_structure(pid: str) -> tuple:
    """Structure (sorted (kind, target) pairs) of a particle id such as 'payload:torso(mass_kg=1,x_m=0.1)+sensor_bias:pitch(rad=0.1)'."""
    if pid == "nominal":
        return ()
    return tuple(sorted(tuple(part.split("(", 1)[0].split(":", 1)) for part in pid.split("+")))


def _ev_view(ev: dict) -> dict:
    out = {k: ev[k] for k in ("twin_pred", "robust8", "robust16", "stress4", "p_full", "train", "contradiction")
           if ev.get(k) is not None}
    if ev.get("p_full") is None and ev.get("robust16") is not None and ev["robust16"] < 14:
        out["p_full"] = "low (robust16 < 14; dev rate of passing at 15/16 is about 1 in 3)"
    if isinstance(out.get("p_full"), float):
        out["p_full"] = round(out["p_full"], 3)
    return out


def measured_panel(exp: dict) -> dict:
    if exp["kind"] == "weigh":
        return dict(exp["measured"])
    f = exp.get("features") or {}
    walk = sum(1 for x in f.values() if x.get("walking"))
    med = {k: sh._median([x.get(k) for x in f.values()]) for k in ("time_upright", "pitch_mean")}
    return {"n_walking": walk, **med}


def feedback_lines(action: str, res: dict) -> list[str]:
    out = []
    pr = res.get("proposals")
    if pr and pr.get("added"):
        for h in pr["added"]:
            if h.get("rank"):
                out.append(f"your hypothesis {h['pid']}: after fitting its magnitude to the data ({h.get('fitted')}) weight "
                           f"{h['weight']:.3f}, rank {h['rank']}, log-likelihood {h['loglik_gap']:+.1f} vs the best")
            else:
                out.append(f"your hypothesis {h['pid']}: {h.get('status')}")
    if not res.get("ok", True) and res.get("refused"):
        out.append(f"{action} REFUSED: {res['refused']}")
    if action == "experiment" and res.get("ok"):
        out.append(f"ran {res['id']} (engine EIG {res.get('eig')}, best available {res.get('best_eig')})")
        if res.get("measured"):
            out.append(f"measured: {json.dumps({k: _r(v) for k, v in res['measured'].items()})}")
    if action == "delegate_diagnosis" and res.get("ok"):
        out.append(f"engine ran {res['ran'] or 'no experiments (its stopping rule already holds)'}")
    if action == "repair" and res.get("ok"):
        out.append(f"repair -> design {res['design']} ({res['mode']}, {res['tool']}): {json.dumps(res['evidence'])}")
    if action == "check" and res.get("ok"):
        out.append(f"check of design {res['design']}: {json.dumps(res['evidence'])}")
    if action == "assimilate" and res.get("ok"):
        out.append(f"belief before {res['before']} -> after {res['after']}")
    if action in ("apply_dossier", "use_learned") and res.get("ok") and res.get("suggested"):
        out.append(f"learned posterior suggested {res['suggested']}")
    return out


# ---------------------------------------------------------------------------------------------------------------- notebook
def notebook(s: LabSession, turn: int, max_turns: int) -> list[str]:
    ep, b = s.ep, s.b
    L = [f"TURN {turn + 1} of {max_turns} | plant budget used {b.budget.used} of {b.budget.total} (left {b.remaining}) | "
         f"simulation budget used {b.twin.used} of {b.twin.total} (left {b.twin.remaining})"]
    if max_turns - turn <= 2:
        L.append("ONLY A FEW TURNS LEFT: submit a design (conclude) or delegate the repair, or the design with the best plant "
                 "evidence is submitted for you.")
    st = ep.state()
    L += ["", "MEASUREMENTS ON THE REAL ROBOT:",
          *["  " + x for x in sh.experiment_lines({"experiments": [e for e in st["experiments"] if e["kind"] != "check"]})]]
    if any(e["kind"] == "weigh" for e in ep.experiments):
        dm = s.design_weigh()
        L.append(f"  (for comparison, the DESIGN itself: total mass {dm['mass_kg']:.3f} kg, centre of mass "
                 f"{dm['com_x_m'] * 100:+.1f} cm forward of the hip; the scale's noise is about 1 % in mass and 0.5 cm)")
    checks = [e for e in ep.experiments if e["kind"] == "check"]
    for e in checks:
        L.append(f"  {e['id']}: robustness check folded into the belief (walking {sum(1 for f in e['features'].values() if f['walking'])}"
                 f"/{len(e['features'])})")
    post = ep.posterior()
    L += ["", "BELIEF (engine posterior; weight, explanation = design + deviation, proposed by):"]
    for p, w in post[:6]:
        L.append(f"  {w:.3f}  {p.pid}  [{p.source}]")
    sp = ep.structure_posterior()
    ent = -sum(w * math.log(w) for _, w in sp if w > 0)
    L.append(f"  explanation types: " + "; ".join(f"{'+'.join(f'{k}:{t}' for k, t in st) or 'nominal'} {w:.2f}" for st, w in sp[:5])
             + f" (entropy {ent:.2f} nats)")
    res = st.get("residuals_of_map") or {}
    if res:
        L += ["", "MODEL CHECK (measured minus predicted by the leading explanation, in noise units; |r| > 2 is unexplained):"]
        for eid, r in res.items():
            big = {k: v for k, v in r.items() if abs(v) > 1.0}
            flag = " UNEXPLAINED" if any(abs(v) > 2.0 for v in big.values()) else ""
            L.append(f"  {eid}: " + (", ".join(f"{k} {v:+.1f}" for k, v in big.items()) or "fits") + flag)
    if s.phase == "diagnosis" or not s.evidence:
        scored = s.ranking()
        tops = [p for p, _ in post[:3]]
        L += ["", "CANDIDATE EXPERIMENTS (engine EIG in nats; predicted walking out of 2 trials under explanations H1/H2/H3 = the top "
                  "three above; you may also design your own: cf:<param>@<level>[&<param>@<level>], floor_test@x<m>):"]
        for r, g, c in scored[:7]:
            preds = []
            for p in tops:
                pr = p.seen.get(f"eig:{c['id']}#2") if c["kind"] != "weigh" else p.seen.get(f"eig:{c['id']}")
                if pr is None:
                    preds.append("?")
                elif c["kind"] == "weigh":
                    preds.append(f"{pr['mass_kg']:.2f}kg/{pr['com_x_m'] * 100:+.1f}cm")
                else:
                    preds.append(str(sum(1 for f in pr.values() if f.get("walking"))))
            L.append(f"  {c['id']}: cost {c['cost']}, EIG {g:.2f}, H1/H2/H3 predict {'/'.join(preds)}")
    L += ["", "REPAIR TOOL MINIMUM PLANT BUDGETS (plant-mode CMA, n_train 4 / 8): " + ", ".join(
        f"{t} {min_budget(t, 4)}/{min_budget(t, 8)}" for t in sh.TOOLS)]
    if s.tool_ranking:
        L += ["", "TOOL SCREEN (twin, under the belief; cma_walking = walking trials of 4 after a short twin optimisation):"]
        L += [f"  {r['tool']}: probe score {r['score']:.2f}, cma_walking {r.get('cma_walking')}" for r in s.tool_ranking[:6]]
    if s.evidence:
        L += ["", "DESIGNS WITH PLANT EVIDENCE (P(pass) = dev-calibrated probability of passing the independent verification; "
                  f"the engine's rule submits at P(pass) >= {s.tau}):"]
        for i, ev in sorted(s.evidence.items()):
            d = b.designs[i]
            L.append(f"  design {i} ({d['source']}): {json.dumps(_ev_view(ev))}")
    if s.memory is not None:
        s.dossiers_shown = s.memory.view(s)
        s.memory_views.append({"turn": turn, "shown": [(d["id"], d["score"]) for d in s.dossiers_shown]})
    if s.dossiers_shown:
        L += ["", "MEMORY (dossiers from earlier investigations; applicability re-checked against this robot's data every turn):"]
        for d in s.dossiers_shown:
            L.append(f"  {d['id']}: {d['line']}")
    if s.learned is not None:
        L += ["", "LEARNED POSTERIOR available (use_learned adds its suggestions as hypotheses)."]
    if s.last_feedback:
        L += ["", "RESULT OF YOUR LAST ACTION:", *["  " + x for x in s.last_feedback]]
    if s.notes:
        L += ["", "YOUR EARLIER NOTES:", *[f"  turn {n['turn'] + 1}: {n['understanding'][:300]}" for n in s.notes[-3:]]]
    rec = s.recommend()
    L += ["", f"ENGINE RECOMMENDATION (what the engine alone would do now): {rec['action']}"
              + (f" {rec['experiment']}" if rec.get("experiment") else "")]
    return L


# ---------------------------------------------------------------------------------------------------------------- Nemotron
AGENT_SYSTEM = f"""You are the lead scientist of a physics laboratory that investigates and repairs a failing two-legged walking robot.

The robot was built from a nominal DESIGN (body and a 17-parameter walking controller) that walked reliably. The real robot now
fails. Something about it differs from its design (damage, wear, mis-calibration, environment); nobody knows what. You never see
the real robot's parameters, only measurements of how it behaves.

You direct the investigation. Your instruments do the numerics, and you should use them:
- The REAL ROBOT runs the experiments you order (each costs plant rollouts from a fixed budget).
- A BELIEF ENGINE keeps a Bayesian posterior over executable explanations. Each explanation is the design plus a deviation; the
  engine simulates it on exactly the same test seeds and compares with the measurements. You add explanations by proposing
  hypotheses; data decide their weight, not you.
- The engine estimates the expected information gain (EIG) of experiments and the predictions of each leading explanation.
- An OPTIMISER (CMA-ES) searches a repair tool's parameters: on the simulator against the belief (`twin` mode, costs no plant
  rollouts until checked), or on the real robot (`plant` mode, costs plant rollouts).
- ROBUSTNESS CHECKS on fresh trials give a dev-calibrated probability that a design passes the independent verification (walking on
  >= 80 % of 24 fresh 10 s trials and of 24 fresh 20 s trials, clearly better than the failing robot). You do not see the
  verification itself.

A good scientist: identifies what is not yet understood; writes competing physical explanations (including two-cause
combinations and unusual targets when the residuals call for them); chooses experiments that discriminate between them; notices
when the data contradict the leading explanation (UNEXPLAINED residuals, a repair that fails although the belief predicted
success) and revises; picks a repair whose mechanism addresses the cause; delegates to the engine when its default is the
better choice; and stops when the evidence is strong enough or the budget is better kept.

Deviation language for hypotheses (1 or 2 primitives; real robot = design + deviation):
{sh._dsl_doc()}

Design counterfactual levels: scale parameters take x0.33, x0.5, x0.7, x0.85, x1.2, x1.5, x2, x3; additive parameters
(duty, knee_shift, stance_knee, hip_bias, pitch_ref, sync_gain, start_lean, fp_kd, fp_kv) take -0.2R, -0.1R, -0.05R, +0.05R,
+0.1R, +0.2R (fractions of their range). Body parameters: torso_mass, foot_length, torque_limit, foot_friction, leg_length,
leg_density. Controller parameters: freq, duty, hip_amp, knee_amp, knee_shift, stance_knee, hip_bias, kp, kd, balance_gain,
pitch_kp, pitch_ref, sync_gain, ramp_s, start_lean, fp_kd, fp_kv.
Repair tools (the optimiser changes only that subsystem): posture (hip_bias, pitch_ref, stance_knee, start_lean), timing (freq,
duty, knee_shift), feedback (kp, kd, balance_gain, pitch_kp, sync_gain), stride (hip_amp, knee_amp, ramp_s), placement (fp_kd,
fp_kv), foot_length, torso_mass, torque_limit, foot_friction, leg_length.

ACTIONS (exactly one per turn; `hypotheses` may accompany any action):
- experiment: field `experiment` = a candidate id or your own design (cf:<param>@<level>[&<param>@<level>], floor_test@x<m> with
  m in [0.2, 5], weigh_test). Field `prediction` = your 5/25/50/75/95 % quantiles for n_walking (of 4), time_upright (s) and
  pitch_mean (rad) BEFORE it runs.
- propose: only add `hypotheses`.
- delegate_diagnosis: the engine runs its own highest-EIG experiments (4 plant rollouts each) until a single explanation
  type holds 90 % of the posterior or 120 plant rollouts have been used in total; it runs nothing if that already holds.
- screen_tools: the engine ranks the repair tools on the simulator under the belief (about 900 simulations, no plant cost).
- repair (one trial repair you direct): fields `tool`, `mode`, optional `design_against` (belief | leading), `start_edits`
  (a counterfactual string applied to the start design first, e.g. balance_gain@x2&pitch_kp@x2), `design` (start design).
  * mode twin: CMA-ES on the simulator against the belief (800 simulations), then a plant check (8, then 16 fresh trials
    and a 20 s stress test if it qualifies): about 8-32 plant rollouts.
  * mode plant: CMA-ES on the real robot with `plant_share` (0.1-1) of the remaining plant budget and `n_train` (4 | 8)
    trials per candidate, then a 16-trial check. A plant CMA needs roughly 150+ rollouts per tool to make progress (the
    minimum per tool is shown in the notebook); small budgets rarely help.
- check: fields `design`, `n` (8 | 16): robustness check, and the 20 s stress test when the design qualifies.
- assimilate: field `design`: fold that design's plant check into the belief.
- apply_dossier: field `dossier` (memory arms only). use_learned: add the learned posterior's suggestions (when available).
- delegate_repair: the engine's repair procedure with ALL remaining budgets, then it submits (ends the investigation): a
  simulator screen of the tools under the belief, an ensemble-robust simulator optimisation of the first tool (800
  simulations) checked on the robot, then CMA-ES on the robot with 60 % of the remaining plant budget on the first tool and
  the rest on the second, stopping early when P(pass) >= 0.75, else submitting the design with the best plant evidence.
  Optional fields: `tool_order` (1-3 tools YOU choose to try first, e.g. from physical reasoning about the cause; the engine's
  own screen ranks the rest), `start_edits` and `design` (start the procedure from that design, with those edits applied).
  Its success rate depends on the plant and simulation budget left when you call it.
- conclude: field `design`: submit it for independent verification (ends the investigation).

Sign conventions: pitch > 0 = torso leans forward. fall_direction +1 = fell forward. x is forward.
Reply with ONE JSON object following the schema. `understanding` = what you now believe and why (physics, not restating
numbers); `uncertainty` = what you do not yet understand; `why` = why this action is the most valuable now."""


class NemotronScientist(sh.HasNemotron):
    """Nemotron as the investigation's director (one instance per investigation)."""

    def __init__(self, **kw):
        kw.setdefault("max_requests", 2 * MAX_TURNS + 4)
        kw.setdefault("max_total_tokens", 900_000)
        super().__init__(roles=("agent",), **kw)
        self.system = AGENT_SYSTEM

    @staticmethod
    def schema() -> dict:
        hyp = sh.HasNemotron.propose_schema()["properties"]["hypotheses"]
        q = {"type": "object", "additionalProperties": False, "required": ["quantity", *sh.QUANTILES],
             "properties": {"quantity": {"type": "string", "enum": list(PRED_QUANTITIES)},
                            **{k: {"type": "number"} for k in sh.QUANTILES}}}
        return {"type": "object", "additionalProperties": False,
                "required": ["understanding", "uncertainty", "action", "why", "hypotheses", "experiment", "prediction"],
                "properties": {
                    "understanding": {"type": "string"}, "uncertainty": {"type": "string"},
                    "action": {"type": "string", "enum": list(ACTIONS)}, "why": {"type": "string"},
                    "hypotheses": hyp, "experiment": {"type": "string"},
                    "prediction": {"type": "array", "maxItems": 3, "items": q},
                    "tool": {"type": "string", "enum": list(sh.TOOLS)}, "mode": {"type": "string", "enum": ["twin", "plant"]},
                    "design_against": {"type": "string", "enum": ["belief", "leading"]},
                    "start_edits": {"type": "string"}, "plant_share": {"type": "number"},
                    "n_train": {"type": "integer", "enum": [4, 8]}, "design": {"type": "integer"},
                    "n": {"type": "integer", "enum": [8, 16]}, "dossier": {"type": "string"},
                    "tool_order": {"type": "array", "maxItems": 3, "items": {"type": "string", "enum": list(sh.TOOLS)}}}}

    def _validate(self, reply, session: LabSession):
        errs = []
        if not isinstance(reply, dict):
            return ["reply must be a JSON object"], None
        a = reply.get("action")
        if a not in ACTIONS:
            return [f"action must be one of {list(ACTIONS)}"], None
        for k in ("understanding", "uncertainty", "why"):
            if not isinstance(reply.get(k), str) or len(reply[k]) > 2 * sh.TEXT_MAX:
                errs.append(f"{k} must be a string of at most {2 * sh.TEXT_MAX} characters")
        devs = []
        hyps = reply.get("hypotheses") or []
        if len(hyps) > sh.MAX_HYPOTHESES:
            errs.append(f"at most {sh.MAX_HYPOTHESES} hypotheses")
        for i, h in enumerate(hyps[:sh.MAX_HYPOTHESES]):
            try:
                devs.append(self.to_deviation(h))
            except Exception as exc:   # noqa: BLE001
                errs.append(f"hypotheses[{i}]: {exc}")
        n_designs = len(session.b.designs)
        if a == "propose" and not hyps:
            errs.append("propose needs at least one hypothesis")
        if a == "experiment":
            spec = reply.get("experiment")
            if not isinstance(spec, str) or not spec:
                errs.append("experiment needs the field `experiment` (a candidate id or your own design)")
            else:
                cand, err = session._candidate(spec)
                if cand is None:
                    errs.append(err + " (observe was already run; choose a candidate or design a counterfactual)"
                                if spec.endswith("observe") else err)
            # the registered prediction is a measurement of the scientist's foresight, not a precondition of the action: a
            # missing or malformed one is recorded and the experiment still runs
            got = {p.get("quantity") for p in reply.get("prediction") or []}
            bad = [p.get("quantity") for p in reply.get("prediction") or []
                   if not all(isinstance(p.get(k), (int, float)) for k in sh.QUANTILES)
                   or any(p[b_] < p[a_] for a_, b_ in zip(sh.QUANTILES, sh.QUANTILES[1:]))]
            if spec != "weigh_test" and (not set(PRED_QUANTITIES) <= got or bad):
                reply = dict(reply, prediction_issue=f"missing {sorted(set(PRED_QUANTITIES) - got)}, malformed {bad}")
                reply["prediction"] = [p for p in reply.get("prediction") or [] if p.get("quantity") not in bad] or None
        if a == "repair":
            if reply.get("tool") not in sh.TOOLS:
                errs.append(f"repair needs `tool` in {list(sh.TOOLS)}")
            if reply.get("mode") not in ("twin", "plant"):
                errs.append("repair needs `mode` twin or plant")
            ps = reply.get("plant_share", 0.6)
            if not isinstance(ps, (int, float)) or not 0.1 <= ps <= 1.0:
                errs.append("plant_share must be in [0.1, 1]")
            if reply.get("design") is not None and not 0 <= reply["design"] < n_designs:
                errs.append(f"design must be an existing design index (0-{n_designs - 1})")
            if reply.get("start_edits"):
                from .eng_tools import parse_counterfactual
                try:
                    parse_counterfactual(reply["start_edits"])
                except ValueError as exc:
                    errs.append(f"start_edits: {exc}")
        if a == "delegate_repair":
            order = reply.get("tool_order") or []
            if len(set(order)) != len(order) or any(t not in sh.TOOLS for t in order):
                errs.append(f"tool_order must list distinct tools from {list(sh.TOOLS)}")
            if reply.get("start_edits"):
                from .eng_tools import parse_counterfactual
                try:
                    parse_counterfactual(reply["start_edits"])
                except ValueError as exc:
                    errs.append(f"start_edits: {exc}")
            if reply.get("design") is not None and not 0 <= reply["design"] < n_designs:
                errs.append(f"design must be an existing design index (0-{n_designs - 1})")
        if a in ("check", "assimilate", "conclude"):
            d = reply.get("design")
            if not isinstance(d, int) or not 0 <= d < n_designs:
                errs.append(f"{a} needs `design` = an existing design index (0-{n_designs - 1})")
            elif a == "assimilate" and not (session.evidence.get(d) or {}).get("checks"):
                errs.append(f"design {d} has no plant check to assimilate")
        if a == "apply_dossier" and session.memory is None:
            errs.append("apply_dossier is not available (no memory in this investigation)")
        if a == "apply_dossier" and session.memory is not None and session.memory.get(reply.get("dossier")) is None:
            errs.append("apply_dossier needs `dossier` = one of the dossier ids shown")
        if a == "use_learned" and session.learned is None:
            errs.append("use_learned is not available here")
        out = dict(reply)
        out["hypotheses_devs"] = devs
        return errs, out

    def act(self, session: LabSession, turn: int, max_turns: int) -> dict | None:
        lines = notebook(session, turn, max_turns) + ["", "TASK: choose the single most valuable next action."]
        dec = self._call("agent", lines, self.schema(), lambda r: self._validate(r, session))
        out = dec.get("out")
        if out is not None:
            session.notes.append({"turn": turn, "understanding": str(out.get("understanding", "")),
                                  "uncertainty": str(out.get("uncertainty", "")), "why": str(out.get("why", ""))})
        return out


def run_agent(session: LabSession, scientist, *, max_turns: int = MAX_TURNS, auto_learned: bool = False) -> dict:
    """The investigation loop. `scientist` has act(session, turn, max_turns) -> action | None (None: engine fallback).
    `auto_learned` (arm A2, no LLM): the learned posterior's suggestions are added right after the first observation."""
    session.begin()
    if auto_learned:
        session.execute({"action": "use_learned"}, "engine")
    for turn in range(max_turns):
        if session.done:
            break
        if session.b.remaining < 8:
            session.force_conclude("plant budget exhausted")
            break
        act = scientist.act(session, turn, max_turns) if scientist is not None else None
        actor = "nemotron"
        if act is None:         # no scientist (engine-only, reproduces A1c5) or a failed/invalid reply (recorded fallback)
            act, actor = session.recommend(), ("engine" if scientist is None else "fallback")
            if actor == "fallback" and act["action"] in ("delegate_repair", "conclude") and max_turns - turn > 2:
                # a formatting failure must not end the investigation: the turn passes, the scientist decides next turn
                act = {"action": "propose", "why": "fallback no-op after an invalid reply"}
        session.execute(act, actor, turn)
    if not session.done:
        session.force_conclude("turn limit")
    return session.record()
