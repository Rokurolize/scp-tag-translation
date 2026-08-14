import json
import re
import sys

import pytest

from scripts.application import coverage_html as coverage_html_workflow
from scripts.commands import build_branch_tag_coverage_html as coverage_html_builder
from scripts.infrastructure.data_paths import ROOT
from scripts.domain.coverage_validation import validate_coverage
from scripts.domain.tag_coverage import ACTION_DESCRIPTIONS, STATUS_DESCRIPTIONS

COVERAGE_JSON = ROOT / "visualization" / "branch_tag_coverage.json"
COVERAGE_HTML = ROOT / "visualization" / "branch_tag_coverage.html"
TEMPLATE_HTML = ROOT / "scripts" / "assets" / "branch_tag_coverage.html"


@pytest.fixture
def coverage():
    return json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))


def _load_embedded_html_coverage():
    html = COVERAGE_HTML.read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="coverage-data">(.*?)</script>', html, re.DOTALL)
    assert match
    return json.loads(match.group(1)), html


def test_coverage_validator_accepts_generated_document(coverage):
    assert validate_coverage(coverage) == coverage


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "misspelled", "status is unknown"),
        ("translation_action", "misspelled", "translation_action is unknown"),
    ],
)
def test_coverage_validator_rejects_unknown_protocol_values(
    field,
    value,
    message,
    coverage,
):
    coverage["branches"][0]["tags"][0][field] = value

    with pytest.raises(ValueError, match=message):
        coverage_html_workflow.validate_coverage(coverage)


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ("status_descriptions", "status_descriptions keys"),
        ("action_descriptions", "action_descriptions keys"),
    ],
)
def test_coverage_validator_rejects_unknown_description_keys(mapping, message, coverage):
    coverage[mapping]["misspelled"] = "invalid"

    with pytest.raises(ValueError, match=message):
        coverage_html_workflow.validate_coverage(coverage)


def test_coverage_validator_rejects_unknown_status_count_key(coverage):
    coverage["branches"][0]["status_counts"]["misspelled"] = 1

    with pytest.raises(ValueError, match="status_counts is invalid"):
        coverage_html_workflow.validate_coverage(coverage)


def test_coverage_validator_rejects_status_counts_that_do_not_match_tags(coverage):
    branch = coverage["branches"][0]
    status = branch["tags"][0]["status"]
    branch["status_counts"][status] -= 1

    with pytest.raises(ValueError, match="status_counts does not match tags"):
        coverage_html_workflow.validate_coverage(coverage)


def test_coverage_validator_rejects_unknown_special_action(coverage):
    coverage["branches"][0]["tags"][0]["target_policy"] = {
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "copy_allowed_for_translation": True,
        "special_translation_action": "misspelled",
    }

    with pytest.raises(ValueError, match="special_translation_action"):
        coverage_html_workflow.validate_coverage(coverage)


@pytest.mark.parametrize(
    "field",
    ("jp_tag", "replacement", "display_tag", "target_policy"),
)
def test_coverage_validator_rejects_missing_nullable_required_field(field, coverage):
    coverage["branches"][0]["tags"][0].pop(field)

    with pytest.raises(ValueError, match=field):
        coverage_html_workflow.validate_coverage(coverage)


def test_coverage_validator_rejects_missing_special_action_key(coverage):
    coverage["branches"][0]["tags"][0]["target_policy"] = {
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "copy_allowed_for_translation": True,
    }

    with pytest.raises(ValueError, match="special_translation_action"):
        coverage_html_workflow.validate_coverage(coverage)


def test_visualization_html_is_self_contained_and_embeds_current_data(coverage):
    assert COVERAGE_HTML.exists()

    embedded, html = _load_embedded_html_coverage()

    assert embedded == coverage
    assert html == coverage_html_workflow.render_coverage_html(coverage)
    assert "fetch(" not in html
    assert "http://" not in html
    assert "https://" not in html
    assert 'id="branchSelect"' in html
    assert 'id="statusFilters"' in html
    assert 'id="tagRows"' in html


def test_dashboard_template_has_one_data_placeholder():
    template = TEMPLATE_HTML.read_text(encoding="utf-8")

    assert template.count("__DATA_JSON__") == 1
    assert '<script type="application/json" id="coverage-data">' in template


def test_visualization_html_escapes_embedded_json_script_boundaries():
    html = coverage_html_workflow.render_coverage_html(
        {
            "schema_version": 1,
            "source": {},
            "status_descriptions": {},
            "branches": [],
            "probe": "</script><p>breakout</p>",
        }
    )

    assert "</script><p>breakout</p>" not in html
    match = re.search(
        r'<script type="application/json" id="coverage-data">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match
    assert json.loads(match.group(1))["probe"] == "</script><p>breakout</p>"


def test_coverage_html_main_reports_input_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    missing_input = tmp_path / "missing.json"
    output = tmp_path / "output" / "coverage.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(missing_input),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out.startswith(
        "エラー: HTML可視化生成に失敗しました: "
    )
    assert not output.exists()


def test_coverage_html_main_publishes_valid_input(
    tmp_path,
    monkeypatch,
    capsys,
):
    input_path = tmp_path / "coverage.json"
    input_path.write_text(
        json.dumps({
            "schema_version": 3,
            "source": {
                "corpus_root": "/tmp/corpus",
                "jp_tag_source": "jp",
                "jp_unused_source": "unused",
                "override_source": "overrides",
                "deprecated_override_source": "deprecated",
                "crosswalk_source": "crosswalk",
            },
            "status_descriptions": dict(STATUS_DESCRIPTIONS),
            "action_descriptions": dict(ACTION_DESCRIPTIONS),
            "branches": [],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "output" / "coverage.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(input_path),
            "--output",
            str(output),
        ],
    )

    coverage_html_builder.main()

    assert '"schema_version":3' in output.read_text(encoding="utf-8")
    assert capsys.readouterr().out == (
        f"HTML可視化を生成しました: {output}\n"
    )


def test_coverage_html_main_reports_malformed_input_path(
    tmp_path,
    monkeypatch,
    capsys,
):
    invalid_input = tmp_path / "broken.json"
    invalid_input.write_text('{"broken": }', encoding="utf-8")
    output = tmp_path / "output" / "coverage.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(invalid_input),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert str(invalid_input) in capsys.readouterr().out
    assert not output.exists()


def test_coverage_html_main_rejects_invalid_nested_schema(
    tmp_path,
    monkeypatch,
    capsys,
):
    invalid_input = tmp_path / "invalid.json"
    invalid_input.write_text(
        json.dumps({
            "schema_version": 1,
            "source": {},
            "status_descriptions": {},
            "action_descriptions": {},
            "branches": [],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "output" / "coverage.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(invalid_input),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert "coverage.source.corpus_root" in capsys.readouterr().out
    assert not output.exists()


def test_coverage_html_main_preserves_output_on_publication_failure(
    tmp_path,
    monkeypatch,
    capsys,
):
    input_path = tmp_path / "coverage.json"
    input_path.write_text("{}", encoding="utf-8")
    output = tmp_path / "coverage.html"
    output.write_text("previous", encoding="utf-8")
    monkeypatch.setattr(
        coverage_html_workflow,
        "validate_coverage",
        lambda raw: raw,
    )

    def fail_publication(_writers):
        raise OSError("disk full")

    monkeypatch.setattr(
        coverage_html_workflow,
        "publish_files_atomically",
        fail_publication,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_branch_tag_coverage_html.py",
            "--input",
            str(input_path),
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        coverage_html_builder.main()

    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        "エラー: HTML可視化生成に失敗しました: disk full\n"
    )
    assert output.read_text(encoding="utf-8") == "previous"
