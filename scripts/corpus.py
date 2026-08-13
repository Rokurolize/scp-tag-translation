"""Local corpus discovery and tag traversal."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path

from scripts.json_io import load_json
from scripts.domain.tag_models import BranchTagStats, TagStats

SAMPLE_LIMIT = 5


def discover_corpus_branches(corpus_root: Path) -> list[str]:
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
        meta = load_json(meta_path)
        if not isinstance(meta, dict):
            raise ValueError(f"metadata root must be an object: {meta_path}")
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


def collect_branch_tag_stats(
    corpus_root: Path,
    branch: str,
) -> BranchTagStats:
    """Collect page counts and representative slugs for coverage reporting."""
    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    page_count = 0
    for slug, tags in iter_corpus_page_tags(corpus_root, branch):
        page_count += 1
        for tag in set(tags):
            counts[tag] += 1
            if len(samples[tag]) < SAMPLE_LIMIT:
                samples[tag].append(slug)

    return {
        "page_count": page_count,
        "tags": {
            tag: TagStats(
                page_count=count,
                sample_slugs=samples[tag],
            )
            for tag, count in counts.items()
        },
    }


def corpus_tags_for_branch(corpus_root: Path, branch: str) -> set[str]:
    tags: set[str] = set()
    for _slug, page_tags in iter_corpus_page_tags(corpus_root, branch):
        tags.update(page_tags)
    return tags
