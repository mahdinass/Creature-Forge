"""Exercise the VM supervisor in Linux using command fakes, never a cloud API."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/"scripts/r0_campaign.sh"


@unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("setsid"),
                     "Linux supervisor test; run with existing WSL Python")
class SupervisorTests(unittest.TestCase):
    def exercise(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bins = root/"bin"
            bins.mkdir()
            commands = {
                "sudo": 'printf "%s\\n" "$*" >> "$R0_TEST_LOG"\n'
                        'if [[ "$1" == tee ]]; then /bin/cat >/dev/null; fi\n',
                "cat": 'if [[ "$1" == /var/lib/forge/deadline ]]; then echo "$R0_TEST_DEADLINE"; '
                       'else exec /bin/cat "$@"; fi\n',
                "getconf": 'echo 64\n',
                "git": 'exit 0\n',
                "python": 'if [[ "$2" == run ]]; then\n'
                          ' if [[ "$R0_TEST_MODE" == failure && "$*" == *"3/8"* ]]; then exit 7; fi\n'
                          ' if [[ "$R0_TEST_MODE" == failure ]]; then sleep 30; else sleep 0.2; fi\n'
                          'fi\necho "{}"\n',
            }
            for name, body in commands.items():
                path = bins/name
                path.write_text("#!/usr/bin/env bash\nset -eu\n"+body)
                path.chmod(0o755)
            deadline = str(int(time.time())+600)
            env = {**os.environ, "PATH": str(bins)+":"+os.environ["PATH"],
                   "R0_PYTHON": str(bins/"python"), "R0_TEST_LOG": str(root/"calls"),
                   "R0_TEST_MODE": mode, "R0_TEST_DEADLINE": deadline}
            args = [] if mode == "bad_arguments" else [str(root/"artifacts/out"), deadline]
            result = subprocess.run(["bash", str(SCRIPT), *args], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=12)
            calls = (root/"calls").read_text()
            self.assertIn("tee /var/lib/forge/deadline", calls)
            self.assertIn("/usr/local/sbin/forge-selfstop", calls)
            if mode == "normal":
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((root/"artifacts/out/COMPLETE").exists())
            elif mode == "failure":
                self.assertEqual(result.returncode, 88, result.stderr)
                self.assertFalse((root/"artifacts/out/COMPLETE").exists())
            else:
                self.assertEqual(result.returncode, 79, result.stderr)

    def test_normal_completion_requests_stop(self):
        self.exercise("normal")

    def test_failed_shard_terminates_other_process_groups_and_requests_stop(self):
        self.exercise("failure")

    def test_early_argument_error_requests_stop(self):
        self.exercise("bad_arguments")


if __name__ == "__main__":
    unittest.main()
