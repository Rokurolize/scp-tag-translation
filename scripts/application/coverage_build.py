"""Build and publish branch tag-coverage artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.domain.branch_config import SUPPORTED_BRANCHES, validate_requested_branches
from scripts.domain.tag_coverage import (
    CoverageInputs,
    build_application_inventory,
    build_coverage,
)
from scripts.domain.tag_coverage_models import Coverage
from scripts.infrastructure.atomic_output import publish_files_atomically
from scripts.infrastructure.data_paths import VISUALIZATION_DIR
from scripts.infrastructure.json_io import write_json
from scripts.pipeline.corpus import collect_branch_tag_stats
from scripts.pipeline.coverage_outputs import (
    write_application_inventory_tsv,
    write_coverage_tsv,
)
from scripts.application.mapping_inputs import (
    MappingInputPaths,
    default_mapping_input_paths,
    load_mapping_inputs,
    to_coverage_inputs,
)

DEFAULT_OUTPUT_DIR = VISUALIZATION_DIR


@dataclass(frozen=True)
class CoverageBuildConfig:
    """Input and output locations for one coverage build."""

    output_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUT_DIR)
    supported_branches: tuple[str, ...] = SUPPORTED_BRANCHES
    mapping_inputs: MappingInputPaths = field(
        default_factory=default_mapping_input_paths,
    )


def default_coverage_build_config(
    *,
    output_dir: Path | None = None,
    supported_branches: Sequence[str] = SUPPORTED_BRANCHES,
) -> CoverageBuildConfig:
    """Return the repository's default coverage build configuration."""
    return CoverageBuildConfig(
        output_dir=DEFAULT_OUTPUT_DIR if output_dir is None else output_dir,
        supported_branches=tuple(supported_branches),
        mapping_inputs=default_mapping_input_paths(),
    )


def load_coverage_inputs(paths: MappingInputPaths) -> CoverageInputs:
    loaded = load_mapping_inputs(paths)
    return to_coverage_inputs(loaded)


def build_and_publish_coverage(
    corpus_root: Path,
    branches: Sequence[str] | None,
    *,
    config: CoverageBuildConfig | None = None,
) -> tuple[Coverage, tuple[Path, Path, Path, Path]]:
    """Build coverage artifacts and publish all four outputs atomically."""
    config = config or default_coverage_build_config()
    requested_branches = tuple(
        config.supported_branches if branches is None else branches
    )
    branches = validate_requested_branches(
        requested_branches,
        supported_branches=config.supported_branches,
    )
    inputs = load_coverage_inputs(config.mapping_inputs)
    branch_tag_stats = {
        branch: collect_branch_tag_stats(corpus_root, branch)
        for branch in branches
    }
    coverage = build_coverage(
        corpus_root,
        branches,
        inputs,
        branch_tag_stats,
    )
    json_path = config.output_dir / "branch_tag_coverage.json"
    tsv_path = config.output_dir / "branch_tag_coverage.tsv"
    inventory = build_application_inventory(coverage)
    inventory_json_path = config.output_dir / "tag_application_inventory.json"
    inventory_tsv_path = config.output_dir / "tag_application_inventory.tsv"
    publish_files_atomically({
        json_path: lambda temporary: write_json(temporary, coverage),
        tsv_path: lambda temporary: write_coverage_tsv(temporary, coverage),
        inventory_json_path: (
            lambda temporary: write_json(temporary, inventory)
        ),
        inventory_tsv_path: (
            lambda temporary: write_application_inventory_tsv(
                temporary,
                inventory,
            )
        ),
    })
    return coverage, (
        json_path,
        tsv_path,
        inventory_json_path,
        inventory_tsv_path,
    )


__all__ = [
    "CoverageBuildConfig",
    "CoverageInputs",
    "DEFAULT_OUTPUT_DIR",
    "build_and_publish_coverage",
    "default_coverage_build_config",
    "load_coverage_inputs",
]
