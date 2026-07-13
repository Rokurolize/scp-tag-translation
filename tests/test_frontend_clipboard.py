import json

from tests.frontend_harness import run_frontend_script


def test_copy_result_falls_back_when_clipboard_api_rejects():
    script = r"""
(async () => {
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
    state = json.loads(run_frontend_script(script))
    assert state == {
        "execCommandCalled": True,
        "logArea": "翻訳結果をコピーしました。(fallback)",
        "readonly": True,
    }


def test_copy_result_restores_readonly_when_fallback_copy_throws():
    script = r"""
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
    state = json.loads(run_frontend_script(script))
    assert state["logArea"].startswith("コピーに失敗しました: Error: copy failed")
    assert state["readonly"] is True


def test_copy_result_restores_readonly_when_selection_restore_throws():
    script = r"""
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
    state = json.loads(run_frontend_script(script))
    assert state == {
        "logArea": "翻訳結果をコピーしました。(fallback)",
        "readonly": True,
    }
