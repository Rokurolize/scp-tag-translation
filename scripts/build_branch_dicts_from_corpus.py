#!/usr/bin/env python3
"""Build source-branch to JP tag dictionaries from local corpus metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import build_dict as en_builder

ROOT = Path(__file__).resolve().parent.parent
DATA_EN = ROOT / "data" / "en_tags.json"
DATA_JP = ROOT / "data" / "jp_tags.json"
DATA_DEPRECATED = ROOT / "data" / "deprecated_tags.json"
OVERRIDES_PATH = ROOT / "sources" / "branch_to_jp_overrides.json"
DICTIONARIES_DIR = ROOT / "dictionaries"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, str | None]) -> None:
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


def corpus_tags_for_branch(corpus_root: Path, branch: str) -> set[str]:
    pages_dir = corpus_root / branch / "pages"
    if not pages_dir.is_dir():
        raise ValueError(f"corpus branch pages directory not found: {pages_dir}")

    tags: set[str] = set()
    for meta_path in sorted(pages_dir.glob("*/meta.json")):
        meta = load_json(meta_path)
        raw_tags = meta.get("tags", [])
        if isinstance(raw_tags, str):
            tags.add(raw_tags)
        elif isinstance(raw_tags, list):
            tags.update(tag for tag in raw_tags if isinstance(tag, str) and tag)
        else:
            raise ValueError(f"invalid tags field in {meta_path}")
    return tags


def jp_maps(jp_tags: list[dict]) -> tuple[set[str], dict[str, str]]:
    jp_names: set[str] = set()
    source_to_jp: dict[str, str] = {}
    for entry in jp_tags:
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"invalid JP tag entry: {entry!r}")
        jp_names.add(name)
        source_tag = entry.get("en_tag")
        if isinstance(source_tag, str) and source_tag:
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


def deprecated_by_source_lang(
    deprecated_raw: list[dict],
    jp_names: set[str],
) -> tuple[dict[str, set[str]], dict[str, dict[str, str]]]:
    deprecated_tags: dict[str, set[str]] = {}
    replacements: dict[str, dict[str, str]] = {}
    for entry in deprecated_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"invalid deprecated entry: {entry!r}")
        source_lang = entry.get("source_lang") or "EN"
        source_tag = entry.get("en_tag")
        if not isinstance(source_lang, str) or not isinstance(source_tag, str):
            raise ValueError(f"invalid deprecated entry: {entry!r}")
        deprecated_tags.setdefault(source_lang, set()).add(source_tag)
        replacement = entry.get("replacement")
        if replacement is None:
            continue
        if not isinstance(replacement, str):
            raise ValueError(f"invalid replacement for {source_lang}:{source_tag}")
        if replacement not in jp_names:
            raise ValueError(
                f"deprecated replacement is not a JP tag: "
                f"{source_lang}:{source_tag}->{replacement}"
            )
        replacements.setdefault(source_lang, {})[source_tag] = replacement
    return deprecated_tags, replacements


def build_branch_dict(
    branch: str,
    source_tags: set[str],
    jp_names: set[str],
    jp_source_map: dict[str, str],
    deprecated_tags: dict[str, set[str]],
    replacements: dict[str, dict[str, str]],
    overrides: dict[str, dict[str, str]],
) -> tuple[dict[str, str | None], dict[str, str]]:
    source_lang = branch_to_source_lang(branch)
    branch_deprecated = deprecated_tags.get(source_lang, set())
    branch_replacements = replacements.get(source_lang, {})
    branch_overrides = overrides.get(branch, {})

    dictionary: dict[str, str | None] = {}
    all_source_tags = set(source_tags) | set(branch_deprecated)
    for source_tag in sorted(all_source_tags):
        if source_tag in branch_deprecated:
            dictionary[source_tag] = None
        elif source_tag in jp_names:
            dictionary[source_tag] = source_tag
        elif source_tag in jp_source_map:
            dictionary[source_tag] = jp_source_map[source_tag]
        elif source_tag in branch_overrides:
            dictionary[source_tag] = branch_overrides[source_tag]
        else:
            dictionary[source_tag] = None

    return dictionary, dict(sorted(branch_replacements.items()))


def build_en_dicts(jp_tags: list[dict], deprecated_raw: list[dict]) -> tuple[int, int]:
    if not DATA_EN.exists():
        raise FileNotFoundError(
            f"{DATA_EN} not found. Run python scripts/parse_sources.py first."
        )
    en_tags: list[dict] = load_json(DATA_EN)
    existing: dict[str, str | None] = {}
    dict_out = DICTIONARIES_DIR / "en_to_jp.json"
    if dict_out.exists():
        existing = load_json(dict_out)

    deprecated_en_tags = {
        entry["en_tag"]
        for entry in deprecated_raw
        if en_builder.is_deprecated_for_en_source(entry)
    }
    dictionary = en_builder.build(en_tags, jp_tags, existing, deprecated_en_tags)
    deprecated_dict = {
        entry["en_tag"]: entry["replacement"]
        for entry in deprecated_raw
        if en_builder.is_deprecated_for_en_source(entry) and entry.get("replacement")
    }
    write_json(dict_out, dictionary)
    write_json(DICTIONARIES_DIR / "deprecated_en_to_jp.json", deprecated_dict)
    return sum(1 for value in dictionary.values() if value is not None), len(dictionary)


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
        help="Optional source branches. Defaults to all non-JP corpus branches.",
    )
    args = parser.parse_args()

    corpus_root = args.corpus_root
    if not corpus_root.is_dir():
        print(f"エラー: corpus rootが見つかりません: {corpus_root}")
        sys.exit(1)
    if not DATA_JP.exists() or not DATA_DEPRECATED.exists():
        print("エラー: 先に python scripts/parse_sources.py を実行してください。")
        sys.exit(1)

    jp_tags: list[dict] = load_json(DATA_JP)
    deprecated_raw: list[dict] = load_json(DATA_DEPRECATED)
    jp_names, jp_source_map = jp_maps(jp_tags)
    try:
        overrides = load_overrides(OVERRIDES_PATH, jp_names)
        deprecated_tags, replacements = deprecated_by_source_lang(
            deprecated_raw,
            jp_names,
        )
    except ValueError as err:
        print(f"エラー: {err}")
        sys.exit(1)

    branches = args.branches if args.branches else discover_branches(corpus_root)
    if not branches:
        print("エラー: 生成対象の支部が見つかりません。")
        sys.exit(1)

    for branch in sorted(branches):
        if branch == "jp" or branch.startswith("_"):
            continue
        if branch == "en":
            try:
                mapped, total = build_en_dicts(jp_tags, deprecated_raw)
            except (OSError, ValueError) as err:
                print(f"エラー: EN辞書生成に失敗しました: {err}")
                sys.exit(1)
            print(f"en: {mapped}/{total} mapped -> dictionaries/en_to_jp.json")
            continue

        try:
            source_tags = corpus_tags_for_branch(corpus_root, branch)
            dictionary, deprecated_dict = build_branch_dict(
                branch,
                source_tags,
                jp_names,
                jp_source_map,
                deprecated_tags,
                replacements,
                overrides,
            )
        except (OSError, ValueError) as err:
            print(f"エラー: {branch}辞書生成に失敗しました: {err}")
            sys.exit(1)

        dict_path = DICTIONARIES_DIR / f"{branch}_to_jp.json"
        deprecated_path = DICTIONARIES_DIR / f"deprecated_{branch}_to_jp.json"
        write_json(dict_path, dictionary)
        write_json(deprecated_path, deprecated_dict)
        mapped = sum(1 for value in dictionary.values() if value is not None)
        print(
            f"{branch}: {mapped}/{len(dictionary)} mapped, "
            f"{len(deprecated_dict)} replacements -> {dict_path}"
        )


if __name__ == "__main__":
    main()
