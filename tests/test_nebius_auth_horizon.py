"""Auth-horizon guard of infra/nebius/forge_cloud.py (2026-10-24 incident: the CLI token expired mid-run and the watchdog
could no longer stop the VM). Pure logic only: no WSL, no Nebius calls."""
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra" / "nebius"))
fc = importlib.import_module("forge_cloud")

H = 3600
NOW = 1_800_000_000


class ParseExpiryTests(unittest.TestCase):
    def test_reads_the_earliest_expires_at_and_ignores_other_lines(self):
        text = "tokens:\n    expires_at: 1792879087\n  other:\n    expires_at: '1792870000'\n    token: abc\n"
        self.assertEqual(fc.parse_expiry(text), 1792870000)

    def test_none_when_absent_or_garbled(self):
        self.assertIsNone(fc.parse_expiry(""))
        self.assertIsNone(fc.parse_expiry("expires_at: soon\n"))

    def test_the_wsl_command_never_selects_the_token_line(self):
        self.assertIn("expires_at", fc._EXPIRY_CMD)
        self.assertNotIn("token", fc._EXPIRY_CMD.replace("expires_at", ""))


class HorizonTests(unittest.TestCase):
    def test_horizon_keeps_margin_and_watchdog_lag(self):
        self.assertEqual(fc.auth_horizon(NOW + 12 * H, NOW), NOW + 12 * H - fc.AUTH_MARGIN_S - fc.WATCHDOG_LAG_S)

    def test_unknown_expiry_fails_closed(self):
        self.assertEqual(fc.auth_clamp_hours(6.0, None, NOW), 0.0)

    def test_clamp(self):
        self.assertEqual(fc.auth_clamp_hours(6.0, NOW + 12 * H, NOW), 6.0)
        self.assertAlmostEqual(fc.auth_clamp_hours(6.0, NOW + 4 * H, NOW), 3.25)
        self.assertLess(fc.auth_clamp_hours(6.0, NOW + 10 * 60, NOW), 0)

    def test_guard_refuses_extend_beyond_horizon_and_clamps_start(self):
        with mock.patch.object(fc, "auth_expiry", return_value=int(fc.time.time()) + 4 * H):
            with self.assertRaises(SystemExit):
                fc.auth_guard(6.0, clamp=False)
            self.assertAlmostEqual(fc.auth_guard(6.0, clamp=True), 3.25, places=2)
            self.assertEqual(fc.auth_guard(2.0, clamp=False), 2.0)
        with mock.patch.object(fc, "auth_expiry", return_value=int(fc.time.time()) + 50 * 60):
            with self.assertRaises(SystemExit):           # < 0.5 h usable: even start refuses
                fc.auth_guard(6.0, clamp=True)
        with mock.patch.object(fc, "auth_expiry", return_value=None):
            with self.assertRaises(SystemExit):
                fc.auth_guard(1.0, clamp=True)


class WatchdogReasonTests(unittest.TestCase):
    def test_stops_on_deadline(self):
        self.assertEqual(fc.watchdog_reason(NOW, NOW - 1, NOW + 12 * H, "RUNNING"), "deadline passed")

    def test_stops_before_auth_expiry_even_with_a_later_deadline(self):
        self.assertEqual(fc.watchdog_reason(NOW, NOW + 5 * H, NOW + fc.AUTH_MARGIN_S - 1, "RUNNING"), "CLI auth expiring")
        self.assertEqual(fc.watchdog_reason(NOW, NOW + 5 * H, NOW + fc.AUTH_MARGIN_S, "STARTING"), "CLI auth expiring")

    def test_no_stop_when_healthy_stopped_or_expiry_unknown(self):
        self.assertIsNone(fc.watchdog_reason(NOW, NOW + 5 * H, NOW + 12 * H, "RUNNING"))
        self.assertIsNone(fc.watchdog_reason(NOW, NOW - 1, NOW, "STOPPED"))
        self.assertIsNone(fc.watchdog_reason(NOW, NOW + 5 * H, None, "RUNNING"))

    def test_the_sv1_incident_would_have_been_stopped_in_time(self):
        # 2026-10-24: token expired 23:43 UTC with the VM RUNNING and a deadline far later; a 15-min watchdog tick
        # at or after expiry - 30 min must request a stop while the token is still valid.
        expiry = NOW
        ticks = [expiry - fc.AUTH_MARGIN_S - 600 + k * fc.WATCHDOG_LAG_S for k in range(4)]
        first = next(t for t in ticks if fc.watchdog_reason(t, expiry + 6 * H, expiry, "RUNNING"))
        self.assertLess(first, expiry)


class ServiceAccountPathTests(unittest.TestCase):
    def test_ctl_prefers_sa_and_falls_back_to_federation(self):
        with mock.patch.object(fc, "sa_config", return_value={"profile": "p", "key_expires_epoch": 2e9}), \
             mock.patch.object(fc, "nebius_sa", return_value="sa-out") as sa, mock.patch.object(fc, "nebius") as fed:
            self.assertEqual(fc.ctl("compute", "instance", "get"), "sa-out")
            fed.assert_not_called()
        with mock.patch.object(fc, "sa_config", return_value={"profile": "p", "key_expires_epoch": 2e9}), \
             mock.patch.object(fc, "nebius_sa", side_effect=SystemExit("denied")), \
             mock.patch.object(fc, "nebius", return_value="fed-out"):
            self.assertEqual(fc.ctl("x"), "fed-out")
        with mock.patch.object(fc, "sa_config", return_value={"profile": "p", "key_expires_epoch": 2e9}), \
             mock.patch.object(fc, "nebius_sa", side_effect=SystemExit("denied")), \
             mock.patch.object(fc, "nebius", side_effect=SystemExit("expired")):
            with self.assertRaises(SystemExit) as cm:
                fc.ctl("x")
            self.assertIn("both auth paths failed", str(cm.exception))
        with mock.patch.object(fc, "sa_config", return_value=None), mock.patch.object(fc, "nebius", return_value="f"):
            self.assertEqual(fc.ctl("x"), "f")

    def test_expired_sa_key_is_refused_without_a_call(self):
        with mock.patch.object(fc, "sa_config", return_value={"profile": "p", "key_expires_epoch": 1}), \
             mock.patch.object(fc.subprocess, "run") as run:
            with self.assertRaises(SystemExit):
                fc.nebius_sa("x")
            run.assert_not_called()

    def test_auth_expiry_uses_the_sa_key_only_when_the_sa_works(self):
        with mock.patch.object(fc, "sa_config", return_value={"profile": "p", "key_expires_epoch": 1794009600}), \
             mock.patch.object(fc, "load", return_value={"instance_id": "i"}), \
             mock.patch.object(fc, "federation_expiry", return_value=123):
            with mock.patch.object(fc, "sa_working", return_value=True):
                self.assertEqual(fc.auth_expiry(), 1794009600)
            with mock.patch.object(fc, "sa_working", return_value=False):
                self.assertEqual(fc.auth_expiry(), 123)

    def test_wait_state_polls_until_stopped(self):
        seq = iter(['{"status": {"state": "STOPPING"}}', '{"status": {"state": "STOPPED"}}'])
        with mock.patch.object(fc, "ctl", side_effect=lambda *a: next(seq)), mock.patch.object(fc.time, "sleep"):
            self.assertEqual(fc.wait_state("i", timeout_s=60), "STOPPED")


if __name__ == "__main__":
    unittest.main()
