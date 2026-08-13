"""Corpus analysis for tag strings copied without whitespace boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = ["build_concatenated_tag_hints"]


@dataclass(slots=True)
class _TrieNode:
    children: dict[str, _TrieNode] = field(default_factory=dict)
    terminal: bool = False


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
    branch: str,
    dictionary: Mapping[str, str | None],
    visible_sequences: Sequence[tuple[str, tuple[str, ...]]],
) -> dict[str, list[str]]:
    """Build exact boundaries only where generic longest matching is ambiguous."""

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
