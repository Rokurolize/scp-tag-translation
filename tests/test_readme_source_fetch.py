"""README documents the repository's authoritative source-update workflow."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"


def test_readme_source_update_uses_repository_wikidot_workflow():
    readme = README.read_text(encoding="utf-8")
    section = readme[readme.index("## 辞書の更新方法") :]

    assert "wikidot.py`フォーク" in section
    assert "JPタグリストのマニフェスト" in section
    assert "`AGENTS.md`の「Updating Wikidot source snapshots」" in section
    assert "`curl`や検索結果を原典として使わず" in section
    assert "```bash\ncurl " not in section
