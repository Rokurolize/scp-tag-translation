"""Parse branch-local official tag guides into deterministic JP mappings."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableSequence, Sequence
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote

from scripts.contracts.errors import InvalidDomainInputError
from scripts.parsers.contracts import (
    BranchGuideAnalysis,
    BranchGuideAudit,
    BranchGuideStats,
    TargetResolver,
)
from scripts.domain.tag_text import normalize_tag
from scripts.parsers.errors import report_source_issue

__all__ = ["analyze_branch_guides"]


_TAG_LINK_RE = re.compile(
    r"\[(?:\*)?"
    r"(?:(?P<scheme>https?://)(?P<host>[^/\]\s]+))?"
    r"/system(?::|/)page-tags/tag/(?P<path>[^\s\]#?]+)"
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


def _normalize_valid_tag(value: str) -> str | None:
    value = normalize_tag(value).strip("\"'")
    if not value or not _VALID_TAG_RE.fullmatch(value):
        return None
    return value


def _normalize_valid_en_tag(value: str) -> str | None:
    value = normalize_tag(value).strip("\"'")
    if not value or not _EN_TAG_RE.fullmatch(value):
        return None
    return value


def _paths_matching_hosts(
    links: Sequence[_TagLink],
    host_fragments: Sequence[str],
) -> list[str]:
    return [
        link["path"]
        for link in links
        if any(fragment in link["host"] for fragment in host_fragments)
    ]


def _iter_branch_link_tails(
    line: str,
    branch_host: str,
) -> Iterable[tuple[_TagLink, str]]:
    """Yield each local branch link and the text before the next link."""
    links = [
        link
        for link in _tag_links(line)
        if not link["host"] or branch_host in link["host"]
    ]
    for index, link in enumerate(links):
        tail_end = (
            links[index + 1]["start"] if index + 1 < len(links) else len(line)
        )
        yield link, line[link["end"] : tail_end]


def _validated_source_en(
    source_raw: str,
    en_raw: str,
) -> tuple[str, list[str], list[str]] | None:
    source = _normalize_valid_tag(source_raw)
    en_tag = _normalize_valid_en_tag(en_raw)
    if source is None or en_tag is None:
        return None
    return source, [en_tag], []


def _parse_table_source_en(
    line: str,
    *,
    strip_en_decorations: bool,
) -> tuple[str, list[str], list[str]] | None:
    if not line.startswith("||"):
        return None
    cells = line.split("||")[1:]
    if len(cells) < 2:
        return None
    links = _tag_links(cells[1])
    if len(links) != 1:
        return None
    en_raw = cells[0].strip(" {}*~") if strip_en_decorations else cells[0]
    return _validated_source_en(links[0]["path"], en_raw)


def _parse_cn_line(line: str) -> tuple[str, list[str], list[str]] | None:
    if not line.lstrip().startswith("*"):
        return None
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
        return None
    source = _normalize_valid_tag(local["path"])
    if source is None:
        return None
    en_values = _paths_matching_hosts(
        links,
        ("scpwiki.com", "scp-wiki.wikidot.com"),
    )
    jp_values = _paths_matching_hosts(
        links,
        ("ja.scp-wiki.net", "scp-jp.wikidot.com"),
    )
    if not en_values and not jp_values:
        tail = line[local["end"] :]
        for raw in re.findall(r"\(\s*([^()]+?)\s*\)", tail):
            if value := _normalize_valid_en_tag(raw.strip("/* ")):
                en_values.append(value)
                break
    if en_values or jp_values:
        return source, en_values, jp_values
    return None


def _parse_cn(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    for row in map(_parse_cn_line, lines):
        if row is not None:
            yield row


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
        if row := _parse_table_source_en(
            line,
            strip_en_decorations=True,
        ):
            yield row


def _parse_link_followed_by_en(
    lines: Iterable[str],
    branch_host: str,
    en_pattern: re.Pattern[str],
) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        for link, tail in _iter_branch_link_tails(line, branch_host):
            match = en_pattern.search(tail)
            if match and (row := _validated_source_en(link["path"], match.group(1))):
                yield row


def _parse_label_parenthetical(
    lines: Iterable[str],
    branch_host: str,
) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        for link, _tail in _iter_branch_link_tails(line, branch_host):
            match = re.search(r"\(([^()]+)\)\s*$", link["label"])
            if match and (row := _validated_source_en(link["path"], match.group(1))):
                yield row


def _parse_ua(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    pattern = re.compile(
        r"^\s*(?:\*\s*)?\*\*(?P<source>[^*]+)\*\*\s*"
        r"\((?P<en>[^()]+)\)"
    )
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        source = _normalize_valid_tag(match.group("source"))
        en_tag = _normalize_valid_en_tag(match.group("en"))
        if source is not None and en_tag is not None:
            yield source, [en_tag], []


def _parse_pt(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    pattern = re.compile(r"^\s*\*\s*\*\*([^*]+)\*\*\s*\|")
    for line in lines:
        match = pattern.match(line)
        links = _tag_links(line)
        if not match or not links:
            continue
        en_tag = _normalize_valid_en_tag(match.group(1))
        source = _normalize_valid_tag(links[0]["path"])
        if en_tag is not None and source is not None and en_tag.lower() != "n/a":
            yield source, [en_tag], []


def _parse_vn(lines: Iterable[str]) -> Iterable[tuple[str, list[str], list[str]]]:
    for line in lines:
        if row := _parse_table_source_en(
            line,
            strip_en_decorations=False,
        ):
            yield row


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
            for link, tail in _iter_branch_link_tails(line, "scp-zh-tr"):
                source = _normalize_valid_tag(link["path"])
                if source is None:
                    continue
                if is_internationality:
                    yield source, [], [source]
                    continue
                match = pattern.search(tail)
                if match and (
                    row := _validated_source_en(link["path"], match.group(1))
                ):
                    yield row


def _analyze_branch_rows(
    rows: Iterable[tuple[str, list[str], list[str]]],
    resolver: TargetResolver,
) -> tuple[dict[str, str], BranchGuideAudit]:
    targets: dict[str, set[str]] = defaultdict(set)
    unresolved_sources: set[str] = set()
    parsed_rows = 0
    resolved_rows = 0
    for source_tag, en_values, jp_values in rows:
        parsed_rows += 1
        target = resolver(en_values, jp_values)
        if target is None:
            unresolved_sources.add(source_tag)
            continue
        resolved_rows += 1
        targets[source_tag].add(target)

    conflicts = sum(1 for values in targets.values() if len(values) > 1)
    mappings = dict(
        sorted(
            (source_tag, next(iter(values)))
            for source_tag, values in targets.items()
            if len(values) == 1 and source_tag not in unresolved_sources
        )
    )
    stats: BranchGuideAudit = {
        "parsed_rows": parsed_rows,
        "resolved_rows": resolved_rows,
        "accepted_tags": len(mappings),
        "conflicting_tags": conflicts,
        "unresolved_source_tags": len(unresolved_sources),
    }
    return mappings, stats


def _validate_source_links(
    source_paths: Sequence[Path],
    diagnostics: MutableSequence[str] | None = None,
) -> None:
    """Reject tag-shaped lines that cannot produce a valid link record."""
    for path in source_paths:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if "page-tags/tag/" not in line:
                continue
            links = _tag_links(line)
            if not links:
                report_source_issue(
                    path,
                    line_number,
                    "invalid branch tag link",
                    diagnostics,
                )
            if any(_normalize_valid_tag(link["path"]) is None for link in links):
                report_source_issue(
                    path,
                    line_number,
                    "invalid branch tag name",
                    diagnostics,
                )


def analyze_branch_guides(
    source_paths: Mapping[str, Sequence[Path]],
    resolver: TargetResolver,
    *,
    strict: bool = False,
    diagnostics: MutableSequence[str] | None = None,
) -> BranchGuideAnalysis:
    """Return unique current-JP mappings and deterministic audit counts.

    ``source_paths`` must contain supported branch keys; unknown keys raise
    ``InvalidDomainInputError``. In strict mode, malformed source records are
    appended to ``diagnostics`` when provided; otherwise the parser raises
    ``SourceParseError``.
    """

    mappings_by_branch: dict[str, dict[str, str]] = {}
    stats: BranchGuideStats = {}
    for branch, paths in source_paths.items():
        if branch != "zh-tr" and branch not in _PARSERS:
            raise InvalidDomainInputError(f"unsupported branch guide: {branch!r}")
        if strict:
            _validate_source_links(paths, diagnostics)
        rows = (
            _parse_zh(paths)
            if branch == "zh-tr"
            else _PARSERS[branch](
                line
                for path in paths
                for line in path.read_text(encoding="utf-8").splitlines()
            )
        )
        mappings_by_branch[branch], stats[branch] = _analyze_branch_rows(rows, resolver)

    mappings = dict(sorted(mappings_by_branch.items()))
    return BranchGuideAnalysis(mappings=mappings, stats=stats)
