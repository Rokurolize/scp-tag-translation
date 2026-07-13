import json

from tests.frontend_harness import run_frontend_script


def test_stale_dictionary_fetch_does_not_overwrite_newer_empty_input():
    script = r"""
(async () => {
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
    state = json.loads(run_frontend_script(script))
    assert state == {
        "targetText": "",
        "logArea": "",
        "loadingDisplay": "none",
    }

