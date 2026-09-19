"""Kubernetes resource.Quantity parsing ("100m", "2Gi", "129e6", "129M", "1.5" ...)."""
from __future__ import annotations

import math
import re
from decimal import Decimal

_BINARY = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "Pi": 2**50, "Ei": 2**60}
_DECIMAL = {"n": Decimal("1e-9"), "u": Decimal("1e-6"), "m": Decimal("1e-3"), "": Decimal(1),
            "k": Decimal("1e3"), "M": Decimal("1e6"), "G": Decimal("1e9"), "T": Decimal("1e12"),
            "P": Decimal("1e15"), "E": Decimal("1e18")}
# number, then EITHER a decimal exponent (e6 / E-3) OR a suffix. Note: "1E" is exa, "1E3" is 1000.
_RE = re.compile(r"^(?P<num>[+-]?(?:\d+\.?\d*|\.\d+))(?:(?P<exp>[eE][+-]?\d+)|(?P<suffix>Ki|Mi|Gi|Ti|Pi|Ei|[numkMGTPE]))?$")


def parse_quantity(text: str) -> Decimal:
    """Exact value of a quantity as a ``Decimal``. Raises ``ValueError`` on anything malformed."""
    if not isinstance(text, str):
        raise ValueError(f"quantity must be a string, got {type(text).__name__}")
    m = _RE.match(text)
    if m is None:
        raise ValueError(f"invalid Kubernetes quantity: {text!r}")
    value = Decimal(m["num"])
    if m["exp"]:
        return value * Decimal(f"1{m['exp']}")
    suffix = m["suffix"] or ""
    if suffix in _BINARY:
        return value * _BINARY[suffix]
    return value * _DECIMAL[suffix]


def cpu_to_millicores(text: str) -> int:
    """CPU quantity in millicores, rounded UP like the API server does ("100u" -> 1)."""
    return math.ceil(parse_quantity(text) * 1000)


def memory_to_bytes(text: str) -> int:
    """Memory quantity in bytes, rounded up to a whole byte."""
    return math.ceil(parse_quantity(text))
