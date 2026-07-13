"""実コーパスのタグ列を使った連結入力の網羅回帰テスト。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from scripts.domain.branch_config import SUPPORTED_BRANCHES

ROOT = Path(__file__).parent.parent
DEFAULT_CORPUS_ROOT = Path(
    "/home/roku/src/Rokurolize/scp-wiki-translation/corpus"
)
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


def _corpus_root() -> Path:
    configured = os.environ.get("SCP_WIKI_CORPUS_ROOT")
    return Path(configured) if configured else DEFAULT_CORPUS_ROOT


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


def test_every_corpus_tag_sequence_translates_when_spaces_are_lost():
    corpus_root = _corpus_root()
    if not corpus_root.is_dir():
        if os.environ.get("SCP_WIKI_CORPUS_ROOT"):
            pytest.fail(
                "SCP_WIKI_CORPUS_ROOTで指定されたcorpusディレクトリがありません: "
                f"{corpus_root}"
            )
        pytest.skip(
            "ローカルコーパスがありません。SCP_WIKI_CORPUS_ROOTでcorpusディレクトリを指定してください。"
        )

    node = shutil.which("node")
    if node is None:
        pytest.skip("nodeが見つからないためフロントエンド回帰テストをスキップします。")

    started = time.perf_counter()
    worker_count = min(4, len(SUPPORTED_BRANCHES))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        branch_summaries = list(
            executor.map(
                lambda branch: _run_branch(node, corpus_root, branch),
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
    assert (
        summary["schemaFailureCount"] == 0
        and summary["intrinsicCollisionCount"] == 0
        and summary["hintFailureCount"] == 0
        and summary["failureVectorCount"] == 0
    ), _failure_message(summary, elapsed)
