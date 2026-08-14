"use strict";

const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const corpusRoot = path.resolve(process.argv[3]);
const branches = JSON.parse(process.argv[4]);
const sampleLimit = 10;

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function arraysEqual(left, right) {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

const indexHtml = fs.readFileSync(path.join(repoRoot, "index.html"), "utf8");
const branchConfig = fs.readFileSync(
  path.join(repoRoot, "branch_config.js"),
  "utf8"
);
const scriptMatch = indexHtml.match(/<script id="app-script">([\s\S]*?)<\/script>/);
if (!scriptMatch) {
  throw new Error("index.htmlのscriptブロックが見つかりません");
}

const elements = {
  targetText: { value: "" },
  logArea: { textContent: "" },
  loadingIndicator: { style: {} },
};
const documentStub = {
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
};
const loadFrontend = new Function(
  "document",
  "window",
  "navigator",
  "console",
  `${branchConfig}
${scriptMatch[1]}
return { doTranslationWithDictionary, tokenizeInputTags };`
);
const frontend = loadFrontend(
  documentStub,
  { addEventListener() {} },
  {},
  console
);

const hasOwn = (object, key) =>
  Object.prototype.hasOwnProperty.call(object, key);

function translate(input, branch, dictionary, deprecated, policy) {
  elements.targetText.value = "";
  elements.logArea.textContent = "";
  frontend.doTranslationWithDictionary(
    dictionary,
    input.trim(),
    branch,
    deprecated,
    policy
  );
  return {
    targetText: elements.targetText.value,
    logArea: elements.logArea.textContent,
  };
}

const summary = {
  pageCount: 0,
  visibleArticleCount: 0,
  uniqueVectorCount: 0,
  checkedVectorCount: 0,
  endToEndVectorCount: 0,
  failureArticleCount: 0,
  failureVectorCount: 0,
  schemaFailureCount: 0,
  intrinsicCollisionCount: 0,
  hintFailureCount: 0,
  branchStats: {},
  samples: [],
};

function addSample(sample) {
  if (summary.samples.length < sampleLimit) {
    summary.samples.push(sample);
  }
}

const policy = readJson(path.join(repoRoot, "dictionaries", "jp_tag_policy.json"));

for (const branch of branches) {
  const pagesDir = path.join(corpusRoot, branch, "pages");
  if (!fs.statSync(pagesDir).isDirectory()) {
    throw new Error(`コーパスのpagesディレクトリがありません: ${pagesDir}`);
  }

  const dictionary = readJson(
    path.join(repoRoot, "dictionaries", `${branch}_to_jp.json`)
  );
  const deprecated = readJson(
    path.join(repoRoot, "dictionaries", `deprecated_${branch}_to_jp.json`)
  );
  const concatenatedHints =
    (policy.concatenated_tag_hints &&
      policy.concatenated_tag_hints[branch]) ||
    {};
  const patterns = new Map();
  const branchStats = {
    pageCount: 0,
    visibleArticleCount: 0,
    uniqueVectorCount: 0,
    checkedVectorCount: 0,
    endToEndVectorCount: 0,
    failureArticleCount: 0,
    failureVectorCount: 0,
    hintFailureCount: 0,
  };

  for (const entry of fs.readdirSync(pagesDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) {
      continue;
    }

    branchStats.pageCount += 1;
    summary.pageCount += 1;
    const metaPath = path.join(pagesDir, entry.name, "meta.json");
    let meta;
    try {
      meta = readJson(metaPath);
    } catch (error) {
      summary.schemaFailureCount += 1;
      addSample({
        type: "invalid_meta",
        branch,
        slug: entry.name,
        error: String(error),
      });
      continue;
    }

    if (
      !Array.isArray(meta.tags) ||
      meta.tags.some((tag) => typeof tag !== "string" || tag.length === 0) ||
      new Set(meta.tags).size !== meta.tags.length
    ) {
      summary.schemaFailureCount += 1;
      addSample({
        type: "invalid_tags",
        branch,
        slug: entry.name,
        tags: meta.tags,
      });
      continue;
    }

    const visibleTags = meta.tags.filter((tag) => !tag.startsWith("_"));
    if (visibleTags.length === 0) {
      continue;
    }

    branchStats.visibleArticleCount += 1;
    summary.visibleArticleCount += 1;
    const key = JSON.stringify(visibleTags);
    const previous = patterns.get(key);
    if (previous) {
      previous.articleCount += 1;
      if (previous.slugs.length < 3) {
        previous.slugs.push(entry.name);
      }
    } else {
      patterns.set(key, {
        tags: visibleTags,
        articleCount: 1,
        slugs: [entry.name],
      });
    }
  }

  branchStats.uniqueVectorCount = patterns.size;
  summary.uniqueVectorCount += patterns.size;
  const joinedOwners = new Map();
  const requiredHintKeys = new Set();
  for (const [key, tags] of Object.entries(concatenatedHints)) {
    const valid =
      Array.isArray(tags) &&
      tags.length > 0 &&
      tags.every((tag) => typeof tag === "string" && hasOwn(dictionary, tag)) &&
      tags.join("") === key &&
      !hasOwn(dictionary, key);
    if (!valid) {
      branchStats.hintFailureCount += 1;
      summary.hintFailureCount += 1;
      addSample({
        type: "invalid_hint",
        branch,
        key,
        tags,
      });
    }
  }
  for (const pattern of patterns.values()) {
    const spacedInput = pattern.tags.join(" ").trim();
    const concatenatedInput = pattern.tags.join("").trim();
    const expectedTags = pattern.tags.flatMap((tag) =>
      tag.trim().split(/\s+/).filter(Boolean)
    );
    const spacedTags = frontend.tokenizeInputTags(
      spacedInput,
      dictionary,
      concatenatedHints
    );
    const recoveredTags = frontend.tokenizeInputTags(
      concatenatedInput,
      dictionary,
      concatenatedHints
    );
    const baselineTags = frontend.tokenizeInputTags(
      concatenatedInput,
      dictionary
    );
    if (!arraysEqual(baselineTags, expectedTags)) {
      requiredHintKeys.add(concatenatedInput);
    }
    const ownerKey = JSON.stringify(expectedTags);
    const previousOwner = joinedOwners.get(concatenatedInput);
    if (previousOwner && previousOwner.ownerKey !== ownerKey) {
      summary.intrinsicCollisionCount += 1;
      addSample({
        type: "intrinsic_collision",
        branch,
        concatenatedInput,
        first: previousOwner,
        second: { ownerKey, slugs: pattern.slugs },
      });
    } else if (!previousOwner) {
      joinedOwners.set(concatenatedInput, {
        ownerKey,
        slugs: pattern.slugs,
      });
    }

    const missingTags = expectedTags.filter(
      (tag) => !hasOwn(dictionary, tag)
    );
    const reasons = [];
    if (missingTags.length > 0) {
      reasons.push("dictionary_missing");
    }
    if (!arraysEqual(spacedTags, expectedTags)) {
      reasons.push("spaced_source_segmentation");
    }
    if (!arraysEqual(recoveredTags, expectedTags)) {
      reasons.push("source_segmentation");
    }
    const spacedState = translate(
      spacedInput,
      branch,
      dictionary,
      deprecated,
      policy
    );
    const concatenatedState = translate(
      concatenatedInput,
      branch,
      dictionary,
      deprecated,
      policy
    );
    branchStats.endToEndVectorCount += 1;
    summary.endToEndVectorCount += 1;
    if (
      spacedState.targetText !== concatenatedState.targetText ||
      spacedState.logArea !== concatenatedState.logArea
    ) {
      reasons.push("translation_state");
    }

    branchStats.checkedVectorCount += 1;
    summary.checkedVectorCount += 1;
    if (reasons.length === 0) {
      continue;
    }

    branchStats.failureVectorCount += 1;
    branchStats.failureArticleCount += pattern.articleCount;
    summary.failureVectorCount += 1;
    summary.failureArticleCount += pattern.articleCount;
    addSample({
      type: "translation_mismatch",
      branch,
      slugs: pattern.slugs,
      representedArticles: pattern.articleCount,
      reasons,
      sourceTags: expectedTags,
      spacedInput,
      spacedTags,
      concatenatedInput,
      baselineTags,
      recoveredTags,
      missingTags,
      spacedState,
      concatenatedState,
    });
  }

  const configuredHintKeys = new Set(Object.keys(concatenatedHints));
  const missingHintKeys = [...requiredHintKeys].filter(
    (key) => !configuredHintKeys.has(key)
  );
  const unexpectedHintKeys = [...configuredHintKeys].filter(
    (key) => !requiredHintKeys.has(key)
  );
  if (missingHintKeys.length > 0 || unexpectedHintKeys.length > 0) {
    const count = missingHintKeys.length + unexpectedHintKeys.length;
    branchStats.hintFailureCount += count;
    summary.hintFailureCount += count;
    addSample({
      type: "hint_coverage",
      branch,
      missingHintKeys: missingHintKeys.slice(0, 10),
      unexpectedHintKeys: unexpectedHintKeys.slice(0, 10),
    });
  }

  summary.branchStats[branch] = branchStats;
}

console.log(JSON.stringify(summary));
