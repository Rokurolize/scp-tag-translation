"""Validation logic for tag mappings."""

import re


def validate_business_rules(dictionary: dict[str, str | None]) -> tuple[list[str], list[str]]:
    """
    Validate business rules for tag mappings.

    Args:
        dictionary: Tag mapping dictionary to validate.

    Returns:
        Tuple of (critical_errors, warnings)
        - critical_errors: List of critical issues that must be fixed
        - warnings: List of non-critical issues
    """
    critical = []
    warnings = []

    # Object classes must be self-mapped (they're universal)
    object_classes = ["safe", "euclid", "keter", "thaumiel", "apollyon", "archon", "neutralized", "explained"]
    for oc in object_classes:
        if oc in dictionary and dictionary[oc] != oc:
            critical.append(f"Object class '{oc}' mapped to '{dictionary[oc]}' instead of self")

    # Series numbers (1000, 2000, etc.) must be self-mapped
    for en_tag, jp_tag in dictionary.items():
        if re.match(r"^\d000$", en_tag):
            if jp_tag != en_tag:
                critical.append(f"Series '{en_tag}' mapped to '{jp_tag}' instead of self")

    # Main structural tags should exist and be mapped
    required_tags = ["scp", "tale", "goi-format", "supplement", "joke"]
    for tag in required_tags:
        if tag not in dictionary:
            critical.append(f"Required tag '{tag}' missing from dictionary")
        elif dictionary[tag] is None:
            critical.append(f"Required tag '{tag}' is unmapped")

    # Language codes (_en, _jp, etc.) should typically be self-mapped
    for en_tag, jp_tag in dictionary.items():
        if re.match(r"^_[a-z]{2}(-[a-z]{2})?$", en_tag):
            # Some language codes might not exist in JP wiki, that's okay
            if jp_tag and jp_tag != en_tag:
                warnings.append(f"Language code '{en_tag}' mapped to '{jp_tag}' instead of self")

    # Simple alphanumeric tags might be unnecessarily translated
    for en_tag, jp_tag in dictionary.items():
        if re.match(r"^[a-z0-9]+$", en_tag) and len(en_tag) <= 10:
            if jp_tag and jp_tag != en_tag and not any(ord(c) > 127 for c in jp_tag):
                # Only warn if it's not a known exception
                if en_tag not in {"sapphire"}:  # Known exceptions
                    warnings.append(f"Simple tag '{en_tag}' unnecessarily mapped to '{jp_tag}'")

    return critical, warnings
