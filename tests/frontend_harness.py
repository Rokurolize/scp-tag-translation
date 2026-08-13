import json
import os
import re
import shutil
import subprocess

import pytest

from scripts.infrastructure.data_paths import ROOT
from scripts.domain.branch_config import BRANCH_CONFIG_BY_CODE

INDEX_HTML = ROOT / "index.html"
BROWSER_CONFIG_PATH = ROOT / "branch_config.js"

_FRONTEND_VM_PREAMBLE = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = fs.readFileSync("branch_config.js", "utf8") + "\n" + html.match(/<script>([\s\S]*?)<\/script>/)[1];
"""


def node() -> str:
    executable = shutil.which("node")
    if executable is None:
        if os.environ.get("SCP_ALLOW_MISSING_NODE") == "1":
            pytest.skip(
                "node が見つからないため frontend JS テストを明示的にスキップ"
            )
        pytest.fail(
            "frontend JS tests require Node.js; set SCP_ALLOW_MISSING_NODE=1 "
            "only when intentionally running a Python-only test subset"
        )
    return executable


def frontend_script() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert match is not None, "script ブロックが見つかりません"
    return f"{BROWSER_CONFIG_PATH.read_text(encoding='utf-8')}\n{match.group(1)}"


def run_node(script: str, *, input_text: str | None = None) -> str:
    completed = subprocess.run(
        [node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
        input=input_text,
    )
    return completed.stdout


def run_frontend_script(script: str, *, input_text: str | None = None) -> str:
    return run_node(f"{_FRONTEND_VM_PREAMBLE}\n{script}", input_text=input_text)


def translate_with_frontend(
    dictionary: dict[str, str | None],
    input_text: str,
    source_lang: str,
    deprecated: dict[str, str] | None = None,
    policy: dict | None = None,
) -> dict[str, str]:
    if policy is None:
        copyable_targets = {
            value for value in dictionary.values() if isinstance(value, str)
        }
        copyable_targets.update(
            value for value in (deprecated or {}).values() if isinstance(value, str)
        )
        if source_lang in BRANCH_CONFIG_BY_CODE:
            copyable_targets.add(BRANCH_CONFIG_BY_CODE[source_lang].jp_branch_tag)
        policy = {
            "tags": {
                target: {
                    "copy_allowed_for_translation": True,
                    "use_restricted": False,
                    "edit_restricted": False,
                    "translation_exempt": False,
                    "special_translation_action": None,
                }
                for target in copyable_targets
            },
            "source_tags": {},
        }

    script = r"""
const elements = {
  targetText: { value: "" },
  logArea: { textContent: "" },
  loadingIndicator: { style: {} },
};
const context = {
  console,
  document: {
    getElementById(id) {
      if (!elements[id]) {
        elements[id] = {
          value: "",
          textContent: "",
          style: {},
          addEventListener() {},
        };
      }
      return elements[id];
    },
  },
  window: { addEventListener() {} },
  navigator: {},
};
vm.createContext(context);
vm.runInContext(frontendScript, context);
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
context.doTranslationWithDictionary(
  payload.dictionary,
  payload.inputText,
  payload.sourceLang,
  payload.deprecated,
  payload.policy
);
console.log(JSON.stringify({
  targetText: elements.targetText.value,
  logArea: elements.logArea.textContent,
}));
"""
    output = run_frontend_script(
        script,
        input_text=json.dumps(
            {
                "dictionary": dictionary,
                "inputText": input_text,
                "sourceLang": source_lang,
                "deprecated": deprecated or {},
                "policy": policy,
            },
            ensure_ascii=False,
        ),
    )
    return json.loads(output)
