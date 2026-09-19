"""Kubernetes resource.Quantity parsing ("100m", "2Gi", "129e6", "129M", "1.5" ...)."""
from __future__ import annotations

from decimal import Decimal

# Suffix tables (given). Binary: powers of 1024. Decimal: powers of 1000 (n u m "" k M G T P E).
BINARY = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40, "Pi": 2**50, "Ei": 2**60}
DECIMAL = {"n": Decimal("1e-9"), "u": Decimal("1e-6"), "m": Decimal("1e-3"), "": Decimal(1),
           "k": Decimal("1e3"), "M": Decimal("1e6"), "G": Decimal("1e9"), "T": Decimal("1e12"),
           "P": Decimal("1e15"), "E": Decimal("1e18")}


def parse_quantity(text: str) -> Decimal:
    """Exact value of a quantity as a ``Decimal`` (never float: 0.1 + 0.2 must equal 0.3).

    TODO: a signed decimal number followed by NOTHING, a suffix from the tables above, or a decimal
    exponent ("e6", "E-3"). Gotchas: "1E" is exa but "1E3" is an exponent; "K" (capital) and "mi" are
    invalid; no whitespace allowed. Raise ``ValueError`` for anything else, including non-strings.
    """
    raise NotImplementedError


def cpu_to_millicores(text: str) -> int:
    """CPU quantity in millicores, rounded UP ("100u" -> 1, never 0)."""
    raise NotImplementedError


def memory_to_bytes(text: str) -> int:
    """Memory quantity in whole bytes, rounded up."""
    raise NotImplementedError
