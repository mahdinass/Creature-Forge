"""Reproducibility checks for pre-registered evidence (no network, no credentials).

Two INDEPENDENT questions are kept apart:

A. Historical integrity - are the frozen prompts in a registration file byte-for-byte what was hashed and
   (for Phase 1) sent? `verify_frozen_prompts` re-hashes the stored messages with the documented canonical
   serialization. Platform independent; never regenerates anything.

B. Physics reproducibility - does MuJoCo, on THIS platform, regenerate the registered evidence? Regenerated
   evidence is compared with the evidence embedded in the frozen prompt (`reference_evidence`). The
   comparison is NOT a hash comparison: floating-point libm/SIMD differences between platforms change
   low-order bits, which would change a hash without changing the science.

Tolerance policy (`compare_evidence`)
  * EXACT: key sets, list lengths, strings, booleans, None, integers (seeds, counts, event tables).
    Any change in schema, failure classification, event names/order or contact-transition sequence fails.
  * TOLERANT only for finite floats: |a-b| <= ATOL + RTOL*max(|a|,|b|).
    RTOL=1e-9, ATOL=1e-12. Observed Windows-vs-Linux deviation on the registered Phase 1 scenario: max
    relative 3.9e-14 (see docs/REPRODUCIBILITY.md), i.e. ~4 orders of magnitude of headroom, while 1e-9
    of a metre or radian is far below any physical significance and far below the 1 ms integration step
    (a real change in when a discrete event happens moves a time by >= one step, 1e-3 s, and is caught).
  * Values the evidence publishes rounded to k decimals are compared with the same tolerance; if a raw value
    lies on a rounding boundary the printed value flips by 10^-k and FAILS (reported as a possible
    rounding-boundary flip) - it is never silently accepted.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import dataclass, field

RTOL = 1e-9
ATOL = 1e-12


# --------------------------------------------------------------------------- A. historical integrity

def canonical_json(messages: list[dict]) -> bytes:
    """Documented canonical serialization hashed for prompts: sorted keys, (',', ':') separators, ASCII-escaped
    JSON, UTF-8. Identical to investigator.prompt_hash."""
    return json.dumps(messages, sort_keys=True, separators=(",", ":")).encode()


def prompt_sha256(messages: list[dict]) -> str:
    return hashlib.sha256(canonical_json(messages)).hexdigest()


def verify_frozen_prompts(protocol: dict) -> dict[str, tuple[bool, str, str]]:
    """{variant: (ok, registered_sha256, recomputed_sha256)} from the STORED messages only."""
    out = {}
    for variant, rec in protocol["prompts"].items():
        got = prompt_sha256(rec["messages"])
        out[variant] = (got == rec["sha256"], rec["sha256"], got)
    return out


# --------------------------------------------------------------------------- B. physics reproducibility

def reference_evidence(protocol: dict, variant: str) -> dict:
    """The evidence object exactly as embedded in the frozen user message."""
    user = next(m for m in protocol["prompts"][variant]["messages"] if m["role"] == "user")
    return json.loads(user["content"])["observed_evidence"]


@dataclass
class Comparison:
    structural: list[str] = field(default_factory=list)  # exact-match violations (schema/categorical)
    numeric: list[dict] = field(default_factory=list)  # every float that differs at all
    n_leaves: int = 0

    @property
    def out_of_tolerance(self) -> list[dict]:
        return [d for d in self.numeric if not d["within_tolerance"]]

    @property
    def ok(self) -> bool:
        return not self.structural and not self.out_of_tolerance

    def max_rel(self) -> float:
        return max((d["rel"] for d in self.numeric), default=0.0)

    def failures(self) -> list[str]:
        msgs = list(self.structural)
        for d in self.out_of_tolerance:
            hint = " (possible rounding-boundary flip)" if _looks_like_rounding_flip(d["ref"], d["new"]) else ""
            msgs.append(f"{d['path']}: ref={d['ref']!r} new={d['new']!r} abs={d['abs']:.3e} rel={d['rel']:.3e} "
                        f"> tol(rtol={RTOL}, atol={ATOL}){hint}")
        return msgs


def _looks_like_rounding_flip(a: float, b: float) -> bool:
    for k in range(1, 7):
        if abs(round(a, k) - a) < 1e-12 and abs(round(b, k) - b) < 1e-12:
            return abs(abs(a - b) - 10 ** -k) < 1e-9
    return False


def _is_float(x) -> bool:
    return isinstance(x, float)


def compare_evidence(ref, new, *, rtol: float = RTOL, atol: float = ATOL) -> Comparison:
    cmp = Comparison()

    def walk(r, n, path):
        if isinstance(r, dict) and isinstance(n, dict):
            if set(r) != set(n):
                cmp.structural.append(f"{path}: key sets differ (only-ref={sorted(set(r) - set(n))}, "
                                      f"only-new={sorted(set(n) - set(r))})")
            for k in r:
                if k in n:
                    walk(r[k], n[k], f"{path}/{k}")
        elif isinstance(r, list) and isinstance(n, list):
            if len(r) != len(n):
                cmp.structural.append(f"{path}: list length {len(r)} != {len(n)}")
                return
            for i, (a, b) in enumerate(zip(r, n)):
                walk(a, b, f"{path}[{i}]")
        else:
            cmp.n_leaves += 1
            if type(r) is not type(n):  # also catches int-vs-float and bool-vs-int drift
                cmp.structural.append(f"{path}: type {type(r).__name__} != {type(n).__name__} ({r!r} vs {n!r})")
            elif _is_float(r):
                if not (math.isfinite(r) and math.isfinite(n)):
                    if not (r == n or (math.isnan(r) and math.isnan(n))):
                        cmp.structural.append(f"{path}: non-finite value changed ({r!r} vs {n!r})")
                    return
                if r != n:
                    d = abs(r - n)
                    scale = max(abs(r), abs(n))
                    cmp.numeric.append({"path": path, "ref": r, "new": n, "abs": d,
                                        "rel": d / scale if scale else 0.0,
                                        "within_tolerance": d <= atol + rtol * scale})
            elif r != n:
                cmp.structural.append(f"{path}: {r!r} != {n!r}")

    walk(ref, new, "")
    return cmp


def format_report(cmp: Comparison, label: str) -> str:
    lines = [f"[{label}] leaves={cmp.n_leaves} structural_violations={len(cmp.structural)} "
             f"float_diffs={len(cmp.numeric)} out_of_tolerance={len(cmp.out_of_tolerance)} "
             f"max_rel={cmp.max_rel():.3e} (tolerance rtol={RTOL}, atol={ATOL})"]
    for d in sorted(cmp.numeric, key=lambda d: -d["rel"]):
        lines.append(f"  {'OK ' if d['within_tolerance'] else 'BAD'} rel={d['rel']:.2e} abs={d['abs']:.2e} "
                     f"{d['path']}: {d['ref']!r} -> {d['new']!r}")
    lines += [f"  STRUCTURAL {m}" for m in cmp.structural]
    return "\n".join(lines)


# --------------------------------------------------------------------------- provenance for future experiments

def environment_fingerprint() -> dict:
    """Simulator/dependency/platform versions to record next to any NEW pre-registration. No secrets."""
    import mujoco
    import numpy
    return {"python": platform.python_version(), "mujoco": mujoco.__version__, "numpy": numpy.__version__,
            "platform": platform.platform(), "machine": platform.machine()}


def registration_provenance(messages: list[dict], reference: dict) -> dict:
    """What a NEW pre-registration should record (historical Phase 1 records are not changed to this scheme):
    the immutable prompt actually sent, its hash + serialization, the environment that produced the evidence,
    and independently reproducible reference evidence with the tolerance policy used to compare it."""
    return {"frozen_prompt": {"messages": messages, "sha256": prompt_sha256(messages),
                              "serialization": "json.dumps(messages, sort_keys=True, separators=(',', ':')).encode()"},
            "generated_in": environment_fingerprint(),
            "reference_evidence": reference,
            "evidence_tolerance": {"rtol": RTOL, "atol": ATOL, "exact": "keys, lengths, str, bool, None, int"},
            "replay_rule": "live replay must send frozen_prompt.messages byte-for-byte, or be registered as a new experiment"}
