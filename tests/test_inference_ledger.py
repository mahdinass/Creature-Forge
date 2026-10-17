"""Persistent inference ledger: caps, calibration lines, prices, locking (docs/FORGE_LOOP_CONTRACTS.md section 5.4)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from creature_forge import inference_ledger as il
from creature_forge.inference_ledger import Caps, InferenceLedger
from creature_forge.nebius import BudgetExceeded

FX = Path(__file__).parent / "fixtures" / "forge_ai"
ROOT = Path(__file__).resolve().parents[1]
NANO = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="cf-ledger-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.path = self.dir / "ledger.jsonl"

    def ledger(self, **kw):
        return InferenceLedger(self.path, **kw)

    def lines(self):
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]


class PriceTests(unittest.TestCase):
    def test_known_prices(self):
        self.assertEqual(il.PRICES["nvidia/nemotron-3-super-120b-a12b"], (3e-7, 9e-7))
        self.assertEqual(il.PRICES[ULTRA], (1e-6, 3e-6))
        self.assertEqual(il.PRICES[NANO], (6e-8, 2.4e-7))
        self.assertEqual(il.PRICES["nvidia/Nemotron-3_5-Lightning"], (6e-8, 2.4e-7))
        self.assertEqual((il.PRICES_DATE, il.PRICES_SOURCE), ("2026-10-14", "GET /v1/models"))

    def test_default_caps(self):
        c = Caps()
        self.assertEqual((c.max_requests, c.max_usd, c.inv_max_requests, c.inv_max_tokens), (8000, 30.0, 4, 80_000))


class PathTests(Base):
    def test_explicit_path_wins_then_env_then_default(self):
        other = self.dir / "env.jsonl"
        default = self.dir / "default.jsonl"
        with mock.patch.dict(os.environ, {il.ENV_VAR: str(other)}):
            self.assertEqual(InferenceLedger(self.path, default_path=default).path, self.path)
            self.assertEqual(InferenceLedger(default_path=default).path, other)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(il.ENV_VAR, None)
            self.assertEqual(InferenceLedger(default_path=default).path, default)
            with self.assertRaises(ValueError):
                InferenceLedger()

    def test_creates_parent_directories(self):
        led = InferenceLedger(self.dir / "a" / "b" / "l.jsonl")
        led.reserve(100, 100, NANO, investigation_id="i-1")
        self.assertTrue((self.dir / "a" / "b" / "l.jsonl").exists())


class ReserveSettleTests(Base):
    def test_reserve_then_settle_cost_and_line_format(self):
        led = self.ledger()
        res = led.reserve(2000, 1000, NANO, investigation_id="i-1", purpose="investigation")
        self.assertAlmostEqual(res.worst_case_usd, 2000 * 6e-8 + 1000 * 2.4e-7)
        row = led.settle(res, request_id="r1", prompt_tokens=1800, completion_tokens=600)
        self.assertAlmostEqual(row["cost_usd"], 1800 * 6e-8 + 600 * 2.4e-7)
        for key in ("ts", "request_id", "model", "prompt_tokens", "completion_tokens", "cost_usd", "purpose", "investigation_id"):
            self.assertIn(key, row)
        lines = self.lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["kind"], "reserve")
        s = led.status()
        self.assertEqual(s["requests"], 1)                      # reservation + settlement is ONE request
        self.assertAlmostEqual(s["usd"], row["cost_usd"])
        self.assertEqual(s["tokens"], 2400)

    def test_unsettled_reservation_counts_at_worst_case(self):
        led = self.ledger()
        res = led.reserve(2000, 1000, NANO, investigation_id="i-1")
        s = led.status()
        self.assertEqual(s["requests"], 1)
        self.assertAlmostEqual(s["usd"], res.worst_case_usd)
        self.assertEqual(s["tokens"], 3000)

    def test_failed_request_settled_with_zero_cost_still_counts(self):
        led = self.ledger()
        res = led.reserve(2000, 1000, NANO, investigation_id="i-1")
        led.settle(res, request_id=None, prompt_tokens=None, completion_tokens=None, status="error")
        s = led.status()
        self.assertEqual((s["requests"], s["usd"]), (1, 0.0))

    def test_release_gives_the_reservation_back(self):
        led = self.ledger()
        res = led.reserve(2000, 1000, NANO, investigation_id="i-1")
        led.release(res)
        s = led.status()
        self.assertEqual((s["requests"], s["usd"], s["tokens"]), (0, 0.0, 0))
        self.assertEqual(led.investigation_status("i-1")["requests"], 0)

    def test_new_instance_sees_prior_usage(self):
        a = self.ledger()
        a.settle(a.reserve(100, 100, NANO, investigation_id="i-1"), request_id="x", prompt_tokens=100, completion_tokens=100)
        self.assertEqual(self.ledger().status()["requests"], 1)

    def test_investigation_id_required(self):
        with self.assertRaises(ValueError):
            self.ledger().reserve(100, 100, NANO, investigation_id="")


class CapTests(Base):
    def test_total_request_cap_raises_before_append(self):
        led = self.ledger(caps=Caps(max_requests=3, inv_max_requests=100))
        for i in range(3):
            led.settle(led.reserve(10, 10, NANO, investigation_id=f"i-{i}"), request_id=str(i), prompt_tokens=10, completion_tokens=10)
        n = len(self.lines())
        with self.assertRaises(BudgetExceeded) as cm:
            led.reserve(10, 10, NANO, investigation_id="i-9")
        self.assertIn("request cap", str(cm.exception))
        self.assertEqual(len(self.lines()), n)                  # nothing was reserved

    def test_usd_cap_uses_worst_case(self):
        led = self.ledger(caps=Caps(max_usd=0.01, inv_max_requests=100, inv_max_tokens=10**9))
        # ULTRA: 1000*1e-6 + 2000*3e-6 = 0.007 worst case
        r1 = led.reserve(1000, 2000, ULTRA, investigation_id="i-1")
        with self.assertRaises(BudgetExceeded) as cm:
            led.reserve(1000, 2000, ULTRA, investigation_id="i-2")          # 0.014 > 0.01
        self.assertIn("spend cap", str(cm.exception))
        led.settle(r1, request_id="a", prompt_tokens=100, completion_tokens=100)    # real cost far smaller: headroom returns
        led.reserve(1000, 2000, ULTRA, investigation_id="i-2")

    def test_per_investigation_request_cap(self):
        led = self.ledger()
        for _ in range(4):
            led.settle(led.reserve(10, 10, NANO, investigation_id="i-1"), request_id="r", prompt_tokens=10, completion_tokens=10)
        with self.assertRaises(BudgetExceeded) as cm:
            led.reserve(10, 10, NANO, investigation_id="i-1")
        self.assertIn("i-1", str(cm.exception))
        led.reserve(10, 10, NANO, investigation_id="i-2")        # another investigation is unaffected

    def test_per_investigation_token_cap(self):
        led = self.ledger()
        led.settle(led.reserve(1000, 16000, NANO, investigation_id="i-1"), request_id="r", prompt_tokens=50_000, completion_tokens=20_000)
        with self.assertRaises(BudgetExceeded) as cm:
            led.reserve(5000, 16000, NANO, investigation_id="i-1")      # 70k used + 21k > 80k
        self.assertIn("token cap", str(cm.exception))
        led.reserve(1000, 5000, NANO, investigation_id="i-1")           # 70k + 6k fits

    def test_exactly_at_cap_is_allowed(self):
        led = self.ledger(caps=Caps(max_requests=1, inv_max_tokens=200))
        led.reserve(100, 100, NANO, investigation_id="i-1")
        with self.assertRaises(BudgetExceeded):
            led.reserve(1, 1, NANO, investigation_id="i-2")

    def test_default_totals_cap(self):
        led = self.ledger()
        self.assertEqual(led.caps.max_requests, 8000)
        self.assertEqual(led.caps.max_usd, 30.0)


class PriceRefusalTests(Base):
    def test_unknown_model_refused_before_anything_is_written(self):
        with self.assertRaises(il.UnknownPrice):
            self.ledger().reserve(10, 10, "someone/else-model", investigation_id="i-1")
        self.assertFalse(self.path.exists())

    def test_unknown_price_is_a_budget_error(self):
        self.assertTrue(issubclass(il.UnknownPrice, BudgetExceeded))

    def test_prices_are_injectable(self):
        led = self.ledger(prices={"m": (1e-3, 2e-3)})
        res = led.reserve(10, 5, "m", investigation_id="i-1")
        self.assertAlmostEqual(res.worst_case_usd, 10 * 1e-3 + 5 * 2e-3)
        with self.assertRaises(il.UnknownPrice):
            led.reserve(10, 10, NANO, investigation_id="i-1")

    def test_malformed_price_entry_refused(self):
        for bad in ((1e-6,), "cheap", (-1.0, 1.0), (None, 1.0)):
            led = self.ledger(prices={"m": bad})
            with self.assertRaises(il.UnknownPrice):
                led.reserve(10, 10, "m", investigation_id="i-1")


class CalibrationLineTests(Base):
    def test_calibration_lines_count_toward_totals(self):
        shutil.copy(FX / "calibration_ledger.jsonl", self.path)
        led = self.ledger()
        s = led.status()
        self.assertEqual(s["requests"], 3)
        expect = sum(json.loads(x)["cost_usd"] for x in (FX / "calibration_ledger.jsonl").read_text().splitlines())
        self.assertAlmostEqual(s["usd"], expect)
        self.assertEqual(s["tokens"], 3 * 2900 + 1200 + 2500 + 900)

    def test_calibration_lines_reduce_headroom(self):
        shutil.copy(FX / "calibration_ledger.jsonl", self.path)
        led = self.ledger(caps=Caps(max_requests=4))
        led.reserve(10, 10, NANO, investigation_id="i-1")
        with self.assertRaises(BudgetExceeded):
            led.reserve(10, 10, NANO, investigation_id="i-2")

    def test_calibration_lines_count_for_their_investigation_id(self):
        shutil.copy(FX / "calibration_ledger.jsonl", self.path)
        led = self.ledger()
        self.assertEqual(led.investigation_status("calib-1")["requests"], 3)
        self.assertEqual(led.investigation_status("other")["requests"], 0)

    def test_usd_headroom_after_calibration(self):
        shutil.copy(FX / "calibration_ledger.jsonl", self.path)
        spent = self.ledger().status()["usd"]
        led = self.ledger(caps=Caps(max_usd=spent + 0.001))
        with self.assertRaises(BudgetExceeded):
            led.reserve(1000, 2000, ULTRA, investigation_id="i-1")      # 0.007 worst case > 0.001 headroom

    def test_garbage_lines_are_skipped_and_reported(self):
        self.path.write_text('{"model": "m", "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.5, "investigation_id": "x"}\nnot json\n[1,2]\n\n'
                             '{"truncated": ', encoding="utf-8")
        s = self.ledger().status()
        self.assertEqual((s["requests"], s["skipped_lines"]), (1, 3))
        self.assertAlmostEqual(s["usd"], 0.5)
        self.ledger().reserve(10, 10, NANO, investigation_id="i-1")            # appending after a partial last line must still work
        self.assertEqual(self.ledger().status()["requests"], 2)


class ConcurrencyTests(Base):
    def test_threads_cannot_jointly_overshoot(self):
        caps = Caps(max_requests=20, inv_max_requests=1000, inv_max_tokens=10**9)
        ok, refused = [], []

        def worker(k):
            led = self.ledger(caps=caps)               # separate instances, like separate server components
            for j in range(10):
                try:
                    led.reserve(10, 10, NANO, investigation_id=f"i-{k}")
                    ok.append(1)
                except BudgetExceeded:
                    refused.append(1)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(ok), 20)
        self.assertEqual(len(refused), 60)
        self.assertEqual(sum(1 for x in self.lines() if x.get("kind") == "reserve"), 20)

    def test_processes_cannot_jointly_overshoot(self):
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "from creature_forge.inference_ledger import InferenceLedger, Caps\n"
            "from creature_forge.nebius import BudgetExceeded\n"
            f"led = InferenceLedger({str(self.path)!r}, caps=Caps(max_requests=15, inv_max_requests=1000, inv_max_tokens=10**9))\n"
            "n = 0\n"
            "for j in range(30):\n"
            "    try:\n"
            f"        led.reserve(10, 10, {NANO!r}, investigation_id='p' + sys.argv[1]); n += 1\n"
            "    except BudgetExceeded:\n"
            "        pass\n"
            "print(n)\n")
        procs = [subprocess.Popen([sys.executable, "-c", code, str(k)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for k in range(3)]
        got = []
        for p in procs:
            out, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err)
            got.append(int(out.strip()))
        self.assertEqual(sum(got), 15)
        self.assertEqual(sum(1 for x in self.lines() if x.get("kind") == "reserve"), 15)

    def test_lock_timeout_fails_closed(self):
        led = self.ledger(lock_timeout_s=0.2)
        with il._flock(self.path.with_name(self.path.name + ".lock"), 1.0):
            res = {}                                                  # a second open file in another thread must be refused the lock

            def attempt():
                try:
                    led.reserve(10, 10, NANO, investigation_id="i-1")
                    res["ok"] = True
                except BudgetExceeded as e:
                    res["err"] = e

            t = threading.Thread(target=attempt)
            t.start()
            t.join(timeout=10)
        self.assertIsInstance(res.get("err"), il.LedgerLockTimeout)
        self.assertFalse(self.path.exists())
        led.reserve(10, 10, NANO, investigation_id="i-1")                  # lock released: works again


if __name__ == "__main__":
    unittest.main()
