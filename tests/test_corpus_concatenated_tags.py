"""実コーパスのタグ列を使った連結入力の網羅回帰テスト。"""

from __future__ import annotations

import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scripts.domain.branch_config import SUPPORTED_BRANCHES
from tests.frontend_harness import node

ROOT = Path(__file__).parent.parent
RUNNER = ROOT / "tests" / "corpus_concatenated_runner.js"
FAILURE_SAMPLE_LIMIT = 10
SUMMARY_COUNTERS = (
    "pageCount",
    "visibleArticleCount",
    "uniqueVectorCount",
    "checkedVectorCount",
    "endToEndVectorCount",
    "failureArticleCount",
    "failureVectorCount",
    "schemaFailureCount",
    "intrinsicCollisionCount",
    "hintFailureCount",
)


def _failure_message(summary: dict, elapsed: float) -> str:
    failing_branches = {
        branch: {
            "articles": stats["failureArticleCount"],
            "vectors": stats["failureVectorCount"],
        }
        for branch, stats in summary["branchStats"].items()
        if stats["failureVectorCount"]
    }
    lines = [
        (
            "連結タグのコーパス回帰: "
            f"{summary['failureArticleCount']}/{summary['visibleArticleCount']}記事、"
            f"{summary['failureVectorCount']}/{summary['uniqueVectorCount']}固有タグ列で不一致 "
            f"({elapsed:.2f}秒)"
        ),
        f"支部別不一致: {json.dumps(failing_branches, ensure_ascii=False, sort_keys=True)}",
        (
            f"メタデータ異常: {summary['schemaFailureCount']}、"
            f"同一連結文字列の本質的衝突: {summary['intrinsicCollisionCount']}、"
            f"境界ヒント異常: {summary['hintFailureCount']}"
        ),
    ]
    lines.extend(
        json.dumps(sample, ensure_ascii=False, sort_keys=True)
        for sample in summary["samples"]
    )
    return "\n".join(lines)


def _run_branch(node: str, corpus_root: Path, branch: str) -> dict:
    completed = subprocess.run(
        [
            node,
            str(RUNNER),
            str(ROOT),
            str(corpus_root),
            json.dumps([branch]),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"{branch}支部の検査に失敗しました。\n{completed.stderr}")
    return json.loads(completed.stdout)


def _merge_summaries(branch_summaries: list[dict]) -> dict:
    merged = {counter: 0 for counter in SUMMARY_COUNTERS}
    merged["branchStats"] = {}
    all_samples = []
    for summary in branch_summaries:
        for counter in SUMMARY_COUNTERS:
            merged[counter] += summary[counter]
        merged["branchStats"].update(summary["branchStats"])
        all_samples.extend(summary["samples"])

    selected = []
    selected_ids = set()
    represented_groups = set()
    for sample in all_samples:
        group = (sample.get("type"), sample.get("branch"))
        if group in represented_groups:
            continue
        selected.append(sample)
        selected_ids.add(id(sample))
        represented_groups.add(group)
    for sample in all_samples:
        if len(selected) >= FAILURE_SAMPLE_LIMIT:
            break
        if id(sample) not in selected_ids:
            selected.append(sample)
    merged["samples"] = selected[:FAILURE_SAMPLE_LIMIT]
    return merged


def _write_minimal_corpus_fixture(root: Path) -> Path:
    policy = json.loads(
        (ROOT / "dictionaries" / "jp_tag_policy.json").read_text(encoding="utf-8")
    )
    for branch in SUPPORTED_BRANCHES:
        dictionary = json.loads(
            (ROOT / "dictionaries" / f"{branch}_to_jp.json").read_text(encoding="utf-8")
        )
        hints = policy.get("concatenated_tag_hints", {}).get(branch, {})
        tags = next(
            (
                values
                for values in hints.values()
                if isinstance(values, list)
                and len(values) > 1
                and all(tag in dictionary for tag in values)
            ),
            [next(iter(dictionary))],
        )
        page_dir = root / branch / "pages" / "fixture"
        page_dir.mkdir(parents=True)
        (page_dir / "meta.json").write_text(
            json.dumps({"tags": tags}),
            encoding="utf-8",
        )
    return root


def _assert_corpus_tag_sequences(
    corpus_root: Path,
    *,
    require_hint_coverage: bool,
) -> None:
    node_executable = node()

    started = time.perf_counter()
    worker_count = min(4, len(SUPPORTED_BRANCHES))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        branch_summaries = list(
            executor.map(
                lambda branch: _run_branch(node_executable, corpus_root, branch),
                SUPPORTED_BRANCHES,
            )
        )
    elapsed = time.perf_counter() - started

    summary = _merge_summaries(branch_summaries)
    assert set(summary["branchStats"]) == set(SUPPORTED_BRANCHES)
    empty_branches = {
        branch: stats
        for branch, stats in summary["branchStats"].items()
        if stats["pageCount"] == 0
        or stats["visibleArticleCount"] == 0
        or stats["uniqueVectorCount"] == 0
    }
    assert not empty_branches, (
        "記事または可視タグ列がない対応支部があります: "
        + json.dumps(empty_branches, ensure_ascii=False, sort_keys=True)
    )
    assert summary["pageCount"] > 0
    assert summary["checkedVectorCount"] == summary["uniqueVectorCount"]
    assert summary["endToEndVectorCount"] == summary["uniqueVectorCount"]
    assert summary["schemaFailureCount"] == 0
    assert summary["intrinsicCollisionCount"] == 0
    assert summary["failureVectorCount"] == 0
    if require_hint_coverage:
        assert summary["hintFailureCount"] == 0, _failure_message(summary, elapsed)


def test_synthetic_corpus_tag_sequence_smoke(tmp_path):
    _assert_corpus_tag_sequences(
        _write_minimal_corpus_fixture(tmp_path / "corpus"),
        require_hint_coverage=False,
    )


@pytest.mark.corpus_integration
def test_every_corpus_tag_sequence_translates_when_spaces_are_lost():
    configured = os.environ.get("SCP_WIKI_CORPUS_ROOT")
    if not configured:
        if os.environ.get("CI"):
            pytest.fail(
                "SCP_WIKI_CORPUS_ROOT must be provisioned for the CI corpus regression"
            )
        pytest.skip("SCP_WIKI_CORPUS_ROOT is required for the real-corpus regression")
    corpus_root = Path(configured)
    if not corpus_root.is_dir():
        pytest.fail(
            "SCP_WIKI_CORPUS_ROOTで指定されたcorpusディレクトリがありません: "
            f"{corpus_root}"
        )
    _assert_corpus_tag_sequences(corpus_root, require_hint_coverage=True)
