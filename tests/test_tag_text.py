import pytest

from scripts.domain.tag_text import normalize_tag


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  SCP-001  ", "SCP-001"),
        ("ｈｏｒｒｏｒ", "horror"),
        ("tag\u200bname", "tagname"),
    ],
)
def test_normalize_tag_canonicalizes_compatibility_and_format_text(
    value,
    expected,
):
    assert normalize_tag(value) == expected


def test_normalize_tag_preserves_empty_result_after_trimming():
    assert normalize_tag("  ") == ""
