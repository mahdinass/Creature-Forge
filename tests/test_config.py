import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from creature_forge.config import load_env
from creature_forge.nebius import DEFAULT_BASE_URL, NebiusClient

REPO = Path(__file__).resolve().parents[1]
FAKE_KEY = "unit-test-key-not-real"


def env_file(d: str, text: str) -> Path:
    p = Path(d) / ".env"
    p.write_text(text, encoding="utf-8")
    return p


class DotenvTests(unittest.TestCase):
    def test_loads_when_variable_absent_from_shell(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=True):
            p = env_file(d, f"NEBIUS_API_KEY={FAKE_KEY}\nNEBIUS_BASE_URL=https://example.test/v1/\n")
            self.assertTrue(load_env(p))
            c = NebiusClient()
            self.assertEqual(c.api_key, FAKE_KEY)
            self.assertEqual(c.base_url, "https://example.test/v1")  # trailing slash normalised

    def test_real_environment_wins_over_dotenv(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"NEBIUS_API_KEY": "from-shell"}, clear=True):
            load_env(env_file(d, f"NEBIUS_API_KEY={FAKE_KEY}\n"))
            self.assertEqual(os.environ["NEBIUS_API_KEY"], "from-shell")

    def test_missing_file_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(load_env(Path(d) / "absent.env"))

    def test_blank_values_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch("creature_forge.nebius.load_env"):
            load_env(env_file(d, "NEBIUS_API_KEY=\nNEBIUS_BASE_URL=\n"))
            c = NebiusClient()
            self.assertIsNone(c.api_key)
            self.assertEqual(c.base_url, DEFAULT_BASE_URL)

    def test_explicit_arguments_beat_everything(self):
        with mock.patch.dict(os.environ, {"NEBIUS_API_KEY": "env", "NEBIUS_BASE_URL": "https://env.test/v1"}):
            c = NebiusClient(api_key="explicit", base_url="https://explicit.test/v1")
            self.assertEqual((c.api_key, c.base_url), ("explicit", "https://explicit.test/v1"))

    def test_key_not_in_client_repr(self):
        self.assertNotIn(FAKE_KEY, repr(NebiusClient(api_key=FAKE_KEY)))

    def test_fresh_process_picks_key_up_from_dotenv_only(self):
        """Real subprocess with NEBIUS_* stripped from the shell, reading a temp .env."""
        with tempfile.TemporaryDirectory() as d:
            p = env_file(d, f"NEBIUS_API_KEY={FAKE_KEY}\n")
            env = {k: v for k, v in os.environ.items() if not k.startswith("NEBIUS_")}
            code = ("import sys;from creature_forge.config import load_env;from creature_forge.nebius import NebiusClient;"
                    "load_env(sys.argv[1]);c=NebiusClient();print(c.api_key is not None, c.api_key==sys.argv[2])")
            out = subprocess.run([sys.executable, "-I", "-c", code, str(p), FAKE_KEY], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.stdout.split(), ["True", "True"], out.stderr)

    def test_dotenv_is_gitignored_and_untracked(self):
        ignored = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=REPO).returncode
        self.assertEqual(ignored, 0)
        tracked = subprocess.run(["git", "ls-files", ".env"], cwd=REPO, capture_output=True, text=True).stdout
        self.assertEqual(tracked.strip(), "")


if __name__ == "__main__":
    unittest.main()
