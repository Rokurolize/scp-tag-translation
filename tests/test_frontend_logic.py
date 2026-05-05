"""index.html 内の翻訳ロジックの回帰テスト"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
INDEX_HTML = ROOT / "index.html"


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
  {}
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
  {}
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
  { artist: "アートワーク" }
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
  {}
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
    assert "unused (非使用タグ)" in state["logArea"]


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
