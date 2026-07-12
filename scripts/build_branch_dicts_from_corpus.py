#!/usr/bin/env python3
"""Build source-branch to JP tag dictionaries from local corpus metadata."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_dict as en_builder
from scripts.atomic_output import publish_files_atomically
from scripts.branch_config import (
    SUPPORTED_BRANCH_CONFIGS,
    SUPPORTED_BRANCHES,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_EN = ROOT / "data" / "en_tags.json"
DATA_JP = ROOT / "data" / "jp_tags.json"
DATA_DEPRECATED = ROOT / "data" / "deprecated_tags.json"
DATA_INT_CROSSWALK = ROOT / "data" / "int_tag_crosswalk.json"
DATA_KO_CROSSWALK = ROOT / "data" / "ko_tag_crosswalk.json"
DATA_BRANCH_GUIDE_CROSSWALK = ROOT / "data" / "branch_guide_crosswalk.json"
OVERRIDES_PATH = ROOT / "sources" / "branch_to_jp_overrides.json"
DEPRECATED_REPLACEMENT_OVERRIDES_PATH = (
    ROOT / "sources" / "deprecated_replacement_overrides.json"
)
DICTIONARIES_DIR = ROOT / "dictionaries"
JP_POLICY_PATH = DICTIONARIES_DIR / "jp_tag_policy.json"

# Compatibility aliases for callers/tests; branch_config.py is the sole source
# of truth shared by generators and the browser UI.
OFFICIAL_BRANCH_SITES: dict[str, str] = {
    config.branch: config.site for config in SUPPORTED_BRANCH_CONFIGS
}
# Compatibility aliases retained for callers/tests. The default build targets
# exactly the 15 sites selected for this translator.
OFFICIAL_BRANCHES: tuple[str, ...] = SUPPORTED_BRANCHES


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=2)
        f.write("\n")


def branch_to_source_lang(branch: str) -> str:
    if branch == "pt-br":
        return "PT"
    if branch == "zh-tr":
        return "ZH"
    return branch.upper()


def source_languages_for_branch(branch: str) -> tuple[str, ...]:
    """Return JP unused-list sections applicable to a source branch.

    SCP-INT pages use EN tags as their base vocabulary, so both the EN and INT
    sections apply.  This is especially important for EN-only operational tags
    such as ``_cc`` and hidden origin tags such as ``_vn``.
    """

    if branch == "int":
        return ("EN", "INT")
    return (branch_to_source_lang(branch),)


def deprecated_policy_for_branch(
    branch: str,
    deprecated_tags: dict[str, set[str]],
    replacements: dict[str, dict[str, str | None]],
) -> tuple[set[str], dict[str, str | None]]:
    applicable: set[str] = set()
    effective: dict[str, str | None] = {}
    for source_lang in source_languages_for_branch(branch):
        applicable.update(deprecated_tags.get(source_lang, set()))
        for source_tag, replacement in replacements.get(source_lang, {}).items():
            existing = effective.get(source_tag)
            if (
                existing is not None
                and replacement is not None
                and existing != replacement
            ):
                raise ValueError(
                    "conflicting inherited replacements: "
                    f"{branch}:{source_tag}->{existing}/{replacement}"
                )
            if replacement is not None or source_tag not in effective:
                effective[source_tag] = replacement
    return applicable, effective


def discover_branches(corpus_root: Path) -> list[str]:
    branches = []
    for branch_dir in sorted(corpus_root.iterdir()):
        if not branch_dir.is_dir():
            continue
        branch = branch_dir.name
        if branch == "jp" or branch.startswith("_"):
            continue
        pages_dir = branch_dir / "pages"
        if not pages_dir.is_dir():
            continue
        if any(pages_dir.glob("*/meta.json")):
            branches.append(branch)
    return branches


def _iter_corpus_page_tags(
    corpus_root: Path,
    branch: str,
) -> Iterator[tuple[str, list[str]]]:
    pages_dir = corpus_root / branch / "pages"
    if not pages_dir.is_dir():
        raise ValueError(f"corpus branch pages directory not found: {pages_dir}")

    for meta_path in sorted(pages_dir.glob("*/meta.json")):
        meta = load_json(meta_path)
        raw_tags = meta.get("tags", [])
        if isinstance(raw_tags, str):
            page_tags = [raw_tags]
        elif isinstance(raw_tags, list):
            if any(not isinstance(tag, str) or not tag for tag in raw_tags):
                raise ValueError(f"invalid tags field in {meta_path}")
            if len(set(raw_tags)) != len(raw_tags):
                raise ValueError(f"duplicate tags in {meta_path}")
            page_tags = raw_tags
        else:
            raise ValueError(f"invalid tags field in {meta_path}")
        yield meta_path.parent.name, page_tags


def collect_corpus_tags_and_visible_sequences(
    corpus_root: Path,
    branch: str,
) -> tuple[set[str], list[tuple[str, tuple[str, ...]]]]:
    tags: set[str] = set()
    visible_sequences = []
    for slug, page_tags in _iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
        visible = tuple(tag for tag in page_tags if not tag.startswith("_"))
        if visible:
            visible_sequences.append((slug, visible))
    return tags, visible_sequences


def corpus_tags_for_branch(corpus_root: Path, branch: str) -> set[str]:
    tags: set[str] = set()
    for _slug, page_tags in _iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
    return tags


def _dictionary_trie(dictionary: dict[str, str | None]) -> dict[Any, Any]:
    root: dict[Any, Any] = {}
    for tag in dictionary:
        node = root
        for character in tag:
            node = node.setdefault(character, {})
        node[None] = True
    return root


def _split_concatenated_tag(
    token: str,
    trie: dict[Any, Any],
) -> tuple[str, ...]:
    can_split = [False] * (len(token) + 1)
    next_end_by_index = [-1] * (len(token) + 1)
    can_split[len(token)] = True

    for index in range(len(token) - 1, -1, -1):
        node = trie
        longest_end = -1
        for end in range(index, len(token)):
            child = node.get(token[end])
            if child is None:
                break
            node = child
            candidate_end = end + 1
            if None in node and can_split[candidate_end]:
                longest_end = candidate_end
        if longest_end != -1:
            can_split[index] = True
            next_end_by_index[index] = longest_end

    if not can_split[0]:
        return (token,)

    result = []
    index = 0
    while index < len(token):
        next_end = next_end_by_index[index]
        result.append(token[index:next_end])
        index = next_end
    return tuple(result)


def _tokenize_without_hints(
    input_text: str,
    dictionary: dict[str, str | None],
    trie: dict[Any, Any],
) -> tuple[str, ...]:
    result = []
    for token in input_text.split():
        if token in dictionary:
            result.append(token)
        else:
            result.extend(_split_concatenated_tag(token, trie))
    return tuple(result)


def build_concatenated_tag_hints(
    corpus_root: Path,
    branch: str,
    dictionary: dict[str, str | None],
    visible_sequences: list[tuple[str, tuple[str, ...]]] | None = None,
) -> dict[str, list[str]]:
    """Build exact boundaries only where generic longest matching is ambiguous."""

    if visible_sequences is None:
        _tags, visible_sequences = collect_corpus_tags_and_visible_sequences(
            corpus_root,
            branch,
        )

    trie = _dictionary_trie(dictionary)
    owners: dict[str, tuple[str, ...]] = {}
    hints: dict[str, list[str]] = {}
    for slug, visible_tags in visible_sequences:
        expected = tuple(
            normalized
            for tag in visible_tags
            for normalized in tag.split()
        )
        concatenated = "".join(visible_tags).strip()
        if not expected or not concatenated:
            continue

        missing_tags = sorted(set(expected).difference(dictionary))
        if missing_tags:
            raise ValueError(
                "corpus tags missing from dictionary during hint generation: "
                f"{branch}:{slug}:{missing_tags!r}"
            )

        existing = owners.get(concatenated)
        if existing is not None and existing != expected:
            raise ValueError(
                "concatenated tag input has multiple corpus boundaries: "
                f"{branch}:{concatenated!r}->{existing!r}/{expected!r}"
            )
        owners[concatenated] = expected

        if concatenated in dictionary and expected != (concatenated,):
            raise ValueError(
                "concatenated tag input conflicts with an exact dictionary key: "
                f"{branch}:{slug}:{concatenated!r}->{expected!r}"
            )

        recovered = _tokenize_without_hints(concatenated, dictionary, trie)
        if recovered == expected:
            continue
        if len(concatenated.split()) != 1:
            raise ValueError(
                "cannot encode a boundary hint containing whitespace: "
                f"{branch}:{concatenated!r}"
            )
        hints[concatenated] = list(expected)

    return dict(sorted(hints.items()))


def complete_hint_dictionaries(
    generated: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, str | None]]:
    complete = dict(generated)
    for branch in SUPPORTED_BRANCHES:
        if branch in complete:
            continue
        path = DICTIONARIES_DIR / f"{branch}_to_jp.json"
        if not path.is_file():
            raise ValueError(
                "existing dictionary required for partial hint generation: "
                f"{path}"
            )
        dictionary = load_json(path)
        if not isinstance(dictionary, dict):
            raise ValueError(f"invalid existing dictionary: {path}")
        complete[branch] = dictionary
    return complete


def jp_maps(jp_tags: list[dict]) -> tuple[set[str], dict[str, str]]:
    jp_names: set[str] = set()
    source_to_jp: dict[str, str] = {}
    for entry in jp_tags:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"invalid JP tag entry: {entry!r}")
        jp_names.add(name)
        for source_tag in en_builder.jp_source_tags(entry):
            existing = source_to_jp.get(source_tag)
            if existing is not None and existing != name:
                raise ValueError(
                    f"source tag maps to multiple JP tags: "
                    f"{source_tag!r}->{existing!r}/{name!r}"
                )
            source_to_jp[source_tag] = name
    return jp_names, source_to_jp


def load_overrides(path: Path, jp_names: set[str]) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    raw = load_json(path)
    if not isinstance(raw, dict):
        raise ValueError("branch override file must be a JSON object")

    overrides: dict[str, dict[str, str]] = {}
    for branch, branch_values in raw.items():
        if not isinstance(branch, str) or not branch:
            raise ValueError(f"invalid override branch: {branch!r}")
        if not isinstance(branch_values, dict):
            raise ValueError(f"override branch must map tags: {branch!r}")
        overrides[branch] = {}
        for source_tag, value in branch_values.items():
            if not isinstance(source_tag, str) or not source_tag:
                raise ValueError(f"invalid override source tag for {branch!r}")
            if isinstance(value, str):
                jp_tag = value
            elif isinstance(value, dict) and isinstance(value.get("jp_tag"), str):
                jp_tag = value["jp_tag"]
            else:
                raise ValueError(f"invalid override value for {branch}:{source_tag}")
            if jp_tag not in jp_names:
                raise ValueError(
                    f"override target is not a JP tag: {branch}:{source_tag}->{jp_tag}"
                )
            overrides[branch][source_tag] = jp_tag
    return overrides


def load_official_crosswalk(
    path: Path,
    jp_names: set[str],
) -> dict[str, dict[str, str]]:
    raw = load_json(path)
    if not isinstance(raw, dict):
        raise ValueError("official crosswalk must be a JSON object")
    result: dict[str, dict[str, str]] = {}
    for branch, mappings in raw.items():
        if not isinstance(branch, str) or not isinstance(mappings, dict):
            raise ValueError(f"invalid official crosswalk branch: {branch!r}")
        result[branch] = {}
        for source_tag, jp_tag in mappings.items():
            if not isinstance(source_tag, str) or not source_tag:
                raise ValueError(f"invalid crosswalk source tag: {branch}:{source_tag!r}")
            if not isinstance(jp_tag, str):
                raise ValueError(
                    f"invalid crosswalk target: {branch}:{source_tag}->{jp_tag!r}"
                )
            if jp_tag not in jp_names:
                # SCP-INT's table can lag or retain branch-only concepts.  They
                # are candidates, not valid JP mappings, until the current JP
                # tag list registers the target.
                continue
            result[branch][source_tag] = jp_tag
    return result


def load_official_crosswalks(
    paths: tuple[Path, ...],
    jp_names: set[str],
) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for path in paths:
        current = load_official_crosswalk(path, jp_names)
        for branch, mappings in current.items():
            # Later, branch-local tables refine the shared SCP-INT table.
            merged.setdefault(branch, {}).update(mappings)
    return merged


def deprecated_by_source_lang(
    deprecated_raw: list[dict],
    jp_names: set[str],
    replacement_overrides: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, set[str]], dict[str, dict[str, str | None]]]:
    deprecated_tags: dict[str, set[str]] = {}
    replacements: dict[str, dict[str, str | None]] = {}
    seen: set[tuple[str, str]] = set()
    for entry in deprecated_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"invalid deprecated entry: {entry!r}")
        source_lang = entry.get("source_lang") or "EN"
        source_tag = entry.get("en_tag")
        if not isinstance(source_lang, str) or not isinstance(source_tag, str):
            raise ValueError(f"invalid deprecated entry: {entry!r}")
        key = (source_lang, source_tag)
        if key in seen:
            raise ValueError(
                f"duplicate deprecated entry: {source_lang}:{source_tag}"
            )
        seen.add(key)
        deprecated_tags.setdefault(source_lang, set()).add(source_tag)
        replacement = entry.get("replacement")
        if replacement is not None and not isinstance(replacement, str):
            raise ValueError(f"invalid replacement for {source_lang}:{source_tag}")
        if replacement is not None and replacement not in jp_names:
            raise ValueError(
                f"deprecated replacement is not a JP tag: "
                f"{source_lang}:{source_tag}->{replacement}"
            )
        replacements.setdefault(source_lang, {})[source_tag] = replacement
    for source_tag, replacement in en_builder.EN_ORIGIN_TAG_REPLACEMENTS.items():
        if replacement not in jp_names:
            raise ValueError(
                f"EN origin replacement is not a JP tag: "
                f"{source_tag}->{replacement}"
            )
        deprecated_tags.setdefault("EN", set()).add(source_tag)
        replacements.setdefault("EN", {})[source_tag] = replacement
    for source_lang, mappings in (replacement_overrides or {}).items():
        for source_tag, replacement in mappings.items():
            if replacement not in jp_names:
                raise ValueError(
                    f"deprecated override target is not a JP tag: "
                    f"{source_lang}:{source_tag}->{replacement}"
                )
            deprecated_tags.setdefault(source_lang, set()).add(source_tag)
            replacements.setdefault(source_lang, {})[source_tag] = replacement
    return deprecated_tags, replacements


def build_branch_dict(
    branch: str,
    source_tags: set[str],
    jp_names: set[str],
    jp_source_map: dict[str, str],
    deprecated_tags: dict[str, set[str]],
    replacements: dict[str, dict[str, str | None]],
    overrides: dict[str, dict[str, str]],
    official_crosswalk: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, str | None], dict[str, str]]:
    branch_deprecated, branch_replacements = deprecated_policy_for_branch(
        branch,
        deprecated_tags,
        replacements,
    )
    branch_overrides = {
        **overrides.get("*", {}),
        **overrides.get(branch, {}),
    }
    branch_crosswalk = (official_crosswalk or {}).get(branch, {})

    dictionary: dict[str, str | None] = {}
    all_source_tags = (
        set(source_tags)
        | set(branch_deprecated)
        | set(branch_overrides)
        | set(branch_crosswalk)
    )
    for source_tag in sorted(all_source_tags):
        if source_tag in branch_deprecated:
            dictionary[source_tag] = None
        elif source_tag in jp_names:
            dictionary[source_tag] = source_tag
        elif source_tag in branch_overrides:
            dictionary[source_tag] = branch_overrides[source_tag]
        elif source_tag in branch_crosswalk:
            dictionary[source_tag] = branch_crosswalk[source_tag]
        elif source_tag in jp_source_map:
            dictionary[source_tag] = jp_source_map[source_tag]
        else:
            dictionary[source_tag] = None

    concrete_replacements = {
        source_tag: replacement
        for source_tag, replacement in branch_replacements.items()
        if replacement is not None
    }
    return dictionary, dict(sorted(concrete_replacements.items()))


def build_en_dicts(
    jp_tags: list[dict],
    deprecated_raw: list[dict],
    overrides: dict[str, dict[str, str]],
    corpus_tags: set[str],
    official_crosswalk: dict[str, dict[str, str]],
    effective_deprecated: set[str] | None = None,
    effective_replacements: dict[str, str | None] | None = None,
) -> tuple[dict[str, str | None], dict[str, str]]:
    if not DATA_EN.exists():
        raise FileNotFoundError(
            f"{DATA_EN} not found. Run python scripts/parse_sources.py first."
        )
    en_tags: list[dict] = load_json(DATA_EN)
    deprecated_en_tags = {
        entry["en_tag"]
        for entry in deprecated_raw
        if en_builder.is_deprecated_for_en_source(entry)
    }
    deprecated_en_tags.update(effective_deprecated or set())
    en_overrides = {
        **overrides.get("*", {}),
        **overrides.get("en", {}),
    }
    category_omitted_tags = en_builder.en_category_omitted_tags(
        en_tags,
        jp_tags,
        set(en_overrides),
    )
    jp_names, jp_source_map = jp_maps(jp_tags)
    en_crosswalk = official_crosswalk.get("en", {})
    all_source_tags = (
        {entry["name"] for entry in en_tags}
        | corpus_tags
        | deprecated_en_tags
        | set(en_overrides)
        | set(en_crosswalk)
    )
    origin_replacements = {
        source_tag: replacement
        for source_tag, replacement in en_builder.EN_ORIGIN_TAG_REPLACEMENTS.items()
        if source_tag in all_source_tags
    }
    deprecated_en_tags.update(category_omitted_tags)
    deprecated_en_tags.update(origin_replacements)
    all_source_tags.update(deprecated_en_tags)
    dictionary: dict[str, str | None] = {}
    for source_tag in sorted(all_source_tags):
        if source_tag in deprecated_en_tags:
            dictionary[source_tag] = None
        elif source_tag in jp_names:
            dictionary[source_tag] = source_tag
        elif source_tag in en_overrides:
            dictionary[source_tag] = en_overrides[source_tag]
        elif source_tag in en_crosswalk:
            dictionary[source_tag] = en_crosswalk[source_tag]
        elif source_tag in jp_source_map:
            dictionary[source_tag] = jp_source_map[source_tag]
        else:
            dictionary[source_tag] = None
    deprecated_dict: dict[str, str] = {
        source_tag: replacement
        for source_tag, replacement in (effective_replacements or {}).items()
        if replacement is not None
    }
    if effective_replacements is None:
        deprecated_dict.update({
            entry["en_tag"]: entry["replacement"]
            for entry in deprecated_raw
            if en_builder.is_deprecated_for_en_source(entry)
            and entry.get("replacement")
        })
    deprecated_dict.update(origin_replacements)
    return dict(sorted(dictionary.items())), dict(sorted(deprecated_dict.items()))


def build_jp_policy(
    jp_tags: list[dict],
    deprecated_raw: list[dict] | None = None,
    en_tags: list[dict] | None = None,
    overrides: dict[str, dict[str, str]] | None = None,
    replacements: dict[str, dict[str, str | None]] | None = None,
    concatenated_tag_hints: dict[str, dict[str, list[str]]] | None = None,
) -> dict[str, Any]:
    tags: dict[str, dict[str, Any]] = {}
    for entry in jp_tags:
        name = entry["name"]
        description = entry.get("description") or ""
        use_restricted = bool(entry.get("use_restricted"))
        edit_restricted = bool(entry.get("edit_restricted"))
        translation_exempt = bool(entry.get("translation_exempt"))
        special_translation_action = None
        if (
            "新規作成は翻訳を含めて基本的に認められていません" in description
            or "当サイトではサンドボックスページの作成は認められていません"
            in description
        ):
            special_translation_action = "staff_permission_required"
        elif "他言語やSCP-INTに翻訳された記事には付与しないでください" in description:
            special_translation_action = "omit"
        tags[name] = {
            "use_restricted": use_restricted,
            "edit_restricted": edit_restricted,
            "translation_exempt": translation_exempt,
            "special_translation_action": special_translation_action,
            "copy_allowed_for_translation": (
                (not use_restricted or translation_exempt)
                and special_translation_action is None
            ),
        }
    source_tags: dict[str, dict[str, dict[str, str]]] = {}
    for entry in deprecated_raw or []:
        source_lang = entry.get("source_lang") or "EN"
        source_tag = entry.get("en_tag")
        if not isinstance(source_lang, str) or not isinstance(source_tag, str):
            continue
        branches = [
            branch
            for branch in SUPPORTED_BRANCHES
            if source_lang in source_languages_for_branch(branch)
        ]
        effective_replacement = (replacements or {}).get(source_lang, {}).get(
            source_tag
        )
        if not branches or effective_replacement is not None:
            continue
        for branch in branches:
            source_tags.setdefault(branch, {})[source_tag] = {
                "translation_action": "omit_jp_unused",
                "reason": entry.get("description")
                or "SCP-JPの非使用タグのため、翻訳記事には付与しません。",
            }

    if en_tags is not None:
        en_overrides = {
            **(overrides or {}).get("*", {}),
            **(overrides or {}).get("en", {}),
        }
        for source_tag in en_builder.en_category_omitted_tags(
            en_tags,
            jp_tags,
            set(en_overrides),
        ):
            for branch in ("en", "int"):
                source_tags.setdefault(branch, {})[source_tag] = {
                    "translation_action": "omit_translation_policy",
                    "reason": (
                        "SCP-JPでは「ジャンルとテーマ」タグ群は制度未整備のため、"
                        "翻訳の際は付与不要です。"
                    ),
                }

    return {
        "schema_version": 2,
        "source": "SCP-JP tag-list and fragment:tag-list-*",
        "tags": dict(sorted(tags.items())),
        "source_tags": {
            branch: dict(sorted(entries.items()))
            for branch, entries in sorted(source_tags.items())
        },
        "concatenated_tag_hints": {
            branch: dict(sorted(entries.items()))
            for branch, entries in sorted(
                (concatenated_tag_hints or {}).items()
            )
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build branch-to-JP tag dictionaries from local corpus metadata",
    )
    parser.add_argument(
        "--corpus-root",
        required=True,
        type=Path,
        help="Path to scp-wiki-translation/corpus",
    )
    parser.add_argument(
        "--branches",
        nargs="*",
        help=(
            "Optional dictionary output branches. Defaults to the 15 supported "
            "sites. The corpus must contain all supported branches so the global "
            "concatenated-tag policy remains complete."
        ),
    )
    args = parser.parse_args()

    corpus_root = args.corpus_root
    if not corpus_root.is_dir():
        print(f"エラー: corpus rootが見つかりません: {corpus_root}")
        sys.exit(1)
    required_data = (
        DATA_EN,
        DATA_JP,
        DATA_DEPRECATED,
        DATA_INT_CROSSWALK,
        DATA_KO_CROSSWALK,
        DATA_BRANCH_GUIDE_CROSSWALK,
    )
    if any(not path.exists() for path in required_data):
        print("エラー: 先に python scripts/parse_sources.py を実行してください。")
        sys.exit(1)

    jp_tags: list[dict] = load_json(DATA_JP)
    deprecated_raw: list[dict] = load_json(DATA_DEPRECATED)
    jp_names, jp_source_map = jp_maps(jp_tags)
    try:
        overrides = load_overrides(OVERRIDES_PATH, jp_names)
        replacement_overrides = load_overrides(
            DEPRECATED_REPLACEMENT_OVERRIDES_PATH,
            jp_names,
        )
        official_crosswalk = load_official_crosswalks(
            (
                DATA_INT_CROSSWALK,
                DATA_KO_CROSSWALK,
                DATA_BRANCH_GUIDE_CROSSWALK,
            ),
            jp_names,
        )
        deprecated_tags, replacements = deprecated_by_source_lang(
            deprecated_raw,
            jp_names,
            replacement_overrides,
        )
    except ValueError as err:
        print(f"エラー: {err}")
        sys.exit(1)

    branches = args.branches if args.branches else list(OFFICIAL_BRANCHES)
    if not branches:
        print("エラー: 生成対象の支部が見つかりません。")
        sys.exit(1)

    outputs: dict[Path, Any] = {}
    branch_dictionaries: dict[str, dict[str, str | None]] = {}
    visible_sequences_by_branch: dict[
        str,
        list[tuple[str, tuple[str, ...]]],
    ] = {}
    for branch in sorted(branches):
        if branch == "jp" or branch.startswith("_"):
            continue
        if branch == "en":
            try:
                source_tags, visible_sequences = (
                    collect_corpus_tags_and_visible_sequences(
                        corpus_root,
                        branch,
                    )
                )
                dictionary, deprecated_dict = build_en_dicts(
                    jp_tags,
                    deprecated_raw,
                    overrides,
                    source_tags,
                    official_crosswalk,
                    deprecated_tags.get("EN", set()),
                    replacements.get("EN", {}),
                )
            except (OSError, ValueError) as err:
                print(f"エラー: EN辞書生成に失敗しました: {err}")
                sys.exit(1)
            outputs[DICTIONARIES_DIR / "en_to_jp.json"] = dictionary
            outputs[DICTIONARIES_DIR / "deprecated_en_to_jp.json"] = deprecated_dict
            branch_dictionaries[branch] = dictionary
            visible_sequences_by_branch[branch] = visible_sequences
            mapped = sum(1 for value in dictionary.values() if value is not None)
            print(
                f"en: {mapped}/{len(dictionary)} mapped -> "
                "dictionaries/en_to_jp.json"
            )
            continue

        try:
            source_tags, visible_sequences = (
                collect_corpus_tags_and_visible_sequences(
                    corpus_root,
                    branch,
                )
            )
            dictionary, deprecated_dict = build_branch_dict(
                branch,
                source_tags,
                jp_names,
                jp_source_map,
                deprecated_tags,
                replacements,
                overrides,
                official_crosswalk,
            )
        except (OSError, ValueError) as err:
            print(f"エラー: {branch}辞書生成に失敗しました: {err}")
            sys.exit(1)

        dict_path = DICTIONARIES_DIR / f"{branch}_to_jp.json"
        deprecated_path = DICTIONARIES_DIR / f"deprecated_{branch}_to_jp.json"
        outputs[dict_path] = dictionary
        outputs[deprecated_path] = deprecated_dict
        branch_dictionaries[branch] = dictionary
        visible_sequences_by_branch[branch] = visible_sequences
        mapped = sum(1 for value in dictionary.values() if value is not None)
        print(
            f"{branch}: {mapped}/{len(dictionary)} mapped, "
            f"{len(deprecated_dict)} replacements -> {dict_path}"
        )

    try:
        hint_dictionaries = complete_hint_dictionaries(branch_dictionaries)
        for branch in SUPPORTED_BRANCHES:
            if branch not in visible_sequences_by_branch:
                _source_tags, visible_sequences_by_branch[branch] = (
                    collect_corpus_tags_and_visible_sequences(
                        corpus_root,
                        branch,
                    )
                )
        concatenated_tag_hints = {
            branch: build_concatenated_tag_hints(
                corpus_root,
                branch,
                hint_dictionaries[branch],
                visible_sequences_by_branch[branch],
            )
            for branch in SUPPORTED_BRANCHES
        }
    except (OSError, ValueError) as err:
        print(f"エラー: 連結タグ境界ヒント生成に失敗しました: {err}")
        sys.exit(1)
    en_tags: list[dict] = load_json(DATA_EN)
    outputs[JP_POLICY_PATH] = build_jp_policy(
        jp_tags,
        deprecated_raw,
        en_tags,
        overrides,
        replacements,
        concatenated_tag_hints,
    )
    publish_files_atomically({
        path: (lambda temporary, data=data: write_json(temporary, data))
        for path, data in outputs.items()
    })
    print(f"jp policy: {len(jp_tags)} tags -> {JP_POLICY_PATH}")
    print(
        "concatenated tag hints: "
        f"{sum(len(entries) for entries in concatenated_tag_hints.values())}"
    )


if __name__ == "__main__":
    main()
