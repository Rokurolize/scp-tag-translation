"""Corpus analysis for tag strings copied without whitespace boundaries."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.domain.branch_config import SUPPORTED_BRANCHES

ROOT = Path(__file__).resolve().parents[2]
DICTIONARIES_DIR = ROOT / "dictionaries"


@dataclass(slots=True)
class _TrieNode:
    children: dict[str, _TrieNode] = field(default_factory=dict)
    terminal: bool = False


def _load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def discover_branches(corpus_root: Path) -> list[str]:
    branches = []
    for branch_dir in sorted(corpus_root.iterdir()):
        if not branch_dir.is_dir():
            continue
        branch = branch_dir.name
        if branch == "jp" or branch.startswith("_"):
            continue
        pages_dir = branch_dir / "pages"
        if pages_dir.is_dir() and any(pages_dir.glob("*/meta.json")):
            branches.append(branch)
    return branches


def iter_corpus_page_tags(
    corpus_root: Path,
    branch: str,
) -> Iterator[tuple[str, list[str]]]:
    pages_dir = corpus_root / branch / "pages"
    if not pages_dir.is_dir():
        raise ValueError(f"corpus branch pages directory not found: {pages_dir}")

    for meta_path in sorted(pages_dir.glob("*/meta.json")):
        meta = _load_json(meta_path)
        if not isinstance(meta, dict):
            raise ValueError(f"invalid metadata object in {meta_path}")
        raw_tags = meta.get("tags", [])
        if isinstance(raw_tags, str):
            page_tags = [raw_tags]
        elif isinstance(raw_tags, list):
            if any(not isinstance(tag, str) or not tag for tag in raw_tags):
                raise ValueError(f"invalid tags field in {meta_path}")
            page_tags = list(raw_tags)
            if len(set(page_tags)) != len(page_tags):
                raise ValueError(f"duplicate tags in {meta_path}")
        else:
            raise ValueError(f"invalid tags field in {meta_path}")
        yield meta_path.parent.name, page_tags


def collect_corpus_tags_and_visible_sequences(
    corpus_root: Path,
    branch: str,
) -> tuple[set[str], list[tuple[str, tuple[str, ...]]]]:
    tags: set[str] = set()
    visible_sequences = []
    for slug, page_tags in iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
        visible = tuple(tag for tag in page_tags if not tag.startswith("_"))
        if visible:
            visible_sequences.append((slug, visible))
    return tags, visible_sequences


def corpus_tags_for_branch(corpus_root: Path, branch: str) -> set[str]:
    tags: set[str] = set()
    for _slug, page_tags in iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
    return tags


def _dictionary_trie(dictionary: Mapping[str, str | None]) -> _TrieNode:
    root = _TrieNode()
    for tag in dictionary:
        node = root
        for character in tag:
            node = node.children.setdefault(character, _TrieNode())
        node.terminal = True
    return root


def _split_concatenated_tag(token: str, trie: _TrieNode) -> tuple[str, ...]:
    can_split = [False] * (len(token) + 1)
    next_end_by_index = [-1] * (len(token) + 1)
    can_split[len(token)] = True

    for index in range(len(token) - 1, -1, -1):
        node = trie
        longest_end = -1
        for end in range(index, len(token)):
            child = node.children.get(token[end])
            if child is None:
                break
            node = child
            candidate_end = end + 1
            if node.terminal and can_split[candidate_end]:
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
    dictionary: Mapping[str, str | None],
    trie: _TrieNode,
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
    dictionary: Mapping[str, str | None],
    visible_sequences: Sequence[tuple[str, tuple[str, ...]]] | None = None,
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
    generated: Mapping[str, dict[str, str | None]],
    *,
    dictionaries_dir: Path = DICTIONARIES_DIR,
    supported_branches: Sequence[str] = SUPPORTED_BRANCHES,
) -> dict[str, dict[str, str | None]]:
    complete = dict(generated)
    for branch in supported_branches:
        if branch in complete:
            continue
        path = dictionaries_dir / f"{branch}_to_jp.json"
        if not path.is_file():
            raise ValueError(
                "existing dictionary required for partial hint generation: "
                f"{path}"
            )
        dictionary = _load_json(path)
        if not isinstance(dictionary, dict) or any(
            not isinstance(tag, str)
            or (target is not None and not isinstance(target, str))
            for tag, target in dictionary.items()
        ):
            raise ValueError(f"invalid existing dictionary: {path}")
        complete[branch] = dictionary
    return complete
