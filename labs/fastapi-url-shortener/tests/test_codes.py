"""Code generation and custom-code validation."""

from __future__ import annotations

import string

import pytest

from lab.codes import generate_code, validate_custom_code
from lab.errors import ValidationFailed

BASE62 = set(string.ascii_letters + string.digits)


def test_generated_code_is_fixed_length_seven_by_default_and_honours_an_explicit_length() -> None:
    assert len(generate_code()) == 7, "generated codes are FIXED length (7 by default)"
    assert len(generate_code(12)) == 12


def test_generated_codes_are_random_base62() -> None:
    codes = [generate_code() for _ in range(200)]
    for code in codes:
        assert set(code) <= BASE62, f"{code!r} contains a non base62 character"
    assert len(set(codes)) > 150, "codes look constant / badly random"


def test_valid_custom_code_is_returned_unchanged() -> None:
    assert validate_custom_code("My-link_01") == "My-link_01"


def test_malformed_and_reserved_custom_codes_are_rejected() -> None:
    for bad in ["ab", "", "a" * 33, "has space", "semi;colon", "slash/es", "dot.ted", "émoji"]:
        with pytest.raises(ValidationFailed):
            validate_custom_code(bad)
    # reserved words, in any letter case
    for reserved in ["docs", "DOCS", "Links", "openapi.json", "redoc"]:
        with pytest.raises(ValidationFailed, match="reserved"):
            validate_custom_code(reserved)
