import json
import subprocess
from pathlib import Path

from tests.frontend_harness import (
    ROOT,
    frontend_script,
    node,
    run_frontend_script,
    translate_with_frontend,
)


def test_issue_3_known_english_tags_use_their_current_jp_mappings():
    root = Path(__file__).parent.parent
    dictionary = json.loads(
        (root / "dictionaries" / "en_to_jp.json").read_text(encoding="utf-8")
    )
    deprecated = json.loads(
        (root / "dictionaries" / "deprecated_en_to_jp.json").read_text(
            encoding="utf-8"
        )
    )
    policy = json.loads(
        (root / "dictionaries" / "jp_tag_policy.json").read_text(encoding="utf-8")
    )

    expected = {
        "co-authored": "共著",
        "afterlife": "死後",
        "doctor-elstrom": "エルストロム博士",
    }
    for source_tag, target_tag in expected.items():
        assert translate_with_frontend(
            dictionary,
            source_tag,
            "en",
            deprecated,
            policy,
        ) == {
            "targetText": f"en {target_tag}",
            "logArea": "",
        }


def split_with_frontend(token: str, dictionary: dict[str, str | None]) -> list[str]:
    script = f"""
const elements = {{}};
const context = {{
  console,
  document: {{
    getElementById(id) {{
      return elements[id] ||= {{ style: {{}}, addEventListener() {{}} }};
    }},
    createElement() {{ return {{}}; }},
  }},
  window: {{ addEventListener() {{}}, location: {{ protocol: "http:" }} }},
  navigator: {{}},
}};
vm.createContext(context);
vm.runInContext(frontendScript, context);
console.log(JSON.stringify(context.splitConcatenatedTags(
  {json.dumps(token)}, {json.dumps(dictionary, ensure_ascii=False)}
)));
"""
    return json.loads(run_frontend_script(script))


def test_index_script_has_valid_javascript_syntax(tmp_path):
    script_path = tmp_path / "index-script.js"
    script_path.write_text(frontend_script(), encoding="utf-8")

    subprocess.run([node(), "--check", str(script_path)], check=True)


def test_split_concatenated_tags_uses_forward_longest_match():
    dictionary = {
        "ab": "AB",
        "abc": "ABC",
        "cd": "CD",
        "d": "D",
    }

    assert split_with_frontend("abcd", dictionary) == ["abc", "d"]


def test_split_concatenated_tags_backs_off_when_longest_prefix_dead_ends():
    dictionary = {
        "a": "A",
        "ab": "AB",
        "bc": "BC",
    }

    assert split_with_frontend("abc", dictionary) == ["a", "bc"]


def test_split_concatenated_tags_returns_original_when_unsplittable():
    dictionary = {
        "a": "A",
        "ab": "AB",
        "bc": "BC",
    }

    assert split_with_frontend("abx", dictionary) == ["abx"]


def test_split_concatenated_tags_handles_empty_dictionary():
    assert split_with_frontend("anything", {}) == ["anything"]


def test_split_concatenated_tags_handles_long_input_without_recursion_overflow():
    script = """
const elements = {};
const context = {
  console,
  document: {
    getElementById(id) {
      return elements[id] ||= { style: {}, addEventListener() {} };
    },
    createElement() { return {}; },
  },
  window: { addEventListener() {}, location: { protocol: "http:" } },
  navigator: {},
};
vm.createContext(context);
vm.runInContext(frontendScript, context);
console.log(context.splitConcatenatedTags('a'.repeat(12000), { a: 'A' }).length);
"""
    assert run_frontend_script(script).strip() == "12000"


def test_scp_3352_copied_tag_string_translates_like_spaced_tags():
    dictionary = json.loads(
        (ROOT / "dictionaries" / "en_to_jp.json").read_text(encoding="utf-8")
    )
    deprecated = json.loads(
        (ROOT / "dictionaries" / "deprecated_en_to_jp.json").read_text(
            encoding="utf-8"
        )
    )
    policy = json.loads(
        (ROOT / "dictionaries" / "jp_tag_policy.json").read_text(
            encoding="utf-8"
        )
    )
    spaced = (
        "anomalous-event fire indestructible inscription neutralized "
        "reviewers-spotlight scp structure"
    )
    concatenated = (
        "anomalous-eventfireindestructibleinscriptionneutralized"
        "reviewers-spotlightscpstructure"
    )

    spaced_state = translate_with_frontend(
        dictionary,
        spaced,
        "en",
        deprecated,
        policy,
    )
    concatenated_state = translate_with_frontend(
        dictionary,
        concatenated,
        "en",
        deprecated,
        policy,
    )

    assert concatenated_state == spaced_state
    assert concatenated_state["targetText"] == (
        "en 炎 破壊不可能 記述 neutralized 批評者スポットライト scp 構造"
    )


def test_translation_prefers_corpus_boundary_hint_over_greedy_segmentation():
    allowed = {
        "copy_allowed_for_translation": True,
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "special_translation_action": None,
    }
    policy = {
        "tags": {tag: allowed for tag in ("en", "safe", "scp", "彫像")},
        "source_tags": {},
        "concatenated_tag_hints": {
            "en": {
                "safescpsculpture": ["safe", "scp", "sculpture"]
            }
        },
    }
    dictionary = {
        "safe": "safe",
        "scp": "scp",
        "sculpture": "彫像",
        "scpsculpture": None,
    }

    spaced = translate_with_frontend(
        dictionary,
        "safe scp sculpture",
        "en",
        policy=policy,
    )
    concatenated = translate_with_frontend(
        dictionary,
        "safescpsculpture",
        "en",
        policy=policy,
    )

    assert concatenated == spaced
    assert concatenated["targetText"] == "en safe scp 彫像"


def test_translation_prefers_exact_dictionary_key_over_boundary_hint():
    allowed = {
        "copy_allowed_for_translation": True,
        "use_restricted": False,
        "edit_restricted": False,
        "translation_exempt": False,
        "special_translation_action": None,
    }
    policy = {
        "tags": {tag: allowed for tag in ("en", "完全一致", "左", "右")},
        "source_tags": {},
        "concatenated_tag_hints": {"en": {"joined": ["left", "right"]}},
    }
    dictionary = {
        "joined": "完全一致",
        "left": "左",
        "right": "右",
    }

    translated = translate_with_frontend(
        dictionary,
        "joined",
        "en",
        policy=policy,
    )

    assert translated == {"targetText": "en 完全一致", "logArea": ""}
