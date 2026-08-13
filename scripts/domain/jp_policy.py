"""Build JP tag restrictions and source-tag translation policies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from scripts.domain.branch_config import SUPPORTED_BRANCHES
from scripts.domain.tag_policy_models import (
    JpPolicyDocument,
    JpTagPolicy,
    SourceTagPolicy,
    SpecialTranslationAction,
)
from scripts.domain.tag_records import (
    DeprecatedTag,
    EnTag,
    JpTag,
)
from scripts.domain.tag_policy import (
    MappingPolicy,
    en_category_omitted_tags,
    source_languages_for_branch,
)


@dataclass(frozen=True)
class JpPolicyInputs:
    jp_tags: Sequence[JpTag]
    deprecated_tags: Sequence[DeprecatedTag] = ()
    en_tags: Sequence[EnTag] | None = None
    mapping_policy: MappingPolicy | None = None
    concatenated_tag_hints: Mapping[str, Mapping[str, list[str]]] | None = None


def _build_jp_tag_policies(jp_tags: Sequence[JpTag]) -> dict[str, JpTagPolicy]:
    tags: dict[str, JpTagPolicy] = {}
    for entry in jp_tags:
        name = entry["name"]
        description = entry.get("description") or ""
        use_restricted = bool(entry.get("use_restricted"))
        edit_restricted = bool(entry.get("edit_restricted"))
        translation_exempt = bool(entry.get("translation_exempt"))
        special_translation_action: SpecialTranslationAction | None = None
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
    return tags


def _build_source_tag_policies(
    inputs: JpPolicyInputs,
) -> dict[str, dict[str, SourceTagPolicy]]:
    source_tags: dict[str, dict[str, SourceTagPolicy]] = {}
    mapping_policy = inputs.mapping_policy
    for entry in inputs.deprecated_tags:
        source_lang = entry.get("source_lang") or "EN"
        source_tag = entry["source_tag"]
        branches = [
            branch
            for branch in SUPPORTED_BRANCHES
            if source_lang in source_languages_for_branch(branch)
        ]
        replacements = mapping_policy.replacements if mapping_policy is not None else {}
        effective_replacement = replacements.get(source_lang, {}).get(source_tag)
        if not branches or effective_replacement is not None:
            continue
        for branch in branches:
            source_tags.setdefault(branch, {})[source_tag] = {
                "translation_action": "omit_jp_unused",
                "reason": entry.get("description")
                or "SCP-JPの非使用タグのため、翻訳記事には付与しません。",
            }

    if inputs.en_tags is not None:
        overrides = mapping_policy.overrides if mapping_policy is not None else {}
        en_overrides = {
            **overrides.get("*", {}),
            **overrides.get("en", {}),
        }
        for source_tag in en_category_omitted_tags(
            list(inputs.en_tags),
            list(inputs.jp_tags),
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
    return source_tags


def build_jp_policy(inputs: JpPolicyInputs) -> JpPolicyDocument:
    tags = _build_jp_tag_policies(inputs.jp_tags)
    source_tags = _build_source_tag_policies(inputs)

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
                (inputs.concatenated_tag_hints or {}).items()
            )
        },
    }
