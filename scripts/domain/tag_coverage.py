"""Build branch tag coverage from validated tag and mapping-policy inputs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.domain.branch_config import (
    BRANCH_CONFIG_BY_CODE,
    validate_requested_branches,
)
from scripts.domain.errors import InvalidDomainInputError
from scripts.domain.tag_coverage_models import (
    ApplicationBranch,
    ApplicationInventory,
    ApplicationTag,
    BranchTagStats,
    Classification,
    Coverage,
    CoverageBranch,
    CoverageTag,
)
from scripts.domain.policy.tag_policy_models import (
    ClassificationStatus,
    CoverageTranslationAction,
    JpTagPolicy,
)
from scripts.domain.records.tag_records import DeprecatedTag, EnTag, JpTag
from scripts.domain.policy.jp_policy import build_jp_tag_policies
from scripts.domain.policy.tag_policy import (
    BranchMappingPolicy,
    MappingPolicy,
    en_category_omitted_tags,
    resolve_source_tag,
)

__all__ = [
    "ACTION_DESCRIPTIONS",
    "STATUS_DESCRIPTIONS",
    "CoverageInputs",
    "build_application_inventory",
    "build_coverage",
]

STATUS_DESCRIPTIONS: dict[ClassificationStatus, str] = {
    "jp_unused_replacement": "Listed in the JP unused-tag page for this source branch with one replacement.",
    "jp_unused_no_single_replacement": "Listed in the JP unused-tag page for this source branch without one deterministic replacement.",
    "jp_translation_policy_omit": "Not copied because the JP tag-list FAQ says to omit this source category on translations.",
    "jp_tag_name": "The source tag itself is a registered JP tag name.",
    "jp_tag_alias": "The source tag is recorded in the JP tag list as a source-language tag annotation.",
    "curated_override_only": "Not recorded in the JP tag list, but mapped by local reviewed override data.",
    "official_crosswalk": "Mapped by an official SCP-INT or branch-local tag crosswalk to a current registered JP tag.",
    "unhandled": "No current JP tag-list mapping, reviewed override, or official crosswalk.",
}
ACTION_DESCRIPTIONS: dict[CoverageTranslationAction, str] = {
    "copy": "Registered JP tag; copyable for a translated page.",
    "copy_replacement": "JP unused source tag replaced by one registered copyable JP tag.",
    "omit_jp_unused": "JP explicitly does not use this source tag; omit it.",
    "omit_translation_policy": "JP translation policy says to omit this source tag category.",
    "omit_jp_policy": "Registered JP tag whose own definition says not to apply it to this translation.",
    "staff_permission_required": "Mapped JP restriction tag without translation exemption; do not copy without staff permission.",
    "tag_application_required": "No JP tag-list mapping; omit and request/confirm a JP tag before use.",
}


@dataclass(frozen=True)
class CoverageInputs:
    """Validated tag records and mapping policy consumed by one coverage build."""

    en_tags: Sequence[EnTag]
    jp_tags: Sequence[JpTag]
    deprecated_tags: Sequence[DeprecatedTag]
    mapping_policy: MappingPolicy


@dataclass(frozen=True)
class _ClassificationContext:
    mapping_policy: MappingPolicy
    branch_policy: BranchMappingPolicy
    target_policies: Mapping[str, JpTagPolicy]
    translation_policy_omit: frozenset[str]


@dataclass(frozen=True)
class _BaseClassification:
    status: ClassificationStatus
    recognized_by_jp_policy: bool
    jp_tag: str | None = None
    replacement: str | None = None


def _base_classification(
    tag: str,
    context: _ClassificationContext,
) -> _BaseClassification:
    resolution = resolve_source_tag(
        tag,
        context.mapping_policy,
        context.branch_policy,
    )
    if resolution.origin == "jp_unused":
        return _BaseClassification(
            status=(
                "jp_unused_replacement"
                if resolution.replacement
                else "jp_unused_no_single_replacement"
            ),
            recognized_by_jp_policy=True,
            replacement=resolution.replacement,
        )
    if resolution.origin == "jp_tag_name":
        return _BaseClassification(
            "jp_tag_name",
            True,
            jp_tag=resolution.target,
        )
    if resolution.origin == "curated_override":
        return _BaseClassification(
            "curated_override_only",
            False,
            jp_tag=resolution.target,
        )
    if tag in context.translation_policy_omit:
        return _BaseClassification(
            "jp_translation_policy_omit",
            True,
        )
    if resolution.origin == "official_crosswalk":
        return _BaseClassification(
            "official_crosswalk",
            False,
            jp_tag=resolution.target,
        )
    if resolution.origin == "jp_tag_alias":
        return _BaseClassification(
            "jp_tag_alias",
            True,
            jp_tag=resolution.target,
        )
    return _BaseClassification("unhandled", False)


def _classify_tag(tag: str, context: _ClassificationContext) -> Classification:
    base = _base_classification(tag, context)
    target = base.replacement or base.jp_tag
    action: CoverageTranslationAction
    copy_allowed = False
    display_tag: str | None = target
    target_policy: JpTagPolicy | None = None

    if base.status == "unhandled":
        action = "tag_application_required"
        display_tag = f"未訳-{tag}"
    elif base.status == "jp_translation_policy_omit":
        action = "omit_translation_policy"
        display_tag = None
    elif target is None:
        action = "omit_jp_unused"
        display_tag = None
    else:
        target_policy = context.target_policies.get(target)
        if target_policy is None:
            raise InvalidDomainInputError(
                f"JP policy missing for mapped target: {tag}->{target}"
            )
        copy_allowed = target_policy["copy_allowed_for_translation"]
        if target_policy["special_translation_action"] == "omit":
            action = "omit_jp_policy"
        elif not copy_allowed:
            action = "staff_permission_required"
        elif base.status == "jp_unused_replacement":
            action = "copy_replacement"
        else:
            action = "copy"

    return {
        "status": base.status,
        "recognized_by_jp_policy": base.recognized_by_jp_policy,
        "jp_tag": base.jp_tag,
        "replacement": base.replacement,
        "translation_action": action,
        "copy_allowed": copy_allowed,
        "display_tag": display_tag,
        "target_policy": target_policy,
    }


def _build_coverage_branch(
    branch: str,
    branch_stats: BranchTagStats,
    context: _ClassificationContext,
) -> CoverageBranch:
    """Build one branch's ranked classifications and status totals."""

    status_counts: Counter[ClassificationStatus] = Counter()
    tags: list[CoverageTag] = []
    tag_stats = branch_stats["tags"]
    sorted_tags = sorted(
        tag_stats,
        key=lambda tag: (-tag_stats[tag]["page_count"], tag),
    )
    for rank, tag in enumerate(sorted_tags, start=1):
        classification = _classify_tag(tag, context)
        status_counts[classification["status"]] += 1
        tags.append({
            "tag": tag,
            "rank": rank,
            "page_count": tag_stats[tag]["page_count"],
            "status": classification["status"],
            "recognized_by_jp_policy": classification[
                "recognized_by_jp_policy"
            ],
            "jp_tag": classification["jp_tag"],
            "replacement": classification["replacement"],
            "translation_action": classification["translation_action"],
            "copy_allowed": classification["copy_allowed"],
            "display_tag": classification["display_tag"],
            "target_policy": classification["target_policy"],
            "sample_slugs": tag_stats[tag]["sample_slugs"],
        })

    return {
        "branch": branch,
        "site": BRANCH_CONFIG_BY_CODE[branch].site,
        "page_count": branch_stats["page_count"],
        "tag_count": len(tags),
        "status_counts": dict(sorted(status_counts.items())),
        "tags": tags,
    }


def build_coverage(
    corpus_root: Path,
    branches: Sequence[str],
    inputs: CoverageInputs,
    branch_tag_stats: Mapping[str, BranchTagStats],
) -> Coverage:
    """Classify corpus statistics, raising InvalidDomainInputError for missing branch data."""
    branches = validate_requested_branches(branches)
    missing_branches = sorted(set(branches) - set(branch_tag_stats))
    if missing_branches:
        raise InvalidDomainInputError(
            "branch tag statistics missing for: " + ", ".join(missing_branches)
        )

    en_branch_policy = inputs.mapping_policy.for_branch("en")
    en_translation_policy_omit = en_category_omitted_tags(
        list(inputs.en_tags),
        list(inputs.jp_tags),
        set(en_branch_policy.overrides),
    )
    jp_policy = build_jp_tag_policies(inputs.jp_tags)

    branch_entries: list[CoverageBranch] = []
    for branch in branches:
        branch_stats = branch_tag_stats[branch]
        context = _ClassificationContext(
            mapping_policy=inputs.mapping_policy,
            branch_policy=inputs.mapping_policy.for_branch(branch),
            target_policies=jp_policy,
            translation_policy_omit=frozenset(
                en_translation_policy_omit
                if branch in {"en", "int"}
                else set()
            ),
        )
        branch_entries.append(_build_coverage_branch(
            branch,
            branch_stats,
            context,
        ))

    return {
        "schema_version": 3,
        "source": {
            "corpus_root": str(corpus_root),
            "jp_tag_source": "sources/jp/tag-list.txt + registered fragments",
            "jp_unused_source": "sources/jp/fragment-unused.txt",
            "override_source": "sources/branch_to_jp_overrides.json",
            "deprecated_override_source": "sources/deprecated_replacement_overrides.json",
            "crosswalk_source": "SCP-INT, SCP-KO, and synced branch-local official tag guides",
        },
        "status_descriptions": STATUS_DESCRIPTIONS,
        "action_descriptions": ACTION_DESCRIPTIONS,
        "branches": branch_entries,
    }


def build_application_inventory(coverage: Coverage) -> ApplicationInventory:
    """Derive the tag-application inventory from complete coverage."""

    branches: list[ApplicationBranch] = []
    for branch_entry in coverage["branches"]:
        tags: list[ApplicationTag] = [
            {
                "tag": entry["tag"],
                "display_tag": entry["display_tag"],
                "page_count": entry["page_count"],
                "sample_slugs": entry["sample_slugs"],
            }
            for entry in branch_entry["tags"]
            if entry["translation_action"] == "tag_application_required"
        ]
        branches.append({
            "branch": branch_entry["branch"],
            "site": branch_entry["site"],
            "scanned_page_count": branch_entry["page_count"],
            "tag_count": len(tags),
            "tags": tags,
        })
    return {
        "schema_version": 1,
        "rule": "JP tag-list未掲載。付与を見合わせ、タグ専任スタッフへの申請・確認が必要。",
        "branches": branches,
    }
