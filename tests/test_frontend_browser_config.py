import csv
import json

from tests.frontend_harness import (
    BROWSER_CONFIG_PATH,
    INDEX_HTML,
    ROOT,
    run_frontend_script,
    translate_with_frontend,
)
from scripts.domain.branch_config import SUPPORTED_BRANCH_CONFIGS, render_browser_config

ACCEPTANCE = ROOT / "tests" / "fixtures" / "branch_acceptance_examples.tsv"


def test_browser_branch_config_is_generated_from_python_metadata():
    assert BROWSER_CONFIG_PATH.read_text(encoding="utf-8") == render_browser_config()
    assert '<script src="./branch_config.js"></script>' in INDEX_HTML.read_text(
        encoding="utf-8"
    )


def test_source_options_are_rendered_from_browser_branch_config():
    expected = [
        {
            "value": config.branch,
            "textContent": f"{config.label} — {config.site}",
            "selected": config.branch == "en",
        }
        for config in SUPPORTED_BRANCH_CONFIGS
    ]
    script = """
const options = [];
const sourceLang = {
  replaceChildren(...children) { options.push(...children); },
};
const context = {
  console,
  document: {
    createElement() { return { value: "", textContent: "", selected: false }; },
    getElementById(id) {
      if (id === "sourceLang") return sourceLang;
      return { addEventListener() {}, style: {}, value: "", textContent: "" };
    },
  },
  window: { addEventListener() {} },
  navigator: {},
};
vm.createContext(context);
vm.runInContext(frontendScript, context);
context.renderSourceBranchOptions();
console.log(JSON.stringify(options));
"""
    assert json.loads(run_frontend_script(script)) == expected


def test_branch_acceptance_examples_translate_with_committed_dictionaries():
    policy = json.loads(
        (ROOT / "dictionaries" / "jp_tag_policy.json").read_text(
            encoding="utf-8"
        )
    )
    with ACCEPTANCE.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    for row in rows:
        branch = row["branch"]
        dictionary = json.loads(
            (ROOT / "dictionaries" / f"{branch}_to_jp.json").read_text(
                encoding="utf-8",
            )
        )
        deprecated_path = ROOT / "dictionaries" / f"deprecated_{branch}_to_jp.json"
        deprecated = json.loads(deprecated_path.read_text(encoding="utf-8"))
        state = translate_with_frontend(
            dictionary,
            row["input_tags"],
            branch,
            deprecated,
            policy,
        )
        output_tags = state["targetText"].split()
        expected_tags = row["expected_jp_tags"].split()
        assert output_tags == expected_tags, (branch, state)
        if branch == "pt-br":
            assert "pt" in output_tags
            assert "pt-br" not in output_tags
        if branch == "zh-tr":
            assert "zh" in output_tags
            assert "zh-tr" not in output_tags

