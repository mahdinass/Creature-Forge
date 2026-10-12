# CREATURE FORGE
## Autonomous Physics-Grounded Robot Design, Failure Investigation, and Evolution

**Document type:** Master Project Specification / Product Requirements Document / Technical Architecture / Research Plan / Hackathon Execution Plan  
**Version:** 1.0 — ambitious full-scope blueprint  
**Prepared:** 2026-10-12  
**Hackathon:** Nebius × NVIDIA Global AI Hackathon 2026  
**Primary track:** Physical AI  
**Submission deadline:** 2026-10-30, 10:00 Pacific / **18:00 Europe/Oslo**  
**Development mode:** Primarily solo, with Claude Code and Codex as coding collaborators  
**Status:** Specification; designs, metrics, experiments, and demonstrations below are **proposed, not implemented or validated**.

---

# 0. Executive directive

**Build the ambitious product—not a trivial robot walking animation.** Creature Forge is a virtual robotics R&D laboratory in which a person can create a creature, give it a physical goal, watch it fail in a real dynamics simulator, and then watch an autonomous AI engineer **investigate the cause, devise and test falsifiable interventions, redesign the morphology and/or controller, train behavior, and reuse validated engineering knowledge on unfamiliar creatures**.

The defining product promise is:

> **From failure to understanding to verified physical redesign.**
>
> Creature Forge does not just search for better robot parameters. It measures what failed, builds hypotheses about why, chooses controlled physical experiments, and accepts modifications only after independent simulation-based verification.

**Non-negotiable truth constraint:** The simulator and deterministic evaluation code determine whether an intervention actually works. The NVIDIA model may propose a hypothesis and a modification but may **never** declare physical success without measured evidence. Correlation and a visually plausible explanation do not constitute a proven causal mechanism; counterfactual tests narrow alternatives, and conclusions carry uncertainty.

## 0.1 The full vision, without pretending it is all a single MVP

All these capabilities belong in the **full product specification**:

1. Interactive 3D robot/creature design studio, with templates, editable anatomy, free-form structural editing, text-assisted and sketch-assisted creation.
2. Real rigid-body dynamics, collision, contact/friction, joints, motors, terrains, and sensor/telemetry instrumentation.
3. Movement learning through conventional control, optimization, evolutionary search, and optional reinforcement learning.
4. Physics-grounded **Failure Autopsy**, with chronology, plots, force overlays, identifiable failure signatures and competing hypotheses.
5. Autonomous NVIDIA Nemotron investigative agent, invoked through Nebius, which chooses informative and admissible experiments.
6. **Counterfactual Arena**: matched runs of the original, controller-only modification, morphology-only modification, and joint modification.
7. Automated redesign subject to constraints on mass, torque, energy, material/cost proxies, and geometry.
8. Knowledge transfer: reuse verified findings across different creatures, with applicability screening and negative-transfer detection.
9. Data-driven predictive physics surrogate / intervention-ranking model, trained on logged experiments and calibrated against high-fidelity simulation.
10. Terrain challenges, robustness testing, perturbations, environment randomization, and an interactive **Break My Robot** challenge.
11. Evolution / lineage visualization, design versioning, replay and rollback.
12. Engineering explanation, uncertainty, traceability, evidence reports, and downloadable artifacts (MJCF, JSON, CSV, reports, optional 3D exports).
13. Multi-robot comparative experiments and parallel compute.
14. Polished creator-centric web product, accessible demo, API, experiment dashboard, and shareable replays.
15. Optional NVIDIA Isaac Lab acceleration, NVIDIA Cosmos reasoning/visual workflows when genuinely appropriate and available, hardware validation path, and commercialization path.

**Engineering principle:** The ambition is retained as an explicitly decomposed roadmap. A feature is not “done” because a screen exists; each feature has a measurable acceptance test. Prioritize functioning, end-to-end vertical slices over broad mock interfaces.

## 0.2 The smallest meaningful scientific claim

> Given a simulated robot with an observed locomotion failure, an agent can select physics-grounded interventions, test them under controlled conditions, and produce an evidence-backed improvement. We evaluate whether this guidance reaches a target more efficiently than equally budgeted non-guided search.

**Stronger conditional claim:** Verified lessons from one morphology improve experiment efficiency on held-out morphologies **without increasing catastrophic failures**. This must be tested, not assumed.

**Do not claim:** discovering physics laws from first principles, guaranteed causal identification, universal robot design, robust real-world deployment, general sim-to-real transfer, or superior sample efficiency until benchmarks demonstrate it.

---

# 1. Official hackathon compliance and constraints

This section is grounded in the official rules supplied by the project owner, not informal marketing descriptions. Resolve conflicts in favor of the actual official rules.

## 1.1 Eligibility and track

- Submit in **Physical AI**: embodied systems, robot learning, simulation, agentic physical reasoning, and evaluation of robot policies.
- **Simulation-only is allowed.** No real hardware is required.
- If no physical hardware is included, the demo video needs **at least one minute showing the key application modules in action**.
- The actual software **must use at least one NVIDIA open-source model** and **run on Nebius Token Factory or Nebius AI Cloud**.
- The rules define this as either a real runtime call to the Token Factory inference API or execution/deployment on Nebius AI Cloud resources such as Serverless Jobs, Serverless Endpoints, or DevPods. Merely using Claude Code/Codex to develop the app does not satisfy this.
- The stage-one judging filter checks that the project genuinely fits the track and meaningfully uses featured infrastructure.

## 1.2 Deliverables that must not be forgotten

- [ ] Functional application matching the described and filmed behavior.
- [ ] Public source repository (GitHub, GitLab, or Bitbucket).
- [ ] Open-source license visible in the repository (choose only after dependency/IP audit).
- [ ] README: installation, prerequisites, environment variables, setup, how to run, test demo scenario, evaluation reproduction.
- [ ] Explanation of where NVIDIA model(s), Nebius Token Factory and/or AI Cloud are used.
- [ ] YouTube demonstration **under three minutes**; no unlicensed third-party content.
- [ ] At least one minute of actual module operation for simulation-only Physical AI.
- [ ] Text description, track selection and feedback on used Nebius/NVIDIA technologies.
- [ ] Provide judging access. Physical AI is exempted from the ordinary hosted-demo URL requirement, but the separate testing-access language still exists. **Recommended:** provide a free public browser demo plus local reproducibility; document limitations if hosted compute is restricted.
- [ ] All submission material in English, or translate it into English.
- [ ] Keep the application available for judging through **December 15, 2026** at minimum; the rules require availability until the judging period ends.
- [ ] Submit by **October 30, 2026, 18:00 Oslo time**. Treat October 29 as the internal hard deadline.

## 1.3 Judging strategy

Four **equally weighted** criteria:

| Criterion | What Creature Forge needs to prove |
|---|---|
| Technological implementation | Actual physics integration, meaningful NVIDIA/Nebius reasoning, valid models, independently repeatable experiments. |
| Design | Coherent, polished, discoverable flow: create → simulate → investigate → experiment → redesign → verify → share. |
| Potential impact | Credible robotics-R&D and teaching use case; useful engineering artifacts; realistic limitations. |
| Quality of idea | Non-obvious workflow: failure-driven hypothesis testing and physically verified design revisions rather than generic animation or pure random evolution. |

**Stage-one gate:** Genuine Physical AI use of the specified technologies.  
**Tie-break priority:** Technological implementation first, then the criteria order in the rules.  
**Prize note:** One overall **or** one track award, plus any eligible bonus according to the official rules; do not assume awards can freely stack.  
**Tavily bonus:** Optional only if genuinely relevant and used in a **functional runtime Tavily API call**. Do not dilute the core experience to chase an unrelated bonus.

## 1.4 IP / safety / costs

- The submission must be original work owned by the entrant and honor all asset, code, model, dataset, and third-party licenses.
- Open-source dependencies and third-party technical help are permitted under the stated ownership/licensing conditions.
- Do **not** put credentials or private tokens in repository history, exported traces, or demo footage.
- Any hardware option must restrict dangerous commands, respect physical safety and human approval, and **cannot** be presented as verified merely because simulation succeeded.
- GPU, hosting, Nemotron calls, and generated videos have potentially material costs. Include explicit quotas, concurrency limits, budget alerts and a pause button.

---

# 2. Product definition

## 2.1 One-sentence product

**Creature Forge is a virtual engineering laboratory where AI-guided physical experiments transform failed robot designs into verified, improved creatures.**

## 2.2 Target audiences

1. **Robotics researchers / students:** Explore morphology-control co-design, active diagnosis and experiment efficiency.
2. **Prototype engineers / startups:** Screen early-stage robot architectures and failure modes prior to building hardware; no claim of manufacturing readiness.
3. **Educators:** Teach center of mass, stability, friction, control feedback and tradeoffs through observable experiments.
4. **Hackathon judges / science enthusiasts:** Understand the workflow in seconds: create a creature, watch it fail, watch competing repairs tested, watch the improved design win.

## 2.3 Product value proposition

- **Explainable experimentation:** Every proposed intervention has a named hypothesis, predicted measurable effect, test conditions and result.
- **Closed-loop redesign:** Modify mechanical and controller variables, not just replay a fixed policy.
- **Knowledge accumulation:** Retain both successful and failed intervention outcomes; optionally transfer to new creatures.
- **Honest verification:** Use deterministic physics tests plus robustness checks to accept/reject claims.
- **Creator experience:** Design, animate and inspect creatures rather than only manipulating scripts.

## 2.4 Primary user story

> As a robotics designer, I want to create a robot, ask it to move across a challenge, observe why it fails, and let the system autonomously propose and experimentally verify changes so I can learn how to improve the actual design.

## 2.5 Representative demo story

- User selects **Biped** and changes upper-body mass or foot size; clicks **Forge**.
- The 3D scene contains a physically simulated articulated robot and a visible target.
- User selects a terrain, maximum mass, torque limit and objective.
- Robot runs and falls or slips; the incident is recorded and automatically timestamped.
- Failure Autopsy shows center of mass, support area, contact forces, angle/velocity, actuation and a confidence-labeled explanation.
- Nemotron proposes *testable alternatives*, e.g., adjust controller response, change foot geometry, redistribute torso mass.
- Parallel isolated test runs compare matched conditions, with predicted vs observed effects.
- The best valid change becomes an updated design; failures and rejected options remain in the experiment history.
- Optionally optimize a locomotion policy, reveal resulting gait, and reuse learned failure patterns on a second creature.
- User exports a verified engineering report and shareable replay.

---

# 3. Explicit project scope and delivery tiers

The product specification contains **the complete ambition**. Delivery labels are a coordination tool for implementing the full vision safely, not an instruction to erase ambitious features.

| Tier | Definition | Includes | Hard success check |
|---|---|---|---|
| **T0 — Foundation** | A real, end-to-end physical system | Robot, MuJoCo, controller, logger, failure detection, editable parameters, replay | A robot really moves; changing mass/friction/torque measurably changes observed behavior. |
| **T1 — Core AI invention** | Autonomous, physics-grounded improvements | Nemotron investigator, typed hypotheses, counterfactuals, morphology/controller changes, verification | Blind test: find and validate an improvement without prewritten fix selection. |
| **T2 — Strong product** | Usable and convincing | Three-dimensional studio, multiple bodies, scenario library, baseline comparison, report, lineage, hosted demo | New user completes full workflow with no developer intervention. |
| **T3 — Advanced intelligence** | Research differentiation | Failure memory, applicability estimation, transfer across robots, online surrogate, active experiment selection | On held-out problems, demonstrate improvement or clearly report negative results. |
| **T4 — Moonshots** | Signature presentation and platform scale | Sketch/text-to-robot, unrestricted topology within a validated grammar, parallel RL evolution, multi-terrain tournaments, sophisticated rendering, Isaac Lab acceleration, optional Cosmos, hardware path | Independently functioning modules plus robustness and license tests. |

**All tiers are specified below.** The shipping branch must remain releasable at the end of every tier. Features that are unfinished must be labeled *experimental* or disabled rather than simulated with deceptive UI.

## 3.1 Demonstration scenarios

- **S1: Forward-tip biped** — mass/geometry/control cause loss of balance.
- **S2: Low-friction slippery ground** — forces exceed available traction; requires gait/force adaptation.
- **S3: Torque-limited legs** — collapse or failure to recover with motor saturation.
- **S4: Foot-clearance obstacle** — repeated toe collisions during swing phase.
- **S5: Oscillating controller** — excessive feedback gain or poor damping causes unstable cycles.
- **S6: Changed terrain after success** — perturbation / transfer / adaptation.
- **S7: New morphology** — reuse applicable physical lessons and reject inapplicable ones.
- **S8: Ambiguous diagnosis** — at least two initially plausible causes; informative test separates them.
- **S9: Engineering cost constraint** — improve motion without violating mass, torque or cost limit.
- **S10: New user-designed creature** — compile a valid robot from a constrained editor or sketch input.

Each scenario must include at least one **clean control** and multiple random seeds. Do not embed the hidden fault identity in any prompt visible to the agent.

---

# 4. Scientific principles and mathematical formulation

## 4.1 Joint robot design problem

Let:

- `m`: robot morphology parameters (segment dimensions, masses, inertias, joint placement, joint bounds, feet/contact geometry, motor capacity).
- `theta`: controller/policy parameters.
- `e`: environment parameters (friction, terrain, obstacles, gravity, disturbances).
- `x_t`: simulator state at time `t` (positions, velocities, contacts, forces, actuator state).
- `u_t`: controller action.
- `F`: physics transition function.

Dynamics:

```text
x_(t+1) = F(x_t, u_t, m, e, dt)
u_t = pi_theta(observation(x_t))
```

Optimize for robust task performance under constraints:

```text
maximize_(m, theta)   E_e [ J(m, theta, e) ]
subject to            mass(m) <= M_max
                      actuator_torque(m, theta) <= tau_max
                      geometry_valid(m)
                      contact_feasible(m)
                      energy(m, theta) <= E_max  (if requested)
```

Potential composite objective **only if its components are separately reported**:

```text
J = w_progress * forward_progress
  + w_survival * time_upright
  + w_success  * goal_reached
  - w_energy   * normalized_energy
  - w_slip     * foot_slip
  - w_impulse  * harmful_contact_impulse
  - w_violation * constraint_penalties
```

**Avoid reward hacking:** High reward is not physical competence. Track individual metrics, inspect videos and run held-out perturbations. A creature that throws itself forward and immediately collapses must not qualify as robust walking because its distance briefly increased.

## 4.2 Failure detection

Potential event conditions (calibrate by morphology):

- Height / torso orientation outside upright region for sustained interval.
- Head/torso touches ground unexpectedly.
- Joint angle or rate outside configured safe envelope.
- Persistent foot slip during stance.
- Sustained actuator saturation with insufficient acceleration.
- No meaningful forward progress over a window.
- Exceeded impact / load or numerical instability thresholds.

Each detector emits **event + evidence**, not a definitive causal label. One failure can have multiple simultaneous mechanisms.

## 4.3 Failure hypotheses

Represent candidate explanations as machine-readable objects:

- **Pitch instability**: angular momentum and corrective torque pattern.
- **Insufficient traction**: required horizontal reaction beyond friction capability.
- **Actuator saturation**: torque limits reached while errors persist.
- **Kinematic limitation**: foot clearance, joint range or stride geometry prevent intended motion.
- **Control oscillation**: phase lag, high gains or mismatch between controller and dynamics.
- **Contact timing / geometry**: unexpected touchdown or loss of support.
- **Model mismatch**: physical parameters or measurement model deviate from assumptions.

**Physics caveat:** Static support-polygon intuition is a useful approximation but inadequate by itself for dynamic locomotion. Use COM velocity, angular momentum, contact wrench/center of pressure where available, torque limits, and trajectory dynamics; don't call a dynamic fall 'proved' solely because the COM projection briefly crossed a foot boundary.

## 4.4 Hypothesis → intervention → causal test

A hypothesis `H` must make a falsifiable prediction:

```text
H: The fall is primarily caused by actuator saturation.
Prediction: Under matched initial states and terrain, increasing allowable torque
            by a controlled amount should reduce saturation time and improve
            recovery; an unrelated foot-friction change should have weaker effect.
```

Interventions `a` must specify exact changes and bounds. Hold other factors fixed where possible. Run matched experiments across multiple seeds. Compare differences and confidence intervals. An observed effect may support a mechanism but not uniquely identify it; keep competing hypotheses in the record.

**Explicit split for morphology-control coupling:**

1. **Frozen-policy effect:** vary morphology with controller unchanged. Tests immediate mechanical contribution but may unfairly disadvantage morphologies needing a different policy.
2. **Adapted-policy effect:** retrain or retune the same-budget controller for each changed body. Tests combined design benefit but introduces optimization effects.
3. **Matched controls:** retain original body with equal policy tuning budget so design changes are not credited for extra training.

This distinction is mandatory for trustworthy co-design evaluation.

## 4.5 Active experiment selection

Candidate intervention pool `A` includes controller, geometry, mass, torque, contact and diagnostic probes. All candidates are validated against a typed schema and hard physical constraints.

Selection policy can use:

```text
utility(a) = expected_improvement(a)
           + lambda * expected_information_gain(a)
           - beta * experiment_cost(a)
           - gamma * risk_or_constraint_penalty(a)
```

Baseline: uniform/random candidate choice and fixed-grid or CMA-ES parameter search under the **same number of simulator evaluations**. Enhanced policies may use a calibrated surrogate or information gain estimate, but the first implementation can use rule-based priors + structured Nemotron reasoning.

**Do not mislabel heuristics as Bayesian inference.** If no calibrated posterior is implemented, call it uncertainty-guided selection rather than a proven expected-information-gain method.

## 4.6 Verification decision

A redesign is accepted when all apply:

1. Candidate compiles and simulates without numerical instability.
2. All hard design constraints hold.
3. Primary metric improves under pre-registered evaluation conditions or reaches goal threshold.
4. Improvement survives multiple seeds and a held-out set of initial states / terrain variations.
5. Secondary metrics are within permitted regression limits.
6. Results and exact configuration are retained for reproduction.

If inconclusive: **unverified**, not improved. If worse: **rejected**, but record evidence for future learning.

---

# 5. High-level architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND — Creature Forge Studio                                    │
│ Design Studio | 3D Arena | Failure Autopsy | Counterfactual Lab       │
│ AI Scientist | Evolution Tree | Knowledge Library | Benchmarks      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP / WebSocket / SSE
┌──────────────────────────────▼──────────────────────────────────────┐
│ API / ORCHESTRATOR                                                  │
│ Sessions | Design validation | Job scheduler | Experiments | Events │
├───────────────┬─────────────────────┬───────────────────────────────┤
│ ROBOT ENGINE  │ AI SCIENTIST        │ LEARNING / EVALUATION         │
│ MJCF factory  │ NVIDIA Nemotron    │ CMA-ES/CEM, optional PPO      │
│ MuJoCo        │ hypothesis policy  │ Intervention ranker/surrogate │
│ Physics logs  │ experiment planner │ Benchmarks + robustness       │
│ Renderer data │ evidence critic    │ Memory + applicability       │
├───────────────┴─────────────────────┴───────────────────────────────┤
│ DATA / INFRA                                                       │
│ SQL metadata | object artifacts | telemetry | model registry       │
│ Nebius Token Factory runtime API | optional Nebius AI Cloud jobs   │
└─────────────────────────────────────────────────────────────────────┘
```

## 5.1 Proposed stack

| Layer | Recommended technology | Notes |
|---|---|---|
| Physics ground truth | **MuJoCo** + Python | Authoritative rigid-body simulation, MJCF model assets and contacts. |
| Robot generation | Validated design DSL → MJCF / `MjSpec` | Parameterized morphology plus optional topology grammar. |
| Controller | PD/state-feedback + parametrized CPG/gait; optional PPO | Get an always-runnable baseline before expensive policy learning. |
| Optimization | NumPy, SciPy, Nevergrad / CMA library; optional PyTorch | CEM/CMA-ES for low-dimensional parameters; RL for advanced policies. |
| AI investigator | NVIDIA **Nemotron** through **Nebius Token Factory** | Structured experiment/hypothesis tool proposals with validation. |
| Optional physical VLM | Approved NVIDIA Cosmos reasoner if available | Secondary perception/reasoning only; don't assume legacy hosted model IDs exist. |
| Optional accelerated training | NVIDIA Isaac Lab / Isaac Sim or MuJoCo Playground | Separate adapter; extra hardware and dependencies. |
| Backend | Python 3.11+; FastAPI; Pydantic | Pin exact versions after smoke tests. |
| Jobs | Local worker + queue; optional Nebius Serverless Jobs | Atomic results and cancellation, quotas, retries. |
| Database | SQLite for local / PostgreSQL for hosted | Versioned schema and migrations. |
| Experiment artifacts | local filesystem or object store | MJCF, configs, seeded replay states, media, metrics, reports. |
| Frontend | React + TypeScript + Vite or Next.js | Choose one early, avoid multiple frameworks. |
| 3D viewer | Three.js / React Three Fiber | Visualize cached simulation frames; physics stays server-authoritative. |
| Styling | Tailwind + accessible component kit | Dense, cinematic lab UI, responsive and readable. |
| Charts | Recharts / uPlot / Plotly | COM, torque, failure time, progress vs experiment. |
| Dev/test | pytest, Playwright, TypeScript typecheck | CI validation at every merge. |
| Packaging | Docker Compose | One-command local demo, hosted worker alternative. |

### Critical integration architecture

**There must be only one authoritative physics implementation.** The browser replays simulation states and offers controls; it must not run a second independent physics engine and silently diverge. Client-side animation may interpolate authoritative poses but cannot fabricate outcomes.  
**Model availability is runtime-discovered.** Exact Nemotron model IDs, region-specific URLs, available tool/JSON output features, and pricing must be checked against the actual account and `/v1/models` response.  
**Optional Cosmos is non-critical.** An older Nebius Cosmos3 hosted recipe is explicitly marked historical/retired. Treat Cosmos integration as conditional until current serving access, model licensing, and endpoint behavior are verified.

---

# 6. Workstream A — Robot creation, anatomy and 3D studio

## A1. Built-in families

Minimum designed families:

1. **Biped** — two legs, pelvis/torso, feet; primary balancing and gait experiments.
2. **Hopper** — one or two spring-like legs; fewer DOFs and clear landing dynamics.
3. **Quadruped** — four legs; richer contact/support modes, transfer challenges.
4. **Crawler / unusual creature** — deliberately nonhuman morphology with low center of mass.
5. **Generated assembly** — composed from a constrained grammar; not unrestricted arbitrary meshes as physics bodies.

Begin with a small stable family and grow to others. For each family, provide a valid model, valid initial pose, controller adapter, allowed parameter ranges, collision self-checks and unit tests.

## A2. Parameterized anatomy

User-editable robot design variables should include:

- Torso dimensions and shape primitives.
- Segment lengths and cross-sections; joint axes and positions.
- Mass distribution and inertial properties (derive feasible inertias from geometry unless explicitly advanced).
- Feet: length, width, contact pad area and material/friction settings.
- Joint limits, damping, springs, motor power / maximum torque.
- Relative body pose and symmetry options.
- Optional tail / stabilizer / extra support point.
- Robot appearance (colors, skins, meshes) strictly separate from collision geometry.

**Validation:** Geometry must be connected, joints nondegenerate, dimensions and inertia physically plausible, collision exclusions coherent, and a static starting pose generatable. Invalid user designs should show actionable errors, never crash the server.

## A3. Design modes

### A3.1 Template editor (foundation)

Sliders, visual joint handles, symmetry toggle and live mass/center-of-mass estimates. Every edit creates a new **design version**. No AI call required for ordinary editing.

### A3.2 Text-to-creature (advanced)

Example: "A lightweight four-legged climber with a heavy central body and broad contact feet, within 12 kg."

Nemotron converts the request into a **typed design DSL**, not executable code. Validate against grammar and constraints, compile to MJCF, preview, and ask for clarification only where indispensable. The LLM cannot arbitrarily write untrusted scripts or unsafe XML unchecked.

### A3.3 Sketch-to-creature (advanced)

- User sketches a stick-figure or segmented creature, marks joints, limbs and intended ground contacts.
- UI extracts primitives and editable graph nodes. A vision model may assist, but manual corrections remain available.
- Geometry-to-robot compiler enforces connectedness, valid DOF and collision definitions.
- Provide user control over scale, symmetry, locomotion direction and motorized joints.
- Render a preview with clearly highlighted inferred/ambiguous joints.

**Do not equate any unconstrained image with a physically valid robot.** The UI must visually present a structured interpretation users can correct.

### A3.4 Unrestricted topology within bounded grammar (moonshot)

Graph grammar for new links, joints and support points with a bounded maximum number of bodies/DOFs; automatically generate controllers for new observations/actions using morphology-aware descriptors or a small shared policy interface. Require topology and performance tests before allowing the design to join optimization.

## A4. Visualization

- Cinematic but readable 3D lab aesthetic; precise shadow/contact cues, terrain grid, coordinate gizmos.
- Orbit camera, orthographic side view, chase camera, free view, slow motion and frame stepping.
- Select robot link to inspect mass, inertia, joint angle, torque and constraint state.
- Overlays: COM marker and velocity, projected COM, support contacts, approximate center of pressure where available, reaction forces and joint torques.
- Timeline scrubbing with synchronized plots.
- Side-by-side synchronized playback for counterfactuals.
- Color-coded design changes (geometry/actuation/controller) and a clear before/after diff.
- Never label estimated quantities as measured quantities.

## A5. Acceptance criteria

- [ ] At least one parametrized robot compiles and simulates after changing geometry and mass.
- [ ] Visible motion originates from recorded MuJoCo states.
- [ ] Editor rejects invalid parameters and invalid joint structures.
- [ ] A creator can reproduce the same robot by importing saved DSL/MJCF.
- [ ] Templates, text-to-design and sketch-to-design have explicit success and fallback behavior.
- [ ] New topology is accepted only if the physics model and controller adapter validate.

---

# 7. Workstream B — Physics simulator and sensor instrumentation

## B1. Simulator contract

Inputs: `RobotDesign`, `ControllerConfig`, `EnvironmentConfig`, seed, duration, solver settings.  
Outputs: `SimulationResult` with status, metrics, time series, events, replay frames and artifacts.

- Use MuJoCo as primary physics backend.
- Integrate fixed or controlled timestep; record solver/version/configuration for reproduction.
- Support floor friction, inclines, rough terrain, steps, periodic bumps and external pushes.
- Apply controls at a defined frequency decoupled from rendering frequency.
- Use configuration-dependent sensor sampling and logging rather than recording everything at full frequency by default.
- Detect nonfinite state, excessive penetrations, unstable solver behavior and invalid actuator commands.
- Keep simulation state snapshots for restarting matched counterfactual experiments.

## B2. Logged telemetry

At minimum:

| Signal | Purpose |
|---|---|
| Root position, orientation and velocities | Stability, progress, angular momentum trends. |
| COM position / velocity | Mass-motion analysis. |
| Joint positions, velocities, torques, limits | Control behavior, actuator saturation, reachability. |
| Ground contact states and forces/impulses | Impact, support and slip investigation. |
| Foot tangential velocity during stance | Detect slip. |
| Body height and orientation | Fall detection. |
| Control targets / errors | Distinguish policy failure vs hardware limits. |
| Terrain ID, friction and perturbations | Controlled experiments. |
| Mechanical and energy proxies | Tradeoff optimization and constraints. |
| Physics configuration + random seed | Reproducibility. |

For full product include optional synthetic IMU, joint encoder noise, bias and latency to simulate hardware sensing—but retain ground-truth telemetry for benchmark adjudication.

## B3. Terrain suite

- Flat ground (sanity / baseline).
- Reduced-friction surface.
- Short inclines / ramps.
- Low obstacles and step-ups.
- Rough ground, randomized height fields.
- Lateral disturbance / external impulse at random time.
- Mixed terrain challenge with multiple segments.

Separate **seen training terrains** from **held-out evaluation terrains** to avoid overfitting.

## B4. Real-time vs accelerated simulation

- **Live mode:** visual playback close to real time for the user.
- **Experiment mode:** headless, faster-than-real-time batch simulation with logs and sparse frames.
- **Arena mode:** compare N runs side by side using precomputed or live-progressive streams.
- **Learning mode:** high-throughput rollouts if a GPU-compatible backend is available.

A live dashboard can visualize rapidly computed experiments after the fact. It must distinguish *live computation* from *replay* in the product and video.

## B5. Physics quality gates

- Gravity drop test: object/robot falls in expected direction and settles reasonably.
- Friction sanity test: same push causes more slip at lower friction.
- Torque-limit test: lower limits produce expected saturation signatures.
- Conservation/sanity checks where appropriate, mindful of contacts/actuators.
- Physics sensitivity test: independent parameter changes produce sensible trajectories.
- Replay determinism test for identical environment/build/hardware where feasible; document floating-point nondeterminism.

---

# 8. Workstream C — Locomotion learning and evolutionary search

## C1. Controller progression

**Level C0 — Deterministic baseline:** Simple PD/state feedback for posture/phase tracking, or CPG oscillator producing target joint angles. Configured to provide a stable enough baseline to investigate meaningful changes.

**Level C1 — Parameter search:** CMA-ES, CEM or Bayesian optimization on low-dimensional gait and feedback parameters. Use multiple random seeds and explicit simulation budgets.

**Level C2 — Co-optimization:** Alternate between morphology changes and controller tuning. Compare with unchanged morphology under equal controller budgets.

**Level C3 — Reinforcement learning:** PPO or similar on one controlled morphology family; use standard implementations and checkpoint/resume. Train on randomized conditions, evaluate out of distribution.

**Level C4 — Morphology-conditioned skill/policy transfer:** Use body descriptors as conditioning inputs and/or distillation. Requires careful action/observation adapters across topologies.

## C2. Why not make full RL the first dependency?

Training a brand-new policy from scratch for every arbitrary body can consume enormous GPU and debugging time. The core contribution is failure understanding and physical intervention, so **basic feedback control + parameterized search must remain a valid non-RL path**. RL is an ambitious differentiator when functioning, not a reason the platform cannot launch.

## C3. Evolution mechanics

- Population of robot/controller genomes (typed parameters and bounded structural edits).
- Mutation/crossover with validation; maintain diversity archive, novelty score optional.
- Objective tradeoffs: distance, survival, energy, material/cost and robustness.
- Preserve elite and rejected designs with metadata, ancestry and experiment outputs.
- Allow human to pin a design and branch subsequent exploration.
- Display **lineage tree** with inherited morphology/control changes and proof links.
- Support Pareto front instead of hiding tradeoffs in a single reward.

## C4. Failure-guided evolution vs blind evolution

Two arms of the experiment:

1. **Blind baseline:** Same mutation budget with random/CMA-ES changes, no diagnostic insights.
2. **Physics-guided arm:** Agent observes logs, selects hypotheses and targeted interventions, shares the same simulator evaluation budget.

Track the **number of physics evaluations**, not merely wall time or LLM calls; also report LLM tokens, wall time and total cost to show the true tradeoff.

## C5. Acceptance criteria

- [ ] Robot changes behavior measurably as controller parameters change.
- [ ] Simple search finds improvement on at least one purposely difficult but solvable task.
- [ ] Evolution does not use invalid bodies or exploit uncontrolled rewards.
- [ ] PPO path, if enabled, provides training curves, saved checkpoint and honest performance evaluation.
- [ ] Morphology-conditioned transfer is assessed on body types not used to build the memory or train the model.

---

# 9. Workstream D — Failure Autopsy: forensic physical reasoning

## D1. Trigger

When a run fails or underperforms, produce a **FailureCase** containing:

- Design and controller version IDs.
- Environment, seed and relevant physical parameters.
- Failure event and first-causal-window time range (pre/post failure).
- Telemetry summary and replay pointer.
- Candidate failure mechanisms, evidence for/against each, and uncertainty.
- Suggested diagnostic interventions—not automatically accepted facts.

## D2. Structured physics features

Derived examples:

- Maximum and time-averaged root pitch/roll; angular-rate growth preceding fall.
- Stance duty cycle, center-of-mass motion, dynamic support transitions.
- Joint tracking error and percentage of time at motor saturation.
- Foot collision count, touchdown timing, toe clearance, foot slip duration.
- Required vs achievable momentum change (model-based estimate).
- Contact impulse spikes, torque/energy budget, height margin.
- Oscillation spectrum/autocorrelation for repeated unstable cycles.
- Correlation between failure and changes in friction, mass or disturbance.

Prefer a Python feature extractor with unit tests over dumping tens of thousands of raw frames into an LLM context.

## D3. Evidence taxonomy

Every statement is labeled:

- `OBSERVED`: direct signal or deterministic calculation from logged data.
- `INFERRED`: model-based explanation with confidence and caveats.
- `PREDICTED`: hypothesis regarding an untested modification.
- `VERIFIED`: result reproduced under a specified evaluation protocol.
- `REJECTED`: intervention fails prediction or violates constraints.
- `UNKNOWN`: data insufficient or confounded.

Visual badges must not make conjectures look established.

## D4. Diagnostic agents

**Physics feature extractor:** Numerical processing, no LLM dependency.  
**Evidence curator:** Selects salient time windows, counters and visual overlays.  
**Nemotron investigator:** Consumes compact structured evidence; proposes multiple hypotheses with predicted distinguishing signals.  
**Skeptic/critic:** Checks each hypothesis against measured evidence and identifies counterexamples / missing measurements. Could reuse the same model with a separate prompt, but report that honestly.  
**Experiment planner:** Creates valid intervention candidates with costs and bounds.  
**Verifier:** Independently executes and scores candidates; can overturn all AI claims.

## D5. Causal discipline

- Distinguish description, correlation and intervention evidence.
- Use controls matched for seed, body, controller and terrain.
- Treat coupled changes as jointly causal, not individually identified.
- Consider controller–morphology adaptation confounding.
- Log cases where the AI provides an elegant explanation but tests reject it.
- Do not assume a solution that helps one seed will help all seeds.
- Show uncertainty and stop/abstain when evidence is inadequate.

## D6. User-visible output

A forensic report with:

1. Replay 3–5 seconds before the incident, at slowed speed.
2. Telemetry graphs aligned to the frame cursor.
3. Free-body / force arrows and COM trajectory overlays where computable.
4. Ranked competing explanations with explicit evidence.
5. AI-suggested probes and predicted effects.
6. Actual experiment outcomes and revisions to confidence.
7. Final conclusion stated at the strength supported by the evidence.

---

# 10. Workstream E — Nemotron autonomous investigation agent

## E1. Scope of autonomy

The investigator may autonomously:

- Summarize measured failure characteristics.
- Propose testable physical hypotheses.
- Select diagnostic observations and low-risk experiments.
- Propose bounded controller/morphology interventions.
- Predict their effects as hypothesis statements.
- Request counterfactual evaluation runs.
- Analyze measured differences, update hypotheses, store findings.
- Plan a sequence of improvements within a time/compute budget.

It may **not** edit arbitrary server files, execute arbitrary shell commands, falsify results, ignore constraint validators, or modify the base benchmark truth labels. Hardware control requires separate approval and sandboxing.

## E2. NVIDIA/Nebius runtime guarantee

- Create a `NebiusLLMProvider` adapter implementing a generic chat/structured-response interface.
- Use a currently available NVIDIA open-source Nemotron model through **Token Factory** for actual decisions during a product run.
- On startup, verify credentials and list model availability; use configurable supported model IDs.
- Log model ID, endpoint (redacted), inference latency, tokens, request IDs and cost when available.
- If offline or quota reached, application remains usable in manual/classical mode **but must clearly indicate that AI investigator is unavailable**; do not misrepresent a deterministic heuristic as Nemotron.
- Use timeouts, retries, schema validation, response-size limits, rate limiting and safe fallback.
- Do not make model reasoning rely on live browser video frame-by-frame; summarize structured telemetry and selected static annotated frames only if the chosen model supports them.

## E3. Structured tool protocol

Allowed virtual tools:

```text
inspect_failure(failure_id, fields, time_window)
get_design(design_id)
get_telemetry_summary(run_id, features)
propose_hypotheses(failure_id, hypotheses[])
propose_interventions(design_id, patches[])
validate_patch(design_id, patch)
run_counterfactual(experiment_spec)
compare_runs(run_ids[], metrics[])
update_hypothesis(hypothesis_id, evidence)
save_transferable_lesson(lesson)
request_additional_probe(kind, limits)
```

All tool calls pass through deterministic authorization, bounds checking, budget management and schema validation.

## E4. Agent loop pseudocode

```python
async def investigate_and_redesign(case_id, budget):
    case = load_failure_case(case_id)
    evidence = compute_physics_features(case)
    hypotheses = await nemotron.generate_hypotheses(evidence)
    hypotheses = validate_hypotheses(hypotheses)

    while budget.can_run_more() and not validated_goal_reached(case):
        candidates = await nemotron.propose_testable_interventions(
            evidence=evidence,
            hypotheses=hypotheses,
            valid_parameter_ranges=design_constraints(case.design),
            prior_lessons=retrieve_applicable_lessons(case),
        )
        candidates = validate_and_deduplicate(candidates)
        if not candidates:
            return stop_as_unresolved("No valid experiment")

        experiment = select_candidate_with_controls(candidates, budget)
        outcomes = await simulator.run_matched_experiments(experiment)
        verification = independent_verifier.evaluate(outcomes)
        store_evidence_and_prediction_vs_observation(experiment, verification)
        budget.charge(outcomes)

        hypotheses = await nemotron.update_beliefs(
            prior=hypotheses, observed=verification,
        )
        evidence = update_case_summary(evidence, verification)

        if verification.meets_acceptance_criteria:
            candidate_design = apply_verified_patch(case.design, experiment.patch)
            return register_accepted_design(candidate_design, verification)

    return stop_as_unresolved("Budget exhausted or no validated improvement")
```

**Key nuance:** This is an orchestrated LLM decision loop, not a claim that the foundation model itself changes its weights after every failure. Learning may occur in external memory, controller training and separately trained surrogate models.

## E5. Error handling and safety

- Invalid output → JSON/Pydantic error → one bounded repair attempt; otherwise fallback.
- Nonsensical physics proposal → reject with explicit constraint violation.
- Contradictory hypotheses → ask for discriminating measurement or experiment.
- No reliable explanation → record `UNKNOWN` and use safe broad search.
- API outage → pause autonomous investigation, retain state, offer manual/classical controls.
- Model budget exceeded → stop in a resumable state; no surprise spend.
- Long experiment → stream job progress; user can cancel and resume.

---

# 11. Workstream F — Counterfactual Arena and verified redesign

## F1. Experiment types

1. **Control (original design and controller)**.
2. **Controller-only**: change one bounded control parameter/set.
3. **Morphology-only**: change one bounded mass, geometry or actuator parameter.
4. **Joint redesign**: morphology + controller with fair retraining budget.
5. **Diagnostic perturbation**: vary friction, external push or load to distinguish mechanisms.
6. **Negative control**: a plausible but irrelevant intervention.
7. **Stress test**: held-out terrain, random initial state and disturbance.

## F2. Experimental fairness

- Same source state / matched seeds / physics version.
- Pre-declared metric thresholds.
- Identical simulation evaluation budgets per candidate arm.
- If some candidates are allowed policy retraining, compare with matched retraining baselines.
- Same rollout horizons, number of seeds and terrain difficulty distributions.
- Separate exploratory runs from final held-out evaluation.
- Maintain run provenance from design revision to every telemetry artifact.

## F3. Auto-redesign patch types

```text
morphology.segment_length
morphology.segment_mass
morphology.inertia / geometry-derived inertia
morphology.foot_length / width / contact geometry
morphology.joint_position / range / damping
actuator.max_torque / gear_ratio (within constraint)
controller.kp / kd / gain schedule
controller.stride_duration / step_height / phase
controller.target_joint_angles / oscillator_params
environment.terrain / friction / external_disturbance  # diagnostic, not a claimed robot repair
```

Changes must include absolute/relative limits and physical validation. Reject interventions violating declared design constraints or modifying evaluator internals.

## F4. Counterfactual outcome view

For every proposal show:

- Before/after robot (same camera and starting pose).
- Changed parameters highlighted.
- Predicted qualitative effect and expected direction.
- Actual metric deltas, robust aggregate and variability.
- Constraint pass/fail.
- Whether the hypothesized cause gained or lost support.
- Link to raw logs and replay.

## F5. Acceptance criteria

- [ ] A single click displays synchronized original and modified simulations from matched conditions.
- [ ] No candidate is accepted without successful verification.
- [ ] Model-proposed changes and baseline optimizer candidates are evaluated with identical physics.
- [ ] Failed experiments remain accessible and inform the evidence history.
- [ ] Rollback and reproducibility work end-to-end.

---

# 12. Workstream G — Lifelong experience and transfer learning

## G1. Lesson representation

A transferable lesson is **not** a loose natural-language memory. Use a structured record:

```text
Lesson {
  source_morphology_descriptor,
  environment_conditions,
  observed_failure_signature,
  hypotheses_tested,
  intervention_patch,
  predicted_effect,
  measured_effect,
  evaluation_seeds,
  constraints,
  confidence_and_limits,
  known_failures_or_negative_transfer,
  source_run_and_report_refs,
}
```

Store unsuccessful interventions as counterexamples. Keep machine-readable design/state descriptors plus a human-readable explanation.

## G2. Applicability mechanism

1. Retrieve candidate lessons using normalized morphology, failure and terrain descriptors.
2. Check hard preconditions (e.g., existence of a foot/contact mode, actuator type).
3. Estimate applicability / uncertainty from task similarity and previous transfer outcomes.
4. Where ambiguity remains, select a cheap diagnostic probe rather than blindly applying the fix.
5. Test a transferred intervention under matched conditions.
6. Record positive and **negative transfer** to improve future retrieval/policy.

Do not claim the model has acquired general physical laws unless performance generalizes across substantial held-out classes and the specific mechanism is validated.

## G3. Transfer experiment

- Dataset contains train families and **held-out morphology variants**.
- Compare no memory, naive nearest-neighbor lesson application, verified applicability screening, and optionally learned ranker.
- Match **physics experiment budget** across arms; report LLM and compute costs separately.
- Measure target reach time, fraction of harmful transfers, verified success rate and calibration.
- **Ablation:** disable applicability checking; disable negative-example retrieval; disable active probes.

## G4. Optional learned intervention surrogate

Input: morphology vector / graph encoding + controller/environment state + failure features + candidate patch.  
Output: predicted performance delta and uncertainty (or distribution) per metric.

Viable first models:

- Gradient-boosted decision trees or ensemble regression on fixed-size descriptors.
- Small MLP ensemble with normalized features.
- Graph neural network / morphology encoder for variable-topology robots (advanced).

Train on held-out historical experiments and calibrate predictions. Never use predicted success instead of actual MuJoCo verification. Under dataset shift, uncertainty should increase and the tool should ask for more simulation evidence.

**Clarification:** A learned *surrogate* is not itself proof that the system has learned Newtonian physics. It approximates outcome trends within a bounded training domain.

## G5. Knowledge Library UI

- Search lessons by failure, terrain, body shape and intervention.
- Evidence-backed design heuristics, with scope and exceptions.
- Transfer experiment preview: "similar failure, different actuator constraints".
- Explicit "not applicable" and "needs experiment" decisions.
- Show provenance, counts, failures, uncertainty and cost of finding the lesson.

---

# 13. Workstream H — NVIDIA physical AI extensions / high-performance learning

## H1. NVIDIA Isaac Lab / Isaac Sim adapter

Purpose: large-scale robot policy learning, sensor-rich scenes and optional photorealistic rendering/advanced simulation.

- Define backend-independent `SimulationBackend` contract.
- Preserve primary MuJoCo ground truth for the core demo and research baselines.
- Implement conversion/import path only for a **validated subset** of MJCF/URDF/scene parameters.
- Run cross-backend comparisons and note differences in contact models/solvers; do not assume numerical equivalence.
- Require GPU compatibility, license review and reliable deployment prior to enabling this in the public product.

## H2. NVIDIA Cosmos integration (conditional)

Possible uses **if model and endpoint are currently available and licensed**:

- Visual interpretation of simulation snapshots as a second opinion on contact/events.
- Explain physical scenes to a nontechnical user.
- Optional cinematic depiction / scene styling, clearly separate from truth-bearing simulation.
- Generate suggestions for environment diversity—not authoritative physics trajectories.

**Never:** treat generated video as rigid-body simulation; derive quantitative forces from AI video without independent estimation and validation; hardcode retired model IDs from historical Nebius examples.

## H3. Parallelism and Nebius Cloud

- Batch independent simulation jobs, with deterministic seed schedules.
- Optional Nebius AI Cloud Serverless Jobs for long-running evaluation and training; confirm current product availability, regions, billing, quotas and container limits.
- Store results in immutable artifacts with job hashes and idempotent execution IDs.
- Schedule expensive PPO training as background tasks with resume/checkpoints and maximum runtime limits.
- Stream status via WebSocket/SSE but keep the web server independent from workers.

## H4. Optional camera/sensing physical AI

Add simulated IMU, tactile contact and camera modalities; compare state-based vs noisy-sensor diagnosis. Requires data-quality audit, latency accounting and a suitable model. Do not displace the actual physics-grounded investigation work.

---

# 14. Workstream I — Product UX, interaction, and visualization

## I1. Navigation architecture

1. **Forge Studio** — design robot and choose movement goal.
2. **Arena** — watch current test, obstacles, disturbances, speed, overlays.
3. **Autopsy** — forensic failure timeline and hypothesis inspector.
4. **Counterfactual Lab** — synchronized experiment comparisons.
5. **Evolution** — lineage tree / Pareto front / generations.
6. **Knowledge Vault** — transferable lessons and provenance.
7. **Benchmarks** — no-nonsense evaluation vs baselines.
8. **Reports** — exports, saved projects, shareable replays.
9. **Compute Console** — model/worker status, usage, quotas, errors.

## I2. Main workflow UX

```text
HOME → Create / Remix Creature
     → Select challenge and constraints
     → Run / Train
     → Detect failure and open Autopsy
     → Generate testable hypotheses
     → Launch Counterfactual Arena
     → Verify best candidate
     → Accept redesign / continue experimenting
     → Save lesson / transfer / export
```

A new user should see a visually exciting result **before** encountering advanced settings, while an expert can drill down into telemetry and methodology.

## I3. Signature interactions

- **Bring to Life** — instantiate anatomy and run authentic physics.
- **Break My Robot** — user introduces a safe, bounded fault / environment perturbation unknown to the investigator.
- **Why Did It Fall?** — freeze and inspect failure frames with evidence overlays.
- **Run the Hypotheses** — create matched experimental branches.
- **Evolve This Design** — launch one bounded iteration / generation.
- **Teach the Next Creature** — compare transfer memory on/off.
- **Show Me the Proof** — reveal raw state, metrics and replay.
- **Export Design & Report** — download reproducible artifacts.

## I4. Interaction states

Every lengthy process supports `queued`, `running`, `streaming`, `completed`, `failed`, `cancelled` and `resumable`. Show progress based on real job status, not fabricated completion percentages. If jobs run asynchronously, persistence and refresh behavior must be engineered; UI must not pretend the task ran after a worker crash.

## I5. Accessibility and presentation

- Keyboard-accessible controls and readable labels.
- Color is never the sole indicator of success/failure.
- Responsive layout; desktop prioritized for lab UI.
- Contrast-safe dark design, charts with units, tooltips and linked raw metrics.
- Explanations limited and precise; optional expandable technical detail.
- Clear "simulation, not hardware validation" disclaimer.
- Public example project loads without requiring the user's own paid credentials; rate-limit guest compute.

---

# 15. Workstream J — Exports and research artifacts

Users can export:

- Robot description (`robot_design.json`, validated `model.xml` MJCF).
- Controller config and source/checkpoint where permitted.
- Environment seed/config and physics version.
- `telemetry.csv` / compressed arrays.
- Run metrics (`metrics.json`) and experiment manifests.
- Experiment graph and lineage JSON.
- Human-readable engineering report (`report.md`, optional PDF later).
- Before/after simulation video and shareable replay reference.
- Evidence statement with outcome and uncertainty; no fabricated scientific certainties.

Report sections:

1. Objective, design, constraints, simulator fidelity assumptions.
2. Observed failure and decisive telemetry.
3. Hypotheses, uncertainty and competing explanations.
4. Proposed interventions with prediction-before-test.
5. Matched experiment design and actual results.
6. Verification on held-out conditions.
7. Tradeoffs: power, mass, energy, control, robustness.
8. Applicable/non-applicable lessons for future designs.
9. Reproducibility manifest and all compute/model version references.
10. Limitations and next physical validation steps.

---
# 16. Canonical domain model and machine-readable contracts

All core contracts must be centralized and versioned. **No module should define an independent interpretation of the robot schema.** Use Pydantic models on the server and generate TypeScript types / OpenAPI bindings for the UI.

## 16.1 Domain entities

| Entity | Purpose | Required relationships |
|---|---|---|
| `Project` | Owner/guest workspace and default scenario | Has many robots, experiments, reports. |
| `RobotDesign` | Immutable morphology specification and visualization assets | Has parent revision, family and version. |
| `ControllerConfig` | Controller class, parameters and optional policy checkpoint | Compatible with one or more morphology schemas. |
| `EnvironmentConfig` | Terrain, friction, obstacle and perturbation parameters | Used by SimulationRuns and experiment groups. |
| `SimulationRun` | A complete seeded physics rollout | References design, controller, environment, artifacts, metrics. |
| `FailureCase` | A failure event with evidence and alternative causes | References SimulationRun. |
| `Hypothesis` | Testable explanation, predicted observations, uncertainty | References FailureCase and multiple tests. |
| `DesignPatch` | Typed, bounded controller/morphology delta | References parent design/controller. |
| `ExperimentGroup` | Matched control/intervention runs | References hypothesis and run IDs. |
| `VerificationResult` | Independent decision on outcomes/constraints | References experiments, thresholds and algorithm version. |
| `Lesson` | Reusable evidence-backed failure/intervention knowledge | References source verification and applicability rules. |
| `LineageNode` | Evolutionary design change | References one design, controller and parent(s). |
| `TrainingJob` | Optimizer/RL/surrogate run | References inputs, budget, status and checkpoint. |
| `Report` | Immutable human/machine readable result | References all supporting artifacts. |

## 16.2 Example robot design schema

```json
{
  "schema_version": "1.0",
  "design_id": "robot_biped_001",
  "name": "Forward-Tip Biped",
  "family": "biped",
  "units": "SI",
  "anatomy": {
    "symmetry": "bilateral",
    "segments": [
      {"id": "torso", "parent": null, "shape": "capsule", "length_m": 0.55, "radius_m": 0.10, "mass_kg": 5.0},
      {"id": "left_upper_leg", "parent": "torso", "shape": "capsule", "length_m": 0.36, "radius_m": 0.045, "mass_kg": 0.8},
      {"id": "left_lower_leg", "parent": "left_upper_leg", "shape": "capsule", "length_m": 0.34, "radius_m": 0.038, "mass_kg": 0.6}
    ],
    "joints": [
      {"id": "left_hip", "parent": "torso", "child": "left_upper_leg", "type": "hinge", "axis": [0, 1, 0], "limits_rad": [-1.3, 1.3], "damping_nms_per_rad": 0.5, "max_torque_nm": 30.0},
      {"id": "left_knee", "parent": "left_upper_leg", "child": "left_lower_leg", "type": "hinge", "axis": [0, 1, 0], "limits_rad": [-2.0, 0.2], "damping_nms_per_rad": 0.4, "max_torque_nm": 28.0}
    ],
    "contact_materials": {"feet": {"friction_coefficient": 0.8}}
  },
  "design_constraints": {
    "max_total_mass_kg": 12.0,
    "max_total_actuator_torque_nm": 160.0,
    "max_segment_count": 24
  }
}
```

**Illustration only:** This is a partial example, **not** a ready-to-compile complete biped. The production schema/validator must ensure all necessary symmetric links, joint anchors, collision geoms and starting positions are present. Validate units in SI; no silently mixed degrees/radians or centimeters/meters.

## 16.3 Example hypothesis schema

```json
{
  "hypothesis_id": "h_001",
  "failure_case_id": "failure_001",
  "mechanism": "actuator_saturation",
  "statement": "Insufficient hip corrective torque contributes to the forward fall.",
  "supporting_evidence": [
    {"metric": "hip_torque_saturation_fraction", "op": ">", "value": 0.75, "observation_ref": "run_001:telemetry:2.1-2.8"}
  ],
  "contradicting_evidence": [],
  "confidence": {"value": 0.55, "type": "heuristic_not_calibrated"},
  "prediction": {
    "intervention": "increase_available_hip_torque_within_budget",
    "metrics_expected_to_increase": ["time_upright_s", "distance_m"],
    "metrics_expected_to_decrease": ["saturation_fraction"]
  },
  "status": "untested"
}
```

Confidence is explicitly typed so a subjective or heuristic estimate cannot be mistaken for a calibrated probability. Use validated enum values and normalized ranges in actual production code.

## 16.4 Example intervention and experiment schema

```json
{
  "experiment_id": "exp_042",
  "hypothesis_id": "h_001",
  "source_design_id": "robot_biped_001",
  "source_controller_id": "controller_007",
  "interventions": [
    {
      "arm_name": "hip_feedback_adjustment",
      "patches": [
        {"target": "controller.kp.left_hip", "operation": "scale", "value": 1.15}
      ],
      "prediction": "A moderate change to corrective feedback may increase upright duration, if stability is gain-limited."
    },
    {
      "arm_name": "foot_length_adjustment",
      "patches": [
        {"target": "anatomy.foot_length_m", "operation": "scale", "value": 1.10}
      ],
      "prediction": "Longer feet may alter the contact and pitching behavior."
    }
  ],
  "control_arm": "no_patch",
  "seeds": [11, 12, 13, 14, 15],
  "duration_s": 10,
  "verification": {
    "primary_metric": "time_upright_s",
    "minimum_relative_improvement": 0.10,
    "hard_constraints_must_pass": true,
    "held_out_seeds": [101, 102, 103]
  }
}
```

**Important design note:** An actuator-capability increase must not be allowed when it violates the user's declared actuator/mass/cost budget. A patch may be mechanically plausible but inadmissible for that experiment.

## 16.5 Simulation result shape

```text
SimulationResult
  run_id: UUID
  schema_version: string
  started_at_utc: timestamp
  model_version: string
  simulator_version: string
  robot_design_hash: SHA256
  controller_hash: SHA256
  environment_hash: SHA256
  seed: integer
  status: COMPLETED | FAILED_NUMERICS | TIMED_OUT | CANCELLED
  terminated_reason: string | null
  metrics: map[string, number]
  events: FailureEvent[]
  frame_artifact_uri: string
  telemetry_artifact_uri: string
  replay_manifest_uri: string
  wall_seconds: number
  compute_cost_estimate: number | null
```

## 16.6 API surface

REST/SSE/WebSocket endpoints are examples of target contracts, not already deployed services:

```text
POST   /api/v1/projects
GET    /api/v1/projects/{project_id}
POST   /api/v1/robots/validate
POST   /api/v1/robots/compile
POST   /api/v1/projects/{id}/robots
PATCH  /api/v1/robots/{robot_id}                 # creates version, never mutates past runs
POST   /api/v1/robots/parse-text
POST   /api/v1/robots/parse-sketch
POST   /api/v1/simulations
GET    /api/v1/simulations/{run_id}
GET    /api/v1/simulations/{run_id}/telemetry
GET    /api/v1/simulations/{run_id}/replay
POST   /api/v1/failures/{id}/analyze
GET    /api/v1/failures/{id}/hypotheses
POST   /api/v1/experiments
GET    /api/v1/experiments/{id}
POST   /api/v1/experiments/{id}/verify
POST   /api/v1/designs/{id}/accept-verified-patch
POST   /api/v1/learning/optimize-controller
POST   /api/v1/learning/train-policy
POST   /api/v1/learning/train-surrogate
POST   /api/v1/transfer/evaluate
GET    /api/v1/lessons
GET    /api/v1/lineage/{robot_id}
POST   /api/v1/reports/generate
GET    /api/v1/reports/{id}
GET    /api/v1/jobs/{id}
POST   /api/v1/jobs/{id}/cancel
GET    /api/v1/events/stream                   # SSE or WS upgrade
GET    /api/v1/health
GET    /api/v1/capabilities
```

Jobs are authenticated or guest-scoped, rate limited, subject to spending caps, idempotent where possible, and use safe artifact handling.

## 16.7 Data provenance

Each finding must have a traceable chain:

```text
RobotDesign(version/hash)
    → Controller(version/hash)
    → Environment(seed/hash)
    → SimulationRun(raw telemetry)
    → FailureCase(features)
    → Hypothesis(model ID, prompt template version, prediction)
    → ExperimentGroup(control + intervention runs)
    → VerificationResult(metrics, rule version)
    → AcceptedDesign / RejectedPatch
    → TransferableLesson
```

Old artifacts and raw results are immutable; derived metrics may be recomputed under a new metric schema and receive a new verification version.

---

# 17. Benchmarks, scientific methodology and ablations

**Purpose:** Defend the claim that physics-informed investigation contributes something beyond random search, conventional co-optimization and attractive explanations.

## 17.1 Pre-register evaluation scenarios

Before tuning the AI investigator, create a hidden evaluation suite with:

| Group | Examples | What it assesses |
|---|---|---|
| Pitch and balance | Off-center mass, gain deficiency, perturbation | Differential diagnosis; stability corrections. |
| Actuation | Torque limiting, joint saturation, latency | Recognition of actuator constraints. |
| Ground contact | Friction reduction, changed contact pads | Whether agent distinguishes slipping from tipping. |
| Gait geometry | Short foot clearance, stride timing, leg reach | Kinematic vs control reasoning. |
| Novel morphology | Different limb ratios/body mass/layout | Transfer and negative-transfer detection. |
| Ambiguous failures | Similar outward fall with different hidden causes | Informative experiment choice. |
| Healthy controls | Functioning locomotion plus noisy telemetry | Avoid inventing failures. |
| Adversarial constraints | Cannot increase actuator strength / mass | Feasible engineering tradeoffs. |

Start with ~10–15 verified scenarios and expand only when stable. Scenarios must not be solvable by reading hidden labels from file names, environment variables, or raw evaluator metadata provided to the agent.

## 17.2 Comparison arms

Mandatory:

- **B0: Random parameter interventions**, same candidate domain and physics budget.
- **B1: CMA-ES/CEM optimizer** of the same design/controller parameters.
- **B2: Nemotron without structured physics telemetry** (short generic run summary) or a one-shot reasoning baseline.
- **B3: Creature Forge full hypothesis-and-counterfactual loop.**

For advanced features:

- **B4: Full loop without knowledge memory.**
- **B5: Full loop with naive nearest-neighbor memory but no applicability checking.**
- **B6: Full loop with applicable lesson checking and active tests.**
- **B7: Model-based surrogate ranking disabled vs enabled.**

This ablation design tests *why* a performance gain happens rather than attributing every effect to the LLM.

## 17.3 Primary and secondary metrics

**Primary (choose before trials):**

- Repair success rate: fraction reaching pre-specified stability/locomotion threshold without constraint violations.
- Sample efficiency: physics evaluations to reach threshold; report censored failures (did not reach within budget).

**Secondary:**

- Mean/median upright time; forward distance; target-completion fraction.
- Energy consumed per distance; motor saturation time; foot slip; contact load.
- Robustness across multiple seeds, terrain shifts and perturbation sizes.
- False diagnosis rate; hypothesis predictive correctness (directional, not just plausibility).
- Useful/harmful transfer rate; total model/compute cost and wall-clock duration.
- User-facing interpretability (small usability study, if possible).
- Geometric feasibility and physical constraint violation rate.

Report distribution, variance, uncertainty intervals and raw trial counts. Avoid only showing the best run, and don't report invented percent improvements.

## 17.4 Experimental budget and statistical integrity

- Preselect a maximum number of simulator evaluations per scenario for all automated arms.
- Keep LLM calls controlled, and report separate token/cost budgets.
- Use fixed dev seeds and **unseen eval seeds**; do not leak eval failures into agent prompt engineering.
- For policy retraining, match training steps / environment interactions and baseline tuning time.
- Run repeats enough to capture nondeterminism, but don't pretend tiny samples are definitive.
- Show both aggregate results and at least one complete failure case with all rejected interventions.
- Maintain a full changelog when test cases or objective definitions are revised.
- Publish at least a small reproducibility script that generates a comparison table directly from saved manifests.

## 17.5 Identifiability safeguards

- The first apparent explanation may not be identifiable from observation alone.
- Test potentially confounding mechanisms with orthogonal interventions.
- Avoid altering multiple correlated parameters unless the hypothesis explicitly requires a joint experiment.
- Do not use the simulator's injected-fault tag in the investigator prompt.
- Keep separate "found improved design" and "correctly identified cause" metrics.
- Mark a mechanism `SUPPORTED`, not `PROVEN`, unless identification assumptions are clear.

## 17.6 Acceptance targets (engineering gates, not promises)

The implementation team should attempt to satisfy:

- [ ] At least 1 nontrivial blind failure repaired with a real Nemotron-guided causal experiment.
- [ ] At least 3 failure categories demonstrably handled without hardcoded per-scenario actions.
- [ ] At least 2 robot morphologies can complete validated simulation runs.
- [ ] Counterfactual experiments are matched and replayable.
- [ ] Held-out trials are run, including unsuccessful attempts.
- [ ] One benchmark table compares full method against at least 2 meaningful baselines.
- [ ] All official submission artifacts can be reproduced by a fresh checkout.

**Ambitious success target:** meaningful improvement over the strongest matched-budget baseline across held-out scenarios, with qualitative failure understanding and demonstrable transfer. If absent, do not misrepresent the outcome—reframe the product around interpretable experiment design and verified co-design while stating the limitation.

---

# 18. Implementation repository and service boundaries

## 18.1 Proposed monorepo

```text
creature-forge/
├── README.md
├── LICENSE
├── NOTICE.md                     # dependency attribution, if needed
├── .env.example
├── docker-compose.yml
├── Makefile
├── .github/
│   └── workflows/ci.yml
├── docs/
│   ├── PROJECT_SPEC.md
│   ├── architecture.md
│   ├── setup.md
│   ├── methodology.md
│   ├── safety-and-limitations.md
│   ├── submission-checklist.md
│   └── experiments/
├── frontend/
│   ├── src/app/
│   ├── src/components/design-studio/
│   ├── src/components/arena-3d/
│   ├── src/components/failure-autopsy/
│   ├── src/components/counterfactual/
│   ├── src/components/evolution/
│   ├── src/components/knowledge/
│   ├── src/components/benchmark/
│   ├── src/lib/api/
│   ├── src/lib/types/
│   └── tests/
├── backend/
│   ├── app/main.py
│   ├── app/api/
│   ├── app/core/config.py
│   ├── app/core/security.py
│   ├── app/models/             # canonical schemas
│   ├── app/services/orchestrator.py
│   ├── app/services/design_compiler.py
│   ├── app/services/nebius_provider.py
│   ├── app/workers/
│   └── tests/
├── engine/
│   ├── robot_dsl/
│   ├── mujoco_backend/
│   ├── controllers/
│   ├── telemetry/
│   ├── failure_detection/
│   ├── physics_features/
│   ├── hypothesis_engine/
│   ├── counterfactuals/
│   ├── interventions/
│   ├── verification/
│   ├── evolution/
│   ├── rl/
│   ├── surrogate/
│   ├── transfer_memory/
│   └── tests/
├── assets/
│   ├── robot_templates/
│   ├── terrain_templates/
│   └── demo_scenarios/
├── eval/
│   ├── scenarios/
│   ├── hidden_scenarios/
│   ├── baselines/
│   ├── metrics/
│   ├── reports/
│   └── reproduce.py
├── scripts/
│   ├── smoke_test.py
│   ├── generate_demo.py
│   ├── seed_database.py
│   ├── check_model_catalog.py
│   └── package_submission.py
└── artifacts/                 # gitignored generated outputs
```

The exact directory names can be revised; **module boundaries and canonical contracts are the important part**.

## 18.2 Contracts for parallel coding agents

**Physics team contract:**

```python
class SimulationBackend(Protocol):
    def validate_design(self, design: RobotDesign) -> ValidationReport: ...
    def compile_design(self, design: RobotDesign) -> CompiledRobot: ...
    def rollout(self, specification: RunSpec) -> SimulationResult: ...
    def checkpoint(self, run_id: str, at_time_s: float) -> StateSnapshot: ...
    def branch(self, snapshot: StateSnapshot, patch: DesignPatch) -> SimulationResult: ...
```

**AI team contract:**

```python
class InvestigationAgent(Protocol):
    async def analyze(self, case: FailureCase) -> list[Hypothesis]: ...
    async def propose(self, context: InvestigationContext) -> list[ExperimentProposal]: ...
    async def interpret(self, result: VerificationResult) -> HypothesisUpdate: ...
```

**Evaluator contract:**

```python
class ExperimentVerifier(Protocol):
    def verify(self, group: ExperimentGroup) -> VerificationResult: ...
    def compare_baseline(self, run_set: BenchmarkRunSet) -> BenchmarkSummary: ...
```

**Frontend contract:**

```ts
type RunUpdate = {
  runId: string;
  jobStatus: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  percent?: number;    // present only when objectively estimable
  eventType: string;
  payload: unknown;     // validated against per-event type schema
};
```

Each component must have one owner, tests and a frozen interface before multiple coding agents implement against it.

---

# 19. Detailed execution plan: October 12–30, 2026

**Date interpretation:** Norway switches from CEST to CET on October 25. Official submission ends October 30 at 18:00 Oslo local time. Do not confuse 10:00 Pacific with 10:00 Norwegian time.

**Reality check:** The full feature set is likely well beyond a reliable 18-day solo build. This plan preserves *all features in the blueprint* but is organized to maximize delivered capability and avoid spending the deadline on unvalidated integrations. Parallel coding assistants can reduce implementation labor; they do not eliminate hardware constraints, physics errors, scientific testing or merge conflicts.

## 19.1 Phase 0 — October 12–13: Foundation and hard-risk proof

**Objectives**

- Create public/private development repository, license plan, `.env.example` and baseline CI.
- Verify Nebius account, Token Factory key, model listing and **actual Nemotron inference call**.
- Build a MuJoCo biped/hopper model and run a reproducible 10-second rollout headlessly.
- Generate essential telemetry and identify one real fall event.
- Bring up frontend with a viewer showing *recorded* physics frames.

**Exit gate:** Real physics motion, one legitimate failure report, one real Nemotron request, and repeatable setup from clean checkout.

## 19.2 Phase 1 — October 14–16: Minimum scientific loop

**Objectives**

- Create initial Failure Autopsy feature extraction and plots.
- Define 3 typed failure mechanisms and intervention schema.
- Let Nemotron produce multiple falsifiable hypotheses from actual measurements.
- Execute control + morphology or controller patch under matched seeds.
- Verify a proposed improvement independently and save all results.
- Implement one classical optimizer baseline.

**Exit gate:** At least one actual failure → hypothesis → test → verification loop that succeeds or produces a scientifically honest negative result.

## 19.3 Phase 2 — October 17–19: Autonomous engineering loop

**Objectives**

- Close the orchestration loop; add budgets, constraints, safe tool execution and retries.
- Implement morphology parameter patching with automatic recompile/validation.
- Add controller search/tuning as a first-class branch.
- Support second robot template and extra failure categories.
- Add Counterfactual Arena with side-by-side real replay.
- Implement experiment graph and rollback.

**Exit gate:** Real autonomous candidate selection and validated design revision works repeatedly on multiple development cases.

## 19.4 Phase 3 — October 20–23: Research differentiation

**Objectives**

- Add failure memory, negative-example recording, applicability screening and transfer benchmark.
- Add held-out scenario evaluation and stronger baselines.
- Implement bounded evolutionary population and lineage tree.
- Train a lightweight surrogate intervention ranker if dataset volume permits.
- Add preliminary multi-terrain robustness checks.
- Begin advanced controller training on one morphology only if compute permits.

**Exit gate:** Metrics reveal what parts actually improve performance. Held-out failures remain blinded. A credible evaluation report exists.

## 19.5 Phase 4 — October 24–26: Product spectacle and advanced features

**Objectives**

- Polish 3D studio and inspector controls.
- Text-to-creature through typed design DSL; constrained sketch editor / assisted parsing.
- Add Break My Robot interaction, visible progress and live/accelerated simulation labels.
- Add terrain suite and polished comparison presentation.
- Produce experiment reports, shareable replays and export flow.
- **Conditional:** Isaac Lab parallel rollout adapter; Cosmos if access/benefit verified; more topologies/advanced RL.

**Exit gate:** Guest can create, break, investigate, redesign and export without developer intervention. No fake demonstrations.

## 19.6 Phase 5 — October 27–29: Stabilization, evaluation and submission

**Objectives**

- Freeze risky features. Disable incomplete components or mark explicitly experimental.
- Re-run clean install on a separate machine/container.
- Finalize evaluation statistics with known limitations.
- Check hosted judge access, quota policies and operational monitoring through December 15.
- Publicly license source; secret/license scanner; attribution check.
- Record and edit <3 minute video, including >=1 minute live application module operation.
- Complete Devpost entry, project narrative, screenshots, feedback and working links.
- **Submit on October 29** as buffer.

**Exit gate:** Public code, free test access, watchable honest demo, and submitted project.

## 19.7 Daily work principles

- At least one working integration milestone per day.
- Keep `main` green and demonstrable; complex R&D lives on branches.
- Never postpone benchmark instrumentation until the last day.
- Run the same demo scenario after every physics/agent change.
- Freeze APIs, schemas and core model IDs early; changes require migration tests.
- Cut scope by tier when actual capability is blocked; don't replace it with persuasive animation.
- Save reproducible experiment seeds, logs and video material continuously.

---

# 20. Claude Code and Codex operating model

## 20.1 Roles

**Project owner / systems architect (human):**

- Owns scientific validity, design direction, hypothesis constraints, acceptance decisions, and final submission.
- Reviews physics assumptions, security, licensing and experiment fairness.
- Makes final project tradeoffs and manual demo verification.

**Claude Code — primary implementation agent:**

- Builds backend integration, MuJoCo model/compiler, orchestrator, frontend and product UX under contracts.
- Proposes small technical design notes and commits coherent working increments.
- Maintains README and service runbooks.

**Codex — independent implementation and reviewer:**

- Implements independent tests, fixtures, benchmark/evaluation harness, contract and edge-case checks.
- Challenges hypotheses and scientifically questionable calculations.
- Reviews merge requests for broken invariants and subtle schema mismatches.
- May independently implement specific non-overlapping modules in an isolated worktree.

**Do not** instruct coding agents to simply "build the whole app" in one pass. They must implement milestone tickets with observable acceptance tests.

## 20.2 Delegation rules

1. Clone and inspect project; read `docs/PROJECT_SPEC.md` in full.
2. Propose plan with touched files, interfaces, tests, risks and external dependencies.
3. Implement a thin vertical slice, not a parallel mock subsystem.
4. Add unit/integration tests and run them.
5. Include a real simulation/example output when modifying core physics or AI.
6. Record cost, compute requirements, new env vars and data migrations.
7. Open a merge request/commit after green CI; separate feature branches/worktrees.
8. Never force push or alter author/co-author metadata without owner's direction. Use normal Git authorship settings and explicit attribution requirements; do not misrepresent work or falsify records.
9. Never fabricate benchmark results or pretend tests ran when they didn't.
10. Treat any LLM output as untrusted input to a validator, even if generated by the same assistant implementing the code.

## 20.3 Initial epic backlog

| Epic | Tickets | Dependency |
|---|---|---|
| E-01 Physics | Design schema, MJCF generation, rollout, telemetry, snapshots, failure events | None |
| E-02 Controls | Baseline controller, optimization, reward/metric separation | E-01 |
| E-03 Nebius | Credential/config, list models, live inference, schema outputs, costs | None |
| E-04 Diagnosis | Feature extractors, hypothesis schemas, forensic metrics and plots | E-01, E-03 |
| E-05 Experiments | Patches, matched seeds, counterfactuals, verification | E-01, E-02, E-04 |
| E-06 Autonomy | Agent planner, tools, retries, caps, memory of rejected tests | E-03, E-04, E-05 |
| E-07 Frontend | 3D viewer, design studio, timeline, Autopsy, Counterfactual Arena | E-01 contracts |
| E-08 Evolution | Mutation/crossover, population, lineage, Pareto display | E-02, E-05 |
| E-09 Transfer | Lesson store, applicability policy, transfer experiments, surrogate | E-05, E-06 |
| E-10 Advanced | Text/sketch design, RL, Isaac, Cosmos optional, more creatures | Core contracts stable |
| E-11 Evaluation | Hidden scenarios, fair baseline runner, ablations, reports | E-01, E-05 |
| E-12 Product ops | Hosting, auth/rate limits, licenses, CI/CD, submission | Cross-cutting |

## 20.4 First actual prompts to give coding agents

### Claude Code — physics foundation

```text
Read docs/PROJECT_SPEC.md. Implement E-01 as a minimal but complete vertical slice:
Pydantic RobotDesign and RunSpec schemas, one physically valid parameterized
MuJoCo robot, headless deterministic-seeded rollout, structured telemetry,
fall-event detection, and artifact export. Use actual physics state only.
Add pytest unit/integration tests and a runnable CLI smoke test. Pin tested
dependencies. Avoid frontend mock data and avoid claiming unsupported physics.
Do not implement other epics yet. Report the exact run command, known limits,
and evidence the physics engine responds correctly to gravity, friction,
and torque-limit changes.
```

### Codex — independent physics audit and evaluation harness

```text
Read docs/PROJECT_SPEC.md and the E-01 API contracts. Work on a separate
branch/worktree. Implement a blinded, reproducible validation suite that
checks gravitational response, friction sensitivity, torque saturation,
parameter bounds, telemetry units, seed replay, and artifact provenance.
Create two or more hidden failure fixtures. Do not modify the implementation
just to make tests pass; report discrepancies and propose targeted fixes.
Deliver pytest commands and a concise correctness report.
```

### Claude Code — agent integration after E-01

```text
Implement E-03 and the first E-04/E-05 vertical slice. Make one real NVIDIA
Nemotron runtime call to Nebius Token Factory; model ID must be configurable
and discoverable. Feed structured telemetry from a legitimate MuJoCo failure
to the model. Require typed competing hypotheses and bounded controller/
morphology experiment proposals. Run matched control/intervention rollouts,
verify improvement deterministically, and persist actual evidence. Implement
schema rejection and budget stops. No model-authored shell execution.
```

### Codex — causal/benchmark review after E-05

```text
Build a fair, reproducible comparison between random intervention search,
a conventional optimization baseline, and the Nemotron-guided experiment
selection loop. Match physics evaluation budgets, separate controller
retraining effects, hold out seeds, and record ALL trials including failures.
Flag leakage from hidden-fault metadata, false causal claims, and violations
of predefined design constraints. Do not report any win before data exist.
```

---

# 21. Performance, cost and operational targets

These are **targets**, not verified performance claims.

## 21.1 Performance envelopes

- Local interactive rendering target: approximately 30–60 FPS on a normal recent desktop, depending on browser/GPU.
- Physics calculation: scalable from a single simulation to asynchronous batches, with headless option.
- AI latency: show immediate request progress and realistic status; no arbitrary guarantee on model response time.
- Replay: support scrubbing without rerunning physics for every frame.
- Policy optimization: checkpointable and cancellable; no UI blocking on long jobs.
- Transfer memory retrieval: filter bounded metadata before expensive AI reasoning.

## 21.2 Cost controls

Configurable example policy:

```yaml
budget:
  max_concurrent_simulations: 4
  max_autonomous_experiments_per_case: 20
  max_model_calls_per_case: 12
  max_wall_minutes_per_case: 30
  max_daily_guest_compute_minutes: 10
  max_daily_public_ai_requests: 30
  allow_paid_training_jobs: false  # until explicit owner opt-in
```

These are suggested starting limits to tune according to actual capacity. Require per-session budget display, project owner override, hard stop on cloud billing thresholds, cached demos and quotas for public guests.

## 21.3 Runtime observability

- Health endpoint for physics, database, queues, storage and AI provider.
- Metrics: job count/duration, model failures, tokens, cost estimate, simulation instability rate, canceled jobs.
- Structured log spans for all investigation/experiment events.
- Error codes displayed to users without leaking secrets or internal filesystem paths.
- Retain anonymized operational logs only as needed; give users control over project deletion in hosted version.

---

# 22. Security, scientific integrity and reliability

## 22.1 Trust boundaries

- LLM output → schema validation → safe domain-specific tools, **never** arbitrary shell.
- Browser project data → authenticated/guest-scoped API; server validates every edit.
- User sketches/uploads → size/type checks, virus and content checks appropriate to hosting; no direct execution.
- Generated MJCF/XML → sanitized, allowlisted schema and controlled asset references.
- Experiment artifacts → immutable safe paths, no traversal, bounded storage.
- Third-party APIs/models → secrets in environment/provider vault, never committed.

## 22.2 Reliability requirements

- Jobs resumable or explicitly fail with retained partial results.
- Idempotent experiment creation using client job keys.
- Transactional design versioning; no mutation of evidence artifacts.
- Queue resource caps and worker timeout handling.
- Integration tests cover restarted server with ongoing jobs.
- Simulated AI model outage test and clear fallback path.
- Public guest demo has rate limits, cached scenario and transparent provenance.

## 22.3 Scientific honesty requirements

- Never describe a visual overlay as a measurement if inferred or stylized.
- Publish negative findings and performance regressions.
- Disclose hand-authored demo scenarios and injected failures.
- Clearly label precomputed replays vs live investigation.
- Distinguish simulator-generated motion from world-model-generated imagery.
- Distinguish LLM hypothesis generation from learned adaptive surrogate or controller weight training.
- State limits of sim-to-real, solver fidelity and contact models.

---

# 23. Risks, countermeasures and go/no-go gates

| Risk | Severity | Earliest warning sign | Countermeasure |
|---|---|---|---|
| Arbitrary robot morphologies cannot walk | Critical | No stable rollout on simple model | Start with controlled robot families and known baseline controller. |
| Most impressive AI analysis is ungrounded | Critical | Explanations plausible but counterfactuals fail | Force evidence/refutation links; verifier is authoritative; no unsupported causal certainty. |
| AI doesn't outperform conventional search | High | No held-out sample-efficiency gain | Evaluate honest interpretability/diagnosis value; improve intervention selection, not dashboards. |
| RL training consumes deadline | Critical | Unstable policies / unavailable GPU | Use PD/CPG + CEM/CMA-ES core; RL optional independent pipeline. |
| Morphology change invalidates controller | High | New body collapses even when mechanically valid | Fair policy retuning and morphology-conditioned adapters. |
| Sketch parser generates invalid bodies | Medium/high | Repeated MJCF compile errors | Bounded graph grammar, validation and manual correction. |
| MuJoCo vs frontend rendering diverges | Medium | Visible motion doesn't match telemetry | Browser renders authoritative state replay only. |
| Nebius model unavailable / renamed | Critical | 404/model error, retired example | Live model-catalog discovery, configurable fallback to available eligible Nemotron. |
| Cosmos endpoint retired/not suitable | Medium | No current model access or bad physical realism | Separate optional adapter; don't use as dynamics ground truth. |
| Cloud bills escalate | High | Unlimited agents/jobs | Per-session quotas, hard caps, precomputed public examples. |
| Overfitting planted failure demos | Critical | Success on only scripted examples | Held-out seeds/scenarios and hidden evaluation labels. |
| Good physics but poor product | High | CLI-only research scripts at demo time | Functional 3D UI built incrementally alongside engine. |
| Too much frontend polish too early | High | No evidence-producing AI loop | Lock first scientific gate by Oct 16. |
| Public repo license conflicts | High | Unclear model/asset redistribution rights | License and asset audit; source/weights/assets separated. |
| Hosted demo unavailable during judging | High | Expired tokens / quota / shutdown | Free cached demo, monitoring, documented local build through Dec 15. |

### Non-negotiable gates

- **G0 Oct 13:** real MuJoCo rollouts + runtime NVIDIA inference.
- **G1 Oct 16:** one independent hypothesis → intervention → comparison → verification.
- **G2 Oct 19:** two working designs, multiple failure categories and usable counterfactual visualization.
- **G3 Oct 23:** benchmark with at least one meaningful baseline and a blind evaluation case.
- **G4 Oct 27:** feature freeze; accessible working product and reproducible repo.
- **G5 Oct 29:** public submission complete.

If a gate fails, do not fake the capability or rush to claim it; narrow a module, use real recorded physics replays, and keep honest experimental outcomes.

---

# 24. Hackathon pitch, storyboard and presentation assets

## 24.1 Name and positioning

**Creature Forge**  
**Tagline:** *Machines that learn from falling.*  
**Technical subtitle:** *Physics-Grounded Failure Investigation and Autonomous Robot Co-Design.*

**One-sentence pitch:**

> Creature Forge lets anyone design a robot, watch it move in real physics, and use an NVIDIA-powered autonomous engineer to investigate failures, test competing mechanical and control fixes, and evolve a verified better design.

**Potential research extension:** Failure knowledge is stored as applicability-scoped lessons and tested on unfamiliar robot bodies, rather than blindly reused.

## 24.2 Under-three-minute video structure

**0:00–0:15 — Hook:** Strange user-designed robot gets up, attempts course, spectacularly but genuinely falls. Caption: "Most AI systems just try again. What if it knew what to investigate?"  
**0:15–0:40 — Creator experience:** Edit geometry or sketch, press Forge, run.  
**0:40–1:10 — Failure Autopsy:** Freeze-frame actual physics, COM/forces/torques, uncertainty-labeled hypotheses.  
**1:10–1:45 — AI scientist:** Real Nemotron plan on Nebius; show tool calls and test predictions, not fake chat narration.  
**1:45–2:20 — Counterfactual Arena:** Matched original, controller fix, mechanical fix, joint fix run and produce measurable outcomes.  
**2:20–2:40 — Verified redesign:** Improved creature clears same challenge; show independent robustness / constraint results.  
**2:40–2:55 — Evidence and impact:** Baseline benchmark and short engineering value proposition; optional second creature benefits from stored lesson if demonstrated.

**Mandatory interpretation:** At least one minute must show actual key modules operating for a simulation-only Physical AI entry. The complete video should remain under three minutes. No copyrighted music/assets without permission.

## 24.3 Judges' evidence package

- Working free-access demo / installable source.
- Short reproducible benchmark script and clean results table.
- Videos/replays before and after with consistent seeds.
- At least one full experiment trail where a hypothesis is rejected.
- Architecture diagram explaining what runs on Nebius and which NVIDIA model makes decisions.
- Transparent limitations (including any 2D-only or template-only features at submission time).
- Open-source license and dependency attribution.
- Setup instructions for running without expensive external services where possible; clearly document which features require Nebius.

## 24.4 Product impact story

Start with **education and early robotics design exploration**. These are concrete users who can benefit from a transparent digital simulator today. Longer-term robotics R&D tooling is plausible, but real hardware deployment requires model calibration, safety validation and hardware experiments not provided by this hackathon prototype.

**Do not pitch** it as a universal automatic real-world robot factory.

---

# 25. Definition of done

## 25.1 Submission-level DoD

- [ ] Working physical robot simulation with legitimate contact dynamics.
- [ ] NVIDIA open-source model used for meaningful runtime decisions through Nebius.
- [ ] User changes robot design and sees real physical consequences.
- [ ] Failure Autopsy displays measured telemetry and honest uncertainty.
- [ ] AI generates testable hypotheses and proposes bounded changes.
- [ ] Counterfactual Arena executes matched physical tests.
- [ ] Independent verifier accepts or rejects each proposal.
- [ ] At least one genuinely improved robot and honest unsuccessful examples shown.
- [ ] Baseline comparison is reproducible, with evaluation limits disclosed.
- [ ] Interactive, coherent UI with no fake data presented as real.
- [ ] Public reproducible Git repository, license, setup, all required assets.
- [ ] <3 minute YouTube video and >=1 minute of working physical-AI modules.
- [ ] Testing access and English Devpost write-up completed before deadline.

## 25.2 Full-vision DoD

- [ ] All core creator families + bounded free-form topology editing.
- [ ] Text-assisted and sketch-assisted robot creation with manual validation.
- [ ] Parametric and evolutionary robot co-design.
- [ ] Optional RL with reproducible training and controller checkpoints.
- [ ] Multi-terrain autonomous active diagnosis and counterfactual testing.
- [ ] Mass/energy/torque/cost-constrained Pareto optimization.
- [ ] Lifelong memory and applicability-aware transfer between morphologies.
- [ ] Learned surrogate intervention model with calibration and OOD checks.
- [ ] Evolutionary lineage, knowledge vault and shareable engineering reports.
- [ ] 3D arena, observability, concurrent experiments and hosted scalability.
- [ ] Optional Isaac Lab/Cosmos adapter only after measurable utility and verified compatibility.
- [ ] Documented optional physical hardware validation pathway; simulation ≠ deployment approval.

**Product truthfulness:** If full-vision items are not yet implemented, keep them in the roadmap—not in an unqualified "Features" list on Devpost.

---

# 26. Architecture decisions requiring early owner approval

The coding team should create short ADRs (Architecture Decision Records) for these choices and test rather than silently assume them:

1. **3D primary physics vs 2.5D model:** This specification selects MuJoCo 3D physics, but a simple planar biped may be used for first gate to reduce control difficulty. Visual 3D alone does not establish full 3D control.
2. **First reliable morphology:** Hopper or biped? Choose based on stable baseline and meaningful falls, not visual aesthetics only.
3. **Controller baseline:** PD/CPG vs imported open-source policy; verify license, action dimensions and reproducibility.
4. **Morphology patch strategy:** MJCF parameter generation vs `MjSpec` editing; support versioning and model recompilation.
5. **Persistence:** SQLite local + simple jobs vs PostgreSQL + Redis; choose based on public-hosting needs and deadline.
6. **LLM structured calls:** JSON schema mode vs tool calling; validate against live Nemotron endpoint rather than theoretical support.
7. **Surrogate features:** Handcrafted physical descriptor vs GNN; start with statistically defensible cheap baseline.
8. **3D streaming:** Pose arrays + procedural meshes vs pre-rendered frames; prioritize authoritative replay and data size.
9. **Gymnasium / Isaac Lab:** Evaluate existing locomotion controllers and cost before creating new RL infrastructure.
10. **Sketch grammar:** What forms are allowed, max joint count, how annotations convert into joints, and how errors are exposed.

---

# 27. Open research questions

1. **Active diagnostic efficiency:** Can interventions chosen from physically grounded failure features beat generic parameter search in simulation-evaluation count?
2. **Causal faithfulness:** When an AI explanation predicts a directional effect, does a controlled intervention validate that prediction at greater-than-baseline rates?
3. **Morphology–controller tradeoffs:** Under equal optimization budgets, when is changing structure more effective than changing the policy?
4. **Applicability-aware memory:** Can verified lessons transfer without increasing negative transfer on unfamiliar robot bodies?
5. **Uncertainty and abstention:** Can the investigator identify cases where available telemetry is insufficient and choose useful probes?
6. **Constrained co-design:** Can a learned intervention selector find feasible redesigns when obvious solutions violate torque/mass budgets?
7. **Robustness:** Do optimized designs survive unseen terrain and initial-state perturbations, not just ideal scripted runs?
8. **Human explainability:** Do force/COM/torque evidence traces help real users understand robot failure compared with black-box optimization plots?

**Research novelty warning:** These are research questions, not declarations that no one has studied them. Robotics morphology co-design and LLM-guided optimization have prior art. Benchmark results and carefully defined contributions determine novelty.

---

# 28. Reference material and provenance

## 28.1 Official source supplied by project owner

**Nebius × NVIDIA Global AI Hackathon 2026 Official Rules**, supplied as `Innlimt tekst.txt`. Priority sections:

- §§1 and 4 — Dates, project requirements, tracks, model/Nebius rules, submission.
- §4 — Public repository/open-source license, YouTube clip, Physical AI minute-of-modules condition, testing access, language.
- §6 — Two-stage judging and equally weighted criteria.
- §7 — IP rights and ownership.
- §8 — Prizes and multiple-award eligibility.

This specification reflects those supplied rules as of 2026-10-12. Recheck the official rules page immediately before submission because the organizer reserves amendment rights.

## 28.2 Verified technical docs and relevant prior work

- **Nebius Token Factory OpenAI-compatible API:** https://api.tokenfactory.nebius.com/docs
- **Nebius Nemotron catalog (verify actual account access/model IDs):** https://nebius.com/services/token-factory/nemotron
- **Current Nemotron model/inference overview:** https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference
- **Nebius Physical AI Token Factory usage guide:** https://github.com/nebius/nebius-physical-ai/blob/main/docs/workbench/token-factory.md
- **Nebius historical Cosmos quickstart with retirement notice:** https://github.com/nebius/nebius-physical-ai/blob/main/docs/hackathon-cosmos3-reasoner.md
- **MuJoCo code and Python API documentation:** https://github.com/google-deepmind/mujoco/blob/main/doc/python.rst
- **MuJoCo model-editing docs:** https://github.com/google-deepmind/mujoco/blob/main/doc/programming/modeledit.rst
- **NVIDIA Isaac Lab official docs:** https://isaac-sim.github.io/IsaacLab/main/index.html
- **NVIDIA Isaac Lab overview:** https://developer.nvidia.com/isaac/lab
- **MuJoCo Playground (GPU-accelerated learning option):** https://github.com/google-deepmind/mujoco_playground
- **NVIDIA Cosmos overview:** https://docs.nvidia.com/cosmos/latest/introduction.html
- **NVIDIA Cosmos repository/license/limitations:** https://github.com/NVIDIA/cosmos
- **Cosmos generated-video physics limitations (example):** https://huggingface.co/nvidia/Cosmos-Predict2-2B-Video2World
- **RoboMoRe (2025), related prior work:** https://arxiv.org/abs/2506.00276
- **Evolution Gym / evolutionary robot morphology prior art:** https://evolutiongym.github.io/

**No source in this list should be taken as proving an unimplemented Creature Forge capability or guaranteeing model access.** Verify licenses, compatibility and endpoint availability before integrating each technology.

---

# 29. Final instructions to the implementation team

1. **Preserve the complete full-scope vision in this document.** Do not reinterpret ambitious requirements as a tiny toy project simply to make a green checklist.
2. **Build the scientific core before cinematic embellishment:** legitimate physics, accurate telemetry, AI-generated falsifiable hypotheses, verified counterfactuals.
3. **Build the product experience concurrently** after the minimum simulator data contract is stable. Judges must see a coherent tool, not only research scripts.
4. **Implement advanced features modularly.** Sketch creation, multi-creature evolution, PPO, transfer memory and Cosmos/Isaac integrations must never corrupt the working core branch.
5. **Never fabricate model intelligence or experimental success.** A failure result is better than a fake victory.
6. **Keep all interventions bounded and reversible.** Never let an LLM override simulator truth or hard constraints.
7. **Design for blinded evaluation**, not solely for the creator's handpicked demo.
8. **Deliver real reproducibility artifacts** for any performance claim.
9. **Keep the official hackathon rules as release blockers**, including runtime NVIDIA/Nebius usage and video requirements.
10. **Submit what is demonstrably working** and keep the bigger roadmap openly labeled as future development.

> **North star:** Let a judge design a strange robot, watch it fail for a non-obvious physical reason, then watch Creature Forge conduct genuine experiments and transform the robot into a demonstrably better design—while the judge can inspect every reason, measurement and rejected idea behind the outcome.

**End of specification — Creature Forge v1.0**