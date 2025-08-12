"""Tests for validation logic."""

from src.validator import validate_business_rules


def test_validate_object_classes():
    """Test object class validation."""
    dictionary = {
        "safe": "safe",  # Correct
        "euclid": "ユークリッド",  # Wrong - should be self-mapped
        "keter": "keter",  # Correct
        # Include required tags to avoid interference
        "scp": "scp",
        "tale": "tale",
        "goi-format": "goi-format",
        "supplement": "supplement",
        "joke": "joke",
    }

    critical, warnings = validate_business_rules(dictionary)

    assert len(critical) == 1
    assert "Object class 'euclid'" in critical[0]


def test_validate_series_numbers():
    """Test series number validation."""
    dictionary = {
        "1000": "1000",  # Correct
        "2000": "二千",  # Wrong - should be self-mapped
        "3000": "3000",  # Correct
        # Include required tags to avoid interference
        "scp": "scp",
        "tale": "tale",
        "goi-format": "goi-format",
        "supplement": "supplement",
        "joke": "joke",
    }

    critical, warnings = validate_business_rules(dictionary)

    assert len(critical) == 1
    assert "Series '2000'" in critical[0]


def test_validate_required_tags():
    """Test required tags validation."""
    dictionary = {
        "scp": "scp",
        "tale": None,  # Unmapped - critical
        # "goi-format" missing - critical
        "supplement": "supplement",  # Include to reduce noise
        "joke": "joke",  # Include to reduce noise
    }

    critical, warnings = validate_business_rules(dictionary)

    assert len(critical) == 2
    assert any("Required tag 'tale' is unmapped" in c for c in critical)
    assert any("Required tag 'goi-format' missing" in c for c in critical)


def test_validate_language_codes():
    """Test language code validation."""
    dictionary = {
        "_en": "_en",  # Correct
        "_jp": "_ja",  # Wrong but just a warning
        "_fr": None,  # Unmapped is okay for language codes
        # Include required tags to avoid interference
        "scp": "scp",
        "tale": "tale",
        "goi-format": "goi-format",
        "supplement": "supplement",
        "joke": "joke",
    }

    critical, warnings = validate_business_rules(dictionary)

    assert len(critical) == 0
    assert len(warnings) == 1
    assert "Language code '_jp'" in warnings[0]


def test_validate_simple_tags():
    """Test simple alphanumeric tag validation."""
    dictionary = {
        "test123": "test123",  # Self-mapped is fine
        "simple": "シンプル",  # Translated to Japanese is fine
        "code": "code2",  # Unnecessarily changed - warning
        "sapphire": "saphir",  # Known exception
        # Include required tags to avoid interference
        "scp": "scp",
        "tale": "tale",
        "goi-format": "goi-format",
        "supplement": "supplement",
        "joke": "joke",
    }

    critical, warnings = validate_business_rules(dictionary)

    assert len(critical) == 0
    assert len(warnings) == 1
    assert "Simple tag 'code'" in warnings[0]
    assert "sapphire" not in str(warnings)  # Should not warn about known exception


def test_validate_all_good():
    """Test with a perfect dictionary."""
    dictionary = {
        "safe": "safe",
        "euclid": "euclid",
        "keter": "keter",
        "scp": "scp",
        "tale": "tale",
        "goi-format": "goi-format",
        "supplement": "supplement",
        "joke": "joke",
        "_en": "_en",
        "1000": "1000",
    }

    critical, warnings = validate_business_rules(dictionary)

    assert len(critical) == 0
    assert len(warnings) == 0
