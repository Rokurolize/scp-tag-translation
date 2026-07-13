"""Browser configuration publication command tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.commands.build_browser_config import publish_browser_config
from scripts.domain.branch_config import render_browser_config

ROOT = Path(__file__).resolve().parents[1]


def test_publish_browser_config_writes_rendered_artifact(tmp_path):
    output = tmp_path / "nested" / "branch_config.js"

    publish_browser_config(output)

    assert output.read_text(encoding="utf-8") == render_browser_config()


def test_build_browser_config_help_works_as_module():
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.commands.build_browser_config", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--output" in completed.stdout
