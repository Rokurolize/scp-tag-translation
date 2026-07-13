"""Parse branch-local official tag guides into deterministic JP mappings."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote

from scripts.parsers.contracts import (
    BranchGuideAnalysis,
    BranchGuideStats,
    TargetResolver,
)
from scripts.parsers.crosswalk_resolver import normalize_tag


_TAG_LINK_RE = re.compile(
    r"\[(?:\*)?"
    r"(?:(?P<scheme>https?://)(?P<host>[^/\]\s]+))?"
    r"/system:page-tags/tag/(?P<path>[^\s\]#?]+)"
    r"(?:[#?][^\s\]]*)?"
    r"(?:\s+(?P<label>[^\]]+))?\]",
    re.IGNORECASE,
)
_VALID_TAG_RE = re.compile(r"^[^\s|()\[\]{}*]+$")
_EN_TAG_RE = re.compile(r"^[a-z0-9_&.:'-]+$", re.IGNORECASE)


class _TagLink(TypedDict):
    path: str
    label: str
    host: str
    start: int
    end: int


def _tag_links(line: str) -> list[_TagLink]:
    links = []
    for match in _TAG_LINK_RE.finditer(line):
        path = normalize_tag(unquote(match.group("path"))).strip("/")
        label = normalize_tag(match.group("label") or path)
        links.append(
            {
                "path": path,
                "label": label,
                "host": (match.group("host") or "").lower(),
                "start": match.start(),
                "end": match.end(),
            }
        )
    return links


def _valid_tag(value: str) -> str | None:
    value = normalize_tag(value).strip("\"'")
    if not value or not _VALID_TAG_RE.fullmatch(value):
        return None
    return value


def _valid_en_tag(value: str) -> str | None:
    value = normalize_tag(value).strip("\"'")
    if not value or not _EN_TAG_RE.fullmatch(value):
        return None
    return value


def _parse_cn(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        if not line.lstrip().startswith("*"):
            continue
        links = _tag_links(line)
        local = next(
            (
                link
                for link in links
                if not link["host"] or "scp-wiki-cn" in link["host"]
            ),
            None,
        )
        if local is None:
            continue
        source = _valid_tag(local["path"])
        if source is None:
            continue
        en_values = [
            link["path"]
            for link in links
            if "scpwiki.com" in link["host"] or "scp-wiki.wikidot.com" in link["host"]
        ]
        jp_values = [
            link["path"]
            for link in links
            if "ja.scp-wiki.net" in link["host"] or "scp-jp.wikidot.com" in link["host"]
        ]
        if not en_values and not jp_values:
            tail = line[local["end"] :]
            for raw in re.findall(r"\(\s*([^()]+?)\s*\)", tail):
                if value := _valid_en_tag(raw.strip("/* ")):
                    en_values.append(value)
                    break
        if en_values or jp_values:
            yield source, en_values, jp_values


def _parse_de(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    in_dictionary = False
    for line in lines:
        if "||~ Englisch ||~ Deutsch ||~ Informationen ||" in line:
            in_dictionary = True
            continue
        if not in_dictionary:
            continue
        if line.startswith("[[/collapsible]]"):
            break
        if not line.startswith("||"):
            continue
        cells = line.split("||")[1:]
        if len(cells) < 2:
            continue
        en_tag = _valid_en_tag(cells[0].strip(" {}*~"))
        links = _tag_links(cells[1])
        if en_tag is None or len(links) != 1:
            continue
        if source := _valid_tag(links[0]["path"]):
            yield source, [en_tag], []


def _parse_link_followed_by_en(
    lines: Iterable[str],
    branch_host: str,
    en_pattern: re.Pattern[str],
) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        links = [
            link
            for link in _tag_links(line)
            if not link["host"] or branch_host in link["host"]
        ]
        for index, link in enumerate(links):
            tail_end = (
                links[index + 1]["start"] if index + 1 < len(links) else len(line)
            )
            tail = line[link["end"] : tail_end]
            match = en_pattern.search(tail)
            source = _valid_tag(link["path"])
            en_tag = _valid_en_tag(match.group(1)) if match else None
            if source is not None and en_tag is not None:
                yield source, [en_tag], []


def _parse_label_parenthetical(
    lines: Iterable[str],
    branch_host: str,
) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        for link in _tag_links(line):
            if link["host"] and branch_host not in link["host"]:
                continue
            source = _valid_tag(link["path"])
            match = re.search(r"\(([^()]+)\)\s*$", link["label"])
            en_tag = _valid_en_tag(match.group(1)) if match else None
            if source is not None and en_tag is not None:
                yield source, [en_tag], []


def _parse_ua(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    pattern = re.compile(
        r"^\s*(?:\*\s*)?\*\*(?P<source>[^*]+)\*\*\s*"
        r"\((?P<en>[^()]+)\)"
    )
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        source = _valid_tag(match.group("source"))
        en_tag = _valid_en_tag(match.group("en"))
        if source is not None and en_tag is not None:
            yield source, [en_tag], []


def _parse_pt(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    pattern = re.compile(r"^\s*\*\s*\*\*([^*]+)\*\*\s*\|")
    for line in lines:
        match = pattern.match(line)
        links = _tag_links(line)
        if not match or not links:
            continue
        en_tag = _valid_en_tag(match.group(1))
        source = _valid_tag(links[0]["path"])
        if en_tag is not None and source is not None and en_tag.lower() != "n/a":
            yield source, [en_tag], []


def _parse_vn(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        if not line.startswith("||"):
            continue
        cells = line.split("||")[1:]
        if len(cells) < 2:
            continue
        en_tag = _valid_en_tag(cells[0])
        links = _tag_links(cells[1])
        if en_tag is None or len(links) != 1:
            continue
        if source := _valid_tag(links[0]["path"]):
            yield source, [en_tag], []


_PARSERS = {
    "cn": _parse_cn,
    "de": _parse_de,
    "es": lambda lines: _parse_link_followed_by_en(
        lines,
        "lafundacionscp",
        re.compile(r"\(([^()]+)\)"),
    ),
    "fr": lambda lines: _parse_link_followed_by_en(
        lines,
        "fondationscp",
        re.compile(r'\(\*\*ang\s*:\*\*\s*"([^"]+)"\)', re.IGNORECASE),
    ),
    "it": lambda lines: _parse_link_followed_by_en(
        lines,
        "fondazionescp",
        re.compile(r"\(([^()]+)\)"),
    ),
    "pl": lambda lines: _parse_label_parenthetical(lines, "scp-pl"),
    "pt-br": _parse_pt,
    "th": lambda lines: _parse_label_parenthetical(lines, "scp-th"),
    "ua": _parse_ua,
    "vn": _parse_vn,
}


def _parse_zh(
    paths: Sequence[Path],
) -> Iterable[tuple[str, list[str], list[str]]]:
    pattern = re.compile(r"[（(]\s*([^（）()]+?)\s*[）)]")
    for path in paths:
        is_internationality = path.name.startswith("fragment-internationality")
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            links = [
                link
                for link in _tag_links(line)
                if not link["host"] or "scp-zh-tr" in link["host"]
            ]
            for index, link in enumerate(links):
                source = _valid_tag(link["path"])
                if source is None:
                    continue
                if is_internationality:
                    yield source, [], [source]
                    continue
                tail_end = (
                    links[index + 1]["start"] if index + 1 < len(links) else len(line)
                )
                match = pattern.search(line[link["end"] : tail_end])
                en_tag = _valid_en_tag(match.group(1)) if match else None
                if en_tag is not None:
                    yield source, [en_tag], []


def analyze_branch_guides(
    source_paths: Mapping[str, Sequence[Path]],
    resolver: TargetResolver,
) -> BranchGuideAnalysis:
    """Return unique current-JP mappings and deterministic audit counts."""

    targets: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    unresolved_sources: dict[str, set[str]] = defaultdict(set)
    stats: BranchGuideStats = {}
    for branch, paths in source_paths.items():
        rows = (
            _parse_zh(paths)
            if branch == "zh-tr"
            else _PARSERS[branch](
                line
                for path in paths
                for line in path.read_text(encoding="utf-8").splitlines()
            )
        )
        parsed_rows = 0
        resolved_rows = 0
        for source_tag, en_values, jp_values in rows:
            parsed_rows += 1
            target = resolver(en_values, jp_values)
            if target is None:
                unresolved_sources[branch].add(source_tag)
                continue
            resolved_rows += 1
            targets[branch][source_tag].add(target)
        conflicts = sum(1 for values in targets[branch].values() if len(values) > 1)
        accepted = sum(
            1
            for source_tag, values in targets[branch].items()
            if len(values) == 1 and source_tag not in unresolved_sources[branch]
        )
        stats[branch] = {
            "parsed_rows": parsed_rows,
            "resolved_rows": resolved_rows,
            "accepted_tags": accepted,
            "conflicting_tags": conflicts,
            "unresolved_source_tags": len(unresolved_sources[branch]),
        }

    mappings = {
        branch: dict(
            sorted(
                (source_tag, next(iter(values)))
                for source_tag, values in branch_targets.items()
                if len(values) == 1 and source_tag not in unresolved_sources[branch]
            )
        )
        for branch, branch_targets in sorted(targets.items())
    }
    return BranchGuideAnalysis(mappings=mappings, stats=stats)
