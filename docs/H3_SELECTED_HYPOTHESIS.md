# H3 selected hypothesis — engineering capability, not learned selection

**H3-SR:** In newly sampled planar biped lineages whose fixed transferred17D controller walks on nominal physics but fails under a unilateral0.4 actuator-strength factor, a bounded antisymmetric stance hip/ankle demand basis will increase repeated FULL recovery by at least15 percentage points over both matched-budget17D tuning and double-budget17D tuning, without more than5 pp healthy-walking or harmful-intervention regression.

This is an exploratory engineering-pilot threshold. It is not a powered confirmatory population or AI-learning claim. Failure to qualify twelve new lineages is an informative acquisition limitation, not evidence for/against controller superiority.

Inputs are the existing nominal body/controller, controller clock/contact estimator and observed state; outputs are six joint demands. No hidden fault label, side, magnitude or verifier outcome enters the controller or optimizer score. Evaluation alone applies hidden unilateral loss. Two signed gains are found using conventional CMA-ES on the plant; this uses physical trials and must be charged. No cross-robot model, history retrieval or Nemotron call is proposed.

For leg l, sign s_l=+1 on left and−1 on right, phi_l=(phi+l/2) mod1. Let b_l=I(loaded_l and phi_l<duty)*sin²(pi*phi_l/duty), and r(t) the existing initiation smoothstep ramp. For j in {hip,ankle}, added demand is s_l*g_j*0.15*nominal_limit*r(t)*b_l, with g_j∈[−1,1]. Knees are unchanged. Existing FP, contact clock and PD execute first. The native actuator clip and weak physical gear remain authoritative; this cannot restore lost peak torque.

The family nests17D exactly at gains(0,0). It permits an antisymmetric stance feedforward basis absent from shared17D parameters, while retaining that class's state-dependent asymmetries. It does not provide arbitrary independent leg trajectories, per-leg phase clocks, a stability proof or general traction repair.

Integration is research-only through `creature_forge/h3_capability.py`; an exception-safe, single-thread worker factory scope routes19D candidates into the unchanged hidden-plant physics and `recovery.assess`. It is absent from production factories, UI, A1 tools and release. Native zero-gain identity and end-to-end bridge behavior must pass a newly authorized physics gate before adaptation. Non-physics tests establish algebra/contracts only.

Expected improvement, if any: redistribute stance effort/attitude control between unequal physical legs beyond what shared parameter tuning finds. Equally plausible failures include clipping, insufficient support, wrong phase shape and harder search. The larger-budget17D control tests finite-search explanations; it cannot prove global infeasibility of17D. The [protocol](H3_EXPERIMENTAL_PROTOCOL.md) fixes qualification, reliability, uncertainty, harm and stopping rules before any H3 physical outcomes.
