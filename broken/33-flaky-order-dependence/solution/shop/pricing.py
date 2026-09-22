"""Prices and tax. Configuration is process-wide."""

PRICES = {"apple": 100, "pear": 150, "plum": 200, "fig": 300}   # cents
_DEFAULTS = {"currency": "USD", "tax_rate": 0.20}
_CONFIG = dict(_DEFAULTS)


def reset():
    _CONFIG.clear()
    _CONFIG.update(_DEFAULTS)


def configure(**changes):
    _CONFIG.update(changes)


def currency():
    return _CONFIG["currency"]


def with_tax(cents):
    return round(cents * (1 + _CONFIG["tax_rate"]))
