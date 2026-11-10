"""Unknown CLI arguments must fail instead of silently starting the menu."""

import subprocess
import sys
from pathlib import Path

SCOUT = Path(__file__).resolve().parent.parent / "scout.py"


def run_scout(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCOUT), *args],
        capture_output=True,
        text=True,
        input="",
        timeout=120,
    )


def test_unknown_argument_exits_nonzero():
    result = run_scout("--bogus")
    assert result.returncode == 2
    assert "--bogus" in result.stderr


def test_help_recognized_after_other_args():
    result = run_scout("foo", "--help")
    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_version_still_works():
    result = run_scout("--version")
    assert result.returncode == 0
    assert "Scout v" in result.stdout
