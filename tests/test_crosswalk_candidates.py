from scripts.parsers.crosswalk_candidates import resolve_crosswalk_candidates


def test_resolve_crosswalk_candidates_keeps_only_unambiguous_targets():
    candidates = [
        ("en", "source", ["source"], ["target"]),
        ("en", "source", ["source"], ["target"]),
        ("en", "conflict", ["conflict"], ["target-a"]),
        ("en", "conflict", ["conflict"], ["target-b"]),
        ("ko", "unresolved", ["unresolved"], []),
    ]

    assert resolve_crosswalk_candidates(
        candidates,
        lambda _en_values, jp_values: next(iter(jp_values), None),
    ) == {"en": {"source": "target"}}
