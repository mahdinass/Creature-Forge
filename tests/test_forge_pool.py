import os
import time
import unittest
from pathlib import Path

from creature_forge import forge_pool as fp
from creature_forge.forge_pool import ForgePool, InlinePool, configured_workers, get_pool, is_error


class WorkerConfigTests(unittest.TestCase):
    def test_default_and_clamp(self):
        self.assertEqual(configured_workers({}), 6)
        self.assertEqual(configured_workers({"CF_WORKERS": "3"}), 3)
        self.assertEqual(configured_workers({"CF_WORKERS": "0"}), 1)
        self.assertEqual(configured_workers({"CF_WORKERS": "-4"}), 1)
        self.assertEqual(configured_workers({"CF_WORKERS": "99"}), 7)
        self.assertEqual(configured_workers({"CF_WORKERS": "many"}), 6)

    def test_constructor_clamps_too(self):
        self.assertEqual(ForgePool(100).max_workers, 7)
        self.assertEqual(ForgePool(0).max_workers, 1)


class LazinessTests(unittest.TestCase):
    def test_no_process_before_first_use_and_singleton(self):
        pool = ForgePool(2)
        self.assertFalse(pool.started)
        self.assertIsNone(pool._executor)
        a = get_pool()
        self.assertIs(a, get_pool())
        self.assertFalse(a.started)         # creating the singleton starts nothing
        pool.close()

    def test_closed_pool_refuses_work(self):
        pool = ForgePool(2)
        pool.close()
        pool.close()                         # idempotent
        with self.assertRaises(RuntimeError):
            list(pool.imap(len, [{}]))


class ImapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pool = ForgePool(2)

    @classmethod
    def tearDownClass(cls):
        cls.pool.close()

    def test_results_carry_their_index(self):
        jobs = [{}, {"a": 1}, {"a": 1, "b": 2}, {"a": 1, "b": 2, "c": 3}]
        got = dict(self.pool.imap(len, jobs))
        self.assertEqual(got, {0: 0, 1: 1, 2: 2, 3: 3})
        self.assertTrue(self.pool.started)
        self.assertEqual(self.pool.map(len, jobs), [0, 1, 2, 3])

    def test_yields_in_completion_order_not_submission_order(self):
        order = [i for i, _ in self.pool.imap(time.sleep, [1.5, 0.0])]
        self.assertEqual(order, [1, 0])

    def test_job_exception_is_a_value_and_does_not_poison_the_batch(self):
        got = dict(self.pool.imap(int, [{"not": "a number"}, "7"]))
        self.assertTrue(is_error(got[0]))
        self.assertEqual(got[0][0], "error")
        self.assertIn("TypeError", got[0][1])
        self.assertEqual(got[1], 7)

    def test_dead_worker_yields_errors_and_the_pool_recovers(self):
        got = dict(self.pool.imap(os._exit, [1]))
        self.assertTrue(is_error(got[0]), got)
        self.assertIn("worker process died", got[0][1])
        self.assertEqual(dict(self.pool.imap(len, [{"a": 1}])), {0: 1})

    def test_empty_job_list(self):
        self.assertEqual(list(self.pool.imap(len, [])), [])


class InlineTests(unittest.TestCase):
    def test_single_worker_runs_in_process_and_matches_the_interface(self):
        pool = ForgePool(1)
        self.assertEqual(dict(pool.imap(len, [{}, {"a": 1}])), {0: 0, 1: 1})
        self.assertFalse(pool.started)       # inline: no processes at all
        self.assertTrue(is_error(dict(pool.imap(int, [[]]))[0]))
        inline = InlinePool()
        self.assertEqual(inline.map(len, [{}, {"a": 1}]), [0, 1])
        self.assertTrue(is_error(inline.map(int, [[]])[0]))

    def test_module_never_imports_the_heavy_stack(self):
        src = Path(fp.__file__).read_text(encoding="utf-8")
        for heavy in ("import mujoco", "import numpy", "from . import"):
            self.assertNotIn(heavy, src)


if __name__ == "__main__":
    unittest.main()
