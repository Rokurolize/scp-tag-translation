"""index.html 内の翻訳ロジックの回帰テスト"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
import csv

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from branch_config import SUPPORTED_BRANCHES

ROOT = Path(__file__).parent.parent
INDEX_HTML = ROOT / "index.html"
ACCEPTANCE = ROOT / "tests" / "fixtures" / "branch_acceptance_examples.tsv"


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node が見つからないため frontend JS テストをスキップ")
    return node


def _frontend_script() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(r"<script>(.*?)</script>", html, re.DOTALL)
    assert match is not None, "script ブロックが見つかりません"
    return match.group(1)


def _translate_with_frontend(
    dictionary: dict[str, str | None],
    input_text: str,
    source_lang: str,
    deprecated: dict[str, str] | None = None,
    policy: dict | None = None,
) -> dict[str, str]:
    node = _node()
    if policy is None:
        copyable_targets = {
            value for value in dictionary.values() if isinstance(value, str)
        }
        copyable_targets.update(
            value for value in (deprecated or {}).values() if isinstance(value, str)
        )
        source_branch_tags = {
            "cn": "cn",
            "cs": "cs",
            "de": "de",
            "en": "en",
            "es": "es",
            "fr": "fr",
            "int": "int",
            "it": "it",
            "ko": "ko",
            "pl": "pl",
            "pt-br": "pt",
            "th": "th",
            "ua": "ua",
            "vn": "vn",
            "zh-tr": "zh",
        }
        if source_lang in source_branch_tags:
            copyable_targets.add(source_branch_tags[source_lang])
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
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
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
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
        input=json.dumps(
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
    return json.loads(completed.stdout)


def _split_with_frontend(token: str, dictionary: dict[str, str | None]) -> list[str]:
    node = _node()

    match = re.search(
        r"function splitConcatenatedTags\(token, dictionary\) \{.*?\n      /\*\*\n"
        r"       \* コピー機能",
        INDEX_HTML.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert match is not None, "splitConcatenatedTags 関数が見つかりません"
    function_source = match.group(0).rsplit("/**", 1)[0]

    script = "\n".join(
        [
            "const splitDictionaryIndexCache = new WeakMap();",
            function_source,
            (
                "console.log(JSON.stringify(splitConcatenatedTags("
                f"{json.dumps(token)}, {json.dumps(dictionary, ensure_ascii=False)}"
                ")));"
            ),
        ]
    )
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(completed.stdout)


def test_index_script_has_valid_javascript_syntax(tmp_path):
    script_path = tmp_path / "index-script.js"
    script_path.write_text(_frontend_script(), encoding="utf-8")

    subprocess.run([_node(), "--check", str(script_path)], check=True)


def test_split_concatenated_tags_uses_forward_longest_match():
    dictionary = {
        "ab": "AB",
        "abc": "ABC",
        "cd": "CD",
        "d": "D",
    }

    assert _split_with_frontend("abcd", dictionary) == ["abc", "d"]


def test_split_concatenated_tags_backs_off_when_longest_prefix_dead_ends():
    dictionary = {
        "a": "A",
        "ab": "AB",
        "bc": "BC",
    }

    assert _split_with_frontend("abc", dictionary) == ["a", "bc"]


def test_split_concatenated_tags_returns_original_when_unsplittable():
    dictionary = {
        "a": "A",
        "ab": "AB",
        "bc": "BC",
    }

    assert _split_with_frontend("abx", dictionary) == ["abx"]


def test_split_concatenated_tags_handles_empty_dictionary():
    assert _split_with_frontend("anything", {}) == ["anything"]


def test_split_concatenated_tags_handles_long_input_without_recursion_overflow():
    node = _node()

    match = re.search(
        r"function splitConcatenatedTags\(token, dictionary\) \{.*?\n      /\*\*\n"
        r"       \* コピー機能",
        INDEX_HTML.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    assert match is not None, "splitConcatenatedTags 関数が見つかりません"
    function_source = match.group(0).rsplit("/**", 1)[0]

    script = "\n".join(
        [
            "const splitDictionaryIndexCache = new WeakMap();",
            function_source,
            "console.log(splitConcatenatedTags('a'.repeat(12000), { a: 'A' }).length);",
        ]
    )
    completed = subprocess.run(
        [node, "-e", script],
        check=True,
        text=True,
        capture_output=True,
    )
    assert completed.stdout.strip() == "12000"


def test_scp_3352_copied_tag_string_translates_like_spaced_tags():
    dictionary = json.loads(
        (ROOT / "dictionaries" / "en_to_jp.json").read_text(encoding="utf-8")
    )
    deprecated = json.loads(
        (ROOT / "dictionaries" / "deprecated_en_to_jp.json").read_text(
            encoding="utf-8"
        )
    )
    policy = json.loads(
        (ROOT / "dictionaries" / "jp_tag_policy.json").read_text(
            encoding="utf-8"
        )
    )
    spaced = (
        "anomalous-event fire indestructible inscription neutralized "
        "reviewers-spotlight scp structure"
    )
    concatenated = (
        "anomalous-eventfireindestructibleinscriptionneutralized"
        "reviewers-spotlightscpstructure"
    )

    spaced_state = _translate_with_frontend(
        dictionary,
        spaced,
        "en",
        deprecated,
        policy,
    )
    concatenated_state = _translate_with_frontend(
        dictionary,
        concatenated,
        "en",
        deprecated,
        policy,
    )

    assert concatenated_state == spaced_state
    assert concatenated_state["targetText"] == (
        "en 炎 破壊不可能 記述 neutralized 批評者スポットライト scp 構造"
    )


def test_translation_prefers_corpus_boundary_hint_over_greedy_segmentation():
    allowed = {
        "copy_allowed_for_translation": True,
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "special_translation_action": None,
    }
    policy = {
        "tags": {tag: allowed for tag in ("en", "safe", "scp", "彫像")},
        "source_tags": {},
        "concatenated_tag_hints": {
            "en": {
                "safescpsculpture": ["safe", "scp", "sculpture"]
            }
        },
    }
    dictionary = {
        "safe": "safe",
        "scp": "scp",
        "sculpture": "彫像",
        "scpsculpture": None,
    }

    spaced = _translate_with_frontend(
        dictionary,
        "safe scp sculpture",
        "en",
        policy=policy,
    )
    concatenated = _translate_with_frontend(
        dictionary,
        "safescpsculpture",
        "en",
        policy=policy,
    )

    assert concatenated == spaced
    assert concatenated["targetText"] == "en safe scp 彫像"


def test_translation_prefers_exact_dictionary_key_over_boundary_hint():
    allowed = {
        "copy_allowed_for_translation": True,
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "special_translation_action": None,
    }
    policy = {
        "tags": {tag: allowed for tag in ("en", "完全一致", "左", "右")},
        "source_tags": {},
        "concatenated_tag_hints": {"en": {"joined": ["left", "right"]}},
    }
    dictionary = {
        "joined": "完全一致",
        "left": "左",
        "right": "右",
    }

    translated = _translate_with_frontend(
        dictionary,
        "joined",
        "en",
        policy=policy,
    )

    assert translated == {"targetText": "en 完全一致", "logArea": ""}


def test_translation_handles_dictionary_keys_that_shadow_object_prototype():
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
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
context.doTranslationWithDictionary(
  { hasOwnProperty: "所有", x: "X" },
  "hasOwnPropertyx",
  "en",
  {},
  { tags: {
    "所有": { copy_allowed_for_translation: true },
    X: { copy_allowed_for_translation: true },
    en: { copy_allowed_for_translation: true },
  } }
);
console.log(JSON.stringify(elements.targetText.value));
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    assert json.loads(completed.stdout) == "en 所有 X"


def test_translation_handles_json_dictionary_proto_keys():
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
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
context.doTranslationWithDictionary(
  JSON.parse('{"__proto__":"プロト","constructor":"コンスト","x":"X"}'),
  "__proto__constructorx",
  "en",
  {},
  { tags: {
    "プロト": { copy_allowed_for_translation: true },
    "コンスト": { copy_allowed_for_translation: true },
    X: { copy_allowed_for_translation: true },
    en: { copy_allowed_for_translation: true },
  } }
);
console.log(JSON.stringify(elements.targetText.value));
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    assert json.loads(completed.stdout) == "en プロト コンスト X"


def test_translation_deduplicates_replacement_and_direct_outputs():
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
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
context.doTranslationWithDictionary(
  { artist: null, artwork: "アートワーク" },
  "artist artwork artwork",
  "en",
  { artist: "アートワーク" },
  { tags: {
    "アートワーク": { copy_allowed_for_translation: true },
    en: { copy_allowed_for_translation: true },
  } }
);
console.log(JSON.stringify(elements.targetText.value));
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    assert json.loads(completed.stdout) == "en アートワーク"


def test_translation_does_not_emit_source_lang_when_all_tags_are_skipped():
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
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
context.doTranslationWithDictionary(
  { unused: null },
  "missing unused",
  "en",
  {},
  { tags: { en: { copy_allowed_for_translation: true } }, source_tags: {} }
);
console.log(JSON.stringify({
  targetText: elements.targetText.value,
  logArea: elements.logArea.textContent,
}));
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    state = json.loads(completed.stdout)
    assert state["targetText"] == ""
    assert "missing (未定義)" in state["logArea"]
    assert "unused (未対応または非使用タグ)" in state["logArea"]


def test_translation_distinguishes_application_from_explicit_jp_omission():
    omitted = _translate_with_frontend(
        {"genre-tag": None},
        "genre-tag",
        "en",
        policy={
            "tags": {},
            "source_tags": {
                "en": {
                    "genre-tag": {
                        "translation_action": "omit_translation_policy",
                        "reason": "翻訳時は付与不要です。",
                    }
                }
            },
        },
    )
    application = _translate_with_frontend(
        {"new-concept": None},
        "new-concept",
        "en",
        policy={"tags": {}, "source_tags": {}},
    )

    assert omitted["targetText"] == ""
    assert "JPでは付与しない" in omitted["logArea"]
    assert "タグ申請" not in omitted["logArea"]
    assert application["targetText"] == ""
    assert "未訳-new-concept" in application["logArea"]
    assert "タグ申請・確認が必要" in application["logArea"]


def test_translation_keeps_restricted_jp_tag_out_of_copy_field():
    state = _translate_with_frontend(
        {"theme": "テーマ"},
        "theme",
        "en",
        policy={
            "tags": {
                "テーマ": {
                    "copy_allowed_for_translation": False,
                    "use_restricted": True,
                    "edit_restricted": False,
                    "translation_exempt": False,
                    "special_translation_action": None,
                }
            },
            "source_tags": {},
        },
    )

    assert state["targetText"] == ""
    assert "スタッフ許可が必要" in state["logArea"]


def test_translation_copies_restricted_tag_with_translation_exemption():
    allowed = {
        "copy_allowed_for_translation": True,
        "use_restricted": True,
        "edit_restricted": False,
        "translation_exempt": True,
        "special_translation_action": None,
    }
    state = _translate_with_frontend(
        {"featured": "注目記事"},
        "featured",
        "en",
        policy={
            "tags": {
                "注目記事": allowed,
                "en": {
                    **allowed,
                    "use_restricted": False,
                    "translation_exempt": False,
                },
            },
            "source_tags": {},
        },
    )

    assert state["targetText"] == "en 注目記事"
    assert "制限緩和/翻訳によりコピー可能" in state["logArea"]


def test_translation_fails_closed_when_jp_policy_is_missing():
    state = _translate_with_frontend(
        {"scp": "scp"},
        "scp",
        "en",
        policy={},
    )

    assert state["targetText"] == ""
    assert "JPポリシーデータ未読込" in state["logArea"]
    assert "データ不整合" in state["logArea"]


def test_translation_uses_normalized_source_branch_tag():
    state = _translate_with_frontend(
        {"conto": "tale"},
        "conto",
        "pt-br",
    )

    assert state["targetText"] == "pt tale"


def test_translation_does_not_add_source_branch_when_branch_tag_is_translated():
    state = _translate_with_frontend(
        {"原創": "zh", "故事": "tale"},
        "原創 故事",
        "zh-tr",
    )

    assert state["targetText"] == "zh tale"


def test_required_source_options_are_visible():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source_select = re.search(
        r'<select id="sourceLang">(.*?)</select>',
        html,
        re.DOTALL,
    )
    assert source_select is not None

    options = set(re.findall(r'<option value="([^"]+)"', source_select.group(1)))
    required = set(SUPPORTED_BRANCHES)
    assert options == required


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
        state = _translate_with_frontend(
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


def test_stale_dictionary_fetch_does_not_overwrite_newer_empty_input():
    script = r"""
(async () => {
  const fs = require("node:fs");
  const vm = require("node:vm");
  const html = fs.readFileSync("index.html", "utf8");
  const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const elements = {
    sourceLang: { value: "en", addEventListener() {} },
    targetLang: { value: "jp", addEventListener() {} },
    sourceText: { value: "scp", addEventListener() {} },
    targetText: { value: "" },
    logArea: { textContent: "" },
    btnCopy: { addEventListener() {} },
    loadingIndicator: { style: {} },
  };
  let resolveDictionaryFetch;
  const context = {
    console,
    document: {
      getElementById(id) {
        return elements[id];
      },
    },
    window: {
      addEventListener() {},
      location: { protocol: "http:" },
    },
    navigator: {},
    fetch(url) {
      if (url.includes("deprecated_")) {
        return Promise.resolve({ ok: false });
      }
      return new Promise((resolve) => {
        resolveDictionaryFetch = resolve;
      });
    },
  };
  vm.createContext(context);
  vm.runInContext(frontendScript, context);

  context.doTranslate();
  elements.sourceText.value = "";
  context.doTranslate();
  resolveDictionaryFetch({
    ok: true,
    json: () => Promise.resolve({ scp: "scp" }),
  });

  await Promise.resolve();
  await Promise.resolve();
  await new Promise((resolve) => setImmediate(resolve));

  console.log(JSON.stringify({
    targetText: elements.targetText.value,
    logArea: elements.logArea.textContent,
    loadingDisplay: elements.loadingIndicator.style.display,
  }));
})();
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    state = json.loads(completed.stdout)
    assert state == {
        "targetText": "",
        "logArea": "",
        "loadingDisplay": "none",
    }


def test_copy_result_falls_back_when_clipboard_api_rejects():
    script = r"""
(async () => {
  const fs = require("node:fs");
  const vm = require("node:vm");
  const html = fs.readFileSync("index.html", "utf8");
  const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  let execCommandCalled = false;
  const textArea = {
    value: "en scp",
    readonly: true,
    hasAttribute(name) {
      return name === "readonly" && this.readonly;
    },
    removeAttribute(name) {
      if (name === "readonly") {
        this.readonly = false;
      }
    },
    setAttribute(name) {
      if (name === "readonly") {
        this.readonly = true;
      }
    },
    select() {},
  };
  const elements = {
    targetText: textArea,
    logArea: { textContent: "" },
    loadingIndicator: { style: {} },
  };
  const context = {
    console: { error() {}, log() {} },
    document: {
      getElementById(id) {
        return elements[id];
      },
      getSelection() {
        return {
          rangeCount: 0,
          removeAllRanges() {},
          addRange() {},
        };
      },
      execCommand(command) {
        execCommandCalled = command === "copy";
        return true;
      },
    },
    window: { addEventListener() {} },
    navigator: {
      clipboard: {
        writeText() {
          return Promise.reject(new Error("denied"));
        },
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(frontendScript, context);

  context.copyResult();
  await Promise.resolve();
  await Promise.resolve();

  console.log(JSON.stringify({
    execCommandCalled,
    logArea: elements.logArea.textContent,
    readonly: textArea.readonly,
  }));
})();
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    state = json.loads(completed.stdout)
    assert state == {
        "execCommandCalled": True,
        "logArea": "翻訳結果をコピーしました。(fallback)",
        "readonly": True,
    }


def test_copy_result_restores_readonly_when_fallback_copy_throws():
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const textArea = {
  value: "en scp",
  readonly: true,
  hasAttribute(name) {
    return name === "readonly" && this.readonly;
  },
  removeAttribute(name) {
    if (name === "readonly") {
      this.readonly = false;
    }
  },
  setAttribute(name) {
    if (name === "readonly") {
      this.readonly = true;
    }
  },
  select() {},
};
const elements = {
  targetText: textArea,
  logArea: { textContent: "" },
  loadingIndicator: { style: {} },
};
const context = {
  console,
  document: {
    getElementById(id) {
      return elements[id];
    },
    getSelection() {
      return {
        rangeCount: 0,
        removeAllRanges() {},
        addRange() {},
      };
    },
    execCommand() {
      throw new Error("copy failed");
    },
  },
  window: { addEventListener() {} },
  navigator: {},
};
vm.createContext(context);
vm.runInContext(frontendScript, context);

context.copyResult();

console.log(JSON.stringify({
  logArea: elements.logArea.textContent,
  readonly: textArea.readonly,
}));
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    state = json.loads(completed.stdout)
    assert state["logArea"].startswith("コピーに失敗しました: Error: copy failed")
    assert state["readonly"] is True


def test_copy_result_restores_readonly_when_selection_restore_throws():
    script = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync("index.html", "utf8");
const frontendScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const textArea = {
  value: "en scp",
  readonly: true,
  hasAttribute(name) {
    return name === "readonly" && this.readonly;
  },
  removeAttribute(name) {
    if (name === "readonly") {
      this.readonly = false;
    }
  },
  setAttribute(name) {
    if (name === "readonly") {
      this.readonly = true;
    }
  },
  select() {},
};
const elements = {
  targetText: textArea,
  logArea: { textContent: "" },
  loadingIndicator: { style: {} },
};
const context = {
  console: { error() {}, log() {} },
  document: {
    getElementById(id) {
      return elements[id];
    },
    getSelection() {
      return {
        rangeCount: 1,
        getRangeAt() {
          return {};
        },
        removeAllRanges() {
          throw new Error("selection failed");
        },
        addRange() {},
      };
    },
    execCommand() {
      return true;
    },
  },
  window: { addEventListener() {} },
  navigator: {},
};
vm.createContext(context);
vm.runInContext(frontendScript, context);

context.copyResult();

console.log(JSON.stringify({
  logArea: elements.logArea.textContent,
  readonly: textArea.readonly,
}));
"""
    completed = subprocess.run(
        [_node(), "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )

    state = json.loads(completed.stdout)
    assert state == {
        "logArea": "翻訳結果をコピーしました。(fallback)",
        "readonly": True,
    }
