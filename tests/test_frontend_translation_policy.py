from tests.frontend_harness import translate_with_frontend


def test_translation_handles_dictionary_keys_that_shadow_object_prototype():
    state = translate_with_frontend(
        {"hasOwnProperty": "所有", "x": "X"},
        "hasOwnPropertyx",
        "en",
    )

    assert state["targetText"] == "en 所有 X"


def test_translation_handles_json_dictionary_proto_keys():
    state = translate_with_frontend(
        {"__proto__": "プロト", "constructor": "コンスト", "x": "X"},
        "__proto__constructorx",
        "en",
    )

    assert state["targetText"] == "en プロト コンスト X"


def test_translation_deduplicates_replacement_and_direct_outputs():
    state = translate_with_frontend(
        {"artist": None, "artwork": "アートワーク"},
        "artist artwork artwork",
        "en",
        {"artist": "アートワーク"},
    )

    assert state["targetText"] == "en アートワーク"


def test_translation_does_not_emit_source_lang_when_all_tags_are_skipped():
    state = translate_with_frontend(
        {"unused": None},
        "missing unused",
        "en",
    )

    assert state["targetText"] == ""
    assert "missing (未定義)" in state["logArea"]
    assert "unused (未対応または非使用タグ)" in state["logArea"]


def test_translation_distinguishes_application_from_explicit_jp_omission():
    omitted = translate_with_frontend(
        {"genre-tag": None},
        "genre-tag",
        "en",
        policy={
            "tags": {},
            "source_tags": {
                "en": {
                    "genre-tag": {
                        "translation_action": "omit_translation_policy",
                        "reason": "翻訳時は付与不要です。",
                    }
                }
            },
        },
    )
    application = translate_with_frontend(
        {"new-concept": None},
        "new-concept",
        "en",
        policy={"tags": {}, "source_tags": {}},
    )

    assert omitted["targetText"] == ""
    assert "JPでは付与しない" in omitted["logArea"]
    assert "タグ申請" not in omitted["logArea"]
    assert application["targetText"] == ""
    assert "未訳-new-concept" in application["logArea"]
    assert "タグ申請・確認が必要" in application["logArea"]


def test_translation_keeps_restricted_jp_tag_out_of_copy_field():
    state = translate_with_frontend(
        {"theme": "テーマ"},
        "theme",
        "en",
        policy={
            "tags": {
                "テーマ": {
                    "copy_allowed_for_translation": False,
                    "use_restricted": True,
                    "edit_restricted": False,
                    "translation_exempt": False,
                    "special_translation_action": None,
                }
            },
            "source_tags": {},
        },
    )

    assert state["targetText"] == ""
    assert "スタッフ許可が必要" in state["logArea"]


def test_translation_copies_restricted_tag_with_translation_exemption():
    allowed = {
        "copy_allowed_for_translation": True,
        "use_restricted": True,
        "edit_restricted": False,
        "translation_exempt": True,
        "special_translation_action": None,
    }
    state = translate_with_frontend(
        {"featured": "注目記事"},
        "featured",
        "en",
        policy={
            "tags": {
                "注目記事": allowed,
                "en": {
                    **allowed,
                    "use_restricted": False,
                    "translation_exempt": False,
                },
            },
            "source_tags": {},
        },
    )

    assert state["targetText"] == "en 注目記事"
    assert "制限緩和/翻訳によりコピー可能" in state["logArea"]


def test_translation_fails_closed_when_jp_policy_is_missing():
    state = translate_with_frontend(
        {"scp": "scp"},
        "scp",
        "en",
        policy={},
    )

    assert state["targetText"] == ""
    assert "JPポリシーデータ未読込" in state["logArea"]
    assert "データ不整合" in state["logArea"]


def test_translation_uses_normalized_source_branch_tag():
    state = translate_with_frontend(
        {"conto": "tale"},
        "conto",
        "pt-br",
    )

    assert state["targetText"] == "pt tale"


def test_translation_does_not_add_source_branch_when_branch_tag_is_translated():
    state = translate_with_frontend(
        {"原創": "zh", "故事": "tale"},
        "原創 故事",
        "zh-tr",
    )

    assert state["targetText"] == "zh tale"

