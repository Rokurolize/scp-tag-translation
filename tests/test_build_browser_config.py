"""Browser configuration publication command tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.commands import build_browser_config as browser_config_command
from scripts.commands.build_browser_config import (
    publish_browser_config,
    render_browser_config,
)

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


@pytest.mark.parametrize("error", [OSError("disk full"), ValueError("invalid config")])
def test_main_reports_expected_publication_errors(error, monkeypatch, capsys):
    def fail_publication(_output):
        raise error

    monkeypatch.setattr(sys, "argv", ["build_browser_config.py"])
    monkeypatch.setattr(
        browser_config_command,
        "publish_browser_config",
        fail_publication,
    )

    with pytest.raises(SystemExit) as excinfo:
        browser_config_command.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        f"エラー: ブラウザ設定の生成に失敗しました: {error}\n"
    )
