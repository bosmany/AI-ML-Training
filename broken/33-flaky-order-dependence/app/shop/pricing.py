"""Prices and tax. Configuration is process-wide."""

PRICES = {"apple": 100, "pear": 150, "plum": 200, "fig": 300}   # cents
_CONFIG = {"currency": "USD", "tax_rate": 0.20}


def configure(**changes):
    _CONFIG.update(changes)


def currency():
    return _CONFIG["currency"]


def with_tax(cents):
    return round(cents * (1 + _CONFIG["tax_rate"]))
