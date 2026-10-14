# Creature Forge: UX redesign plan (branch `feature/creative-redesign`, stacked on `feature/studio-ux-repair`)

## 1. Audit: what is wrong with the current screens

| Screen | Problem | Decision |
|---|---|---|
| Overview | Text first; two dense cards; no picture of the product | Full-bleed real MuJoCo biped (recorded walker replay) with three actions; research detail folded into expandable sections |
| Studio | Works; parameter form + one viewport | Keep logic; becomes **Simulate → Playground**, bigger canvas, fall report in plain language |
| Compare | Works | Keep as **Simulate → Compare** |
| Investigations | Purpose unclear: record lists with R-numbers | **Experiment history**: one sentence of purpose; groups (verified, rejected, invalid, historical) |
| Locomotion | Tables and plots first | **Walking lab**: robot walking first (start vs improved controller), one-line result, statistics behind "Advanced results" |
| AI Investigation | Vertical research document | Cinematic: synchronized robots are the centre, step rail Failure → Evidence → AI proposal → Verification → Verdict, inspector for parameter changes |
| Sketch | Drag-the-joints editor | **Draw**: freehand strokes → deterministic interpretation → preview → simulate; joint handles kept as **Refine** |

## 2. Information architecture

Journey: **Create → Simulate → Investigate** (plus Home and an Advanced results area).

```
Home                      ?tab=overview
Create    Draw | Refine   ?tab=sketch (&mode=refine)
Simulate  Playground | Compare   ?tab=studio | ?tab=compare
Investigate  AI investigation | Walking lab | Experiment history   ?tab=demo | ?tab=locomotion | ?tab=lab
Research  (advanced results, statistics, raw evidence)  inside each page, behind disclosure
```

Every legacy `?tab=` value keeps working; the new top bar groups them, the page shows the sub-views as a segmented control.

## 3. Visual direction (checked against the brief, not the generic dark dashboard)

- **Idea:** a forge workshop. The creature is the only bright object on a graphite stage; colour marks *where you are in the journey*, not decoration.
- Base: ink `#0d1016`, anvil `#161b24`, slate line `#262e3c`, chalk text `#e9edf4`, haze `#8f9aae`.
- Journey accents (they encode information): **Create** ember `#ff7a45`, **Simulate** tide `#3cc9d6`, **Investigate** violet `#9c8cff` (also the existing "model-written" colour). Semantic: ok `#4fd18b`, bad `#ff5d6c`, warn `#f2b441`.
- Type: Bricolage Grotesque (display, variable) + Instrument Sans (body), bundled locally (works offline); tabular numerals for measurements. Sentence case, no all-caps eyebrows.
- One memorable thing per screen (hero walker, drawing canvas, synchronized pair); everything else quiet. Motion only for state changes (stroke appears, skeleton settles, parameter marker slides, outcome bars fill); `prefers-reduced-motion` disables it.
- Review against the brief: the first plan used one accent for everything; revised so each journey stage owns its colour, and the hero is a real simulation rather than a gradient.

## 4. Freehand biped: contract

- Draw strokes in a world-scaled canvas (400 px = 1 m, optional grid/ground/ruler guides). Pen roles: Auto, Torso, Leg, Foot. Undo/redo/erase/clear/zoom/pan; raw strokes are kept and re-editable.
- **Interpretation is deterministic** (`creature_forge/freehand.py`, same strokes → same result): resample → simplify → classify (auto only) → torso (base, top, area → mass), legs (hip, knee = point of maximum bend or arc-midpoint, ankle), feet (toe direction) → body parameters + initial pose.
- Ambiguity is never guessed away: the UI lists what was found, lets the user re-label a stroke, and refuses to simulate until it is resolved.
- **Guided constraints ON** (default): snaps ground, near-vertical legs, near-level feet, near-equal legs; validates against the scientific design bounds; reports each snap; raw drawing untouched.
- **Guided constraints OFF** (experimental): no snapping; validated against wider *sandbox* bounds (finite, positive, compilable, bounded); outcome is **valid** / **questionable but buildable** (simulate it; falling is a result) / **unrepresentable** (exact limitation; optional *Approximate and simulate* with before/after and explicit consent).
- Representable exactly in sandbox: different left/right leg lengths and feet, initial pose (pitch, hip/knee/ankle per leg inside joint ranges), torso mass, friction, torque limit, density. **Mirrored/fixed:** torso *shape* (fixed 0.12 × 0.30 m box; mass follows the drawn area), joint ranges, planar motion, two legs only.
- Scientific bounds (`BOUNDS`) and the registered experiments are untouched; a pinned-hash test guards this.

## 5. Phases

1. Audit and plan (this document).
2. Shell, design system, landing.
3. Freehand sketch, guided toggle, sandbox backend (highest priority).
4. AI Investigation cinematic view, Walking lab, Experiment history.
5. Integration, responsive, screenshots, tests, docs, Draft PR.
