import pytest

from lab import cpu_to_millicores, memory_to_bytes, parse_quantity


def test_cpu_quantities_become_millicores():
    cases = {"100m": 100, "1": 1000, "1.5": 1500, "0.25": 250, "2": 2000, "0": 0, "500m": 500, "0.1": 100}
    for text, expected in cases.items():
        assert cpu_to_millicores(text) == expected, f"cpu {text!r} should be {expected}m"


def test_cpu_sub_millicore_values_round_up_like_the_api_server():
    assert cpu_to_millicores("100u") == 1, "0.1m rounds UP to 1m, never down to 0"
    assert cpu_to_millicores("1500u") == 2
    assert cpu_to_millicores("1n") == 1


def test_memory_binary_suffixes_are_powers_of_1024():
    assert memory_to_bytes("512Mi") == 512 * 1024**2
    assert memory_to_bytes("2Gi") == 2 * 1024**3
    assert memory_to_bytes("1Ki") == 1024
    assert memory_to_bytes("1.5Gi") == 1610612736
    assert memory_to_bytes("1Ti") == 1024**4


def test_memory_decimal_suffixes_are_powers_of_1000_and_differ_from_binary():
    assert memory_to_bytes("129M") == 129_000_000
    assert memory_to_bytes("1k") == 1000
    assert memory_to_bytes("1G") == 10**9
    assert memory_to_bytes("1Gi") != memory_to_bytes("1G"), "Gi and G are NOT the same"


def test_exponent_and_plain_integer_forms():
    assert memory_to_bytes("129e6") == 129_000_000
    assert memory_to_bytes("1e3") == 1000
    assert memory_to_bytes("1E3") == 1000, "capital E followed by digits is an exponent"
    assert memory_to_bytes("1E") == 10**18, "capital E with NO digits is the exa suffix"
    assert memory_to_bytes("1024") == 1024
    assert cpu_to_millicores("1e-1") == 100


def test_parse_quantity_is_exact_not_float():
    from decimal import Decimal
    assert parse_quantity("0.1") + parse_quantity("0.2") == Decimal("0.3"), "floats would give 0.30000000000000004"
    assert parse_quantity("100m") == Decimal("0.1")


def test_invalid_quantities_raise_value_error():
    for bad in ["", "abc", "Gi", "1 Gi", "1GI", "1K", "1mi", "1.2.3", "--1", "1e", "12Mi3", " 1", "1 "]:
        with pytest.raises(ValueError):
            parse_quantity(bad)
    with pytest.raises(ValueError):
        parse_quantity(5)  # type: ignore[arg-type]
