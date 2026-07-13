"""Keep agent-facing development commands aligned with the package layout."""

from __future__ import annotations

import re
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_GUIDE = ROOT / "CLAUDE.md"
MODULE_COMMAND = re.compile(r"^python -m (scripts\.commands\.[a-z_]+)(?:\s|$)")


def test_agent_guide_uses_existing_command_modules():
    guide = AGENT_GUIDE.read_text(encoding="utf-8")
    modules = {
        match.group(1)
        for line in guide.splitlines()
        if (match := MODULE_COMMAND.match(line))
    }

    assert modules
    assert "python scripts/" not in guide
    assert all(find_spec(module) is not None for module in modules)


def test_agent_guide_names_current_branch_config_source():
    guide = AGENT_GUIDE.read_text(encoding="utf-8")

    assert "`scripts/domain/branch_config.py`" in guide
    assert "`scripts/branch_config.py`" not in guide
