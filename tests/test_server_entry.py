from __future__ import annotations

import subprocess
import sys


def test_server_entry_help_works():
    """The console-script is invokable and has --help text mentioning bind options."""
    result = subprocess.run(
        [sys.executable, "-m", "xte_kitchen_server.server_entry", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout
