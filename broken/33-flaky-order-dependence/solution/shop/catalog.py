"""Stock levels (in production this would be a DB; here a module-level dict)."""


class OutOfStock(Exception):
    pass


_INITIAL = {"apple": 10, "pear": 4, "plum": 5, "fig": 0}
_STOCK = dict(_INITIAL)


def reset():
    """Back to the initial stock (used by the test suite between tests)."""
    _STOCK.clear()
    _STOCK.update(_INITIAL)


def stock(sku):
    return _STOCK[sku]


def reserve(sku, qty):
    if _STOCK[sku] < qty:
        raise OutOfStock(f"{sku}: have {_STOCK[sku]}, need {qty}")
    _STOCK[sku] -= qty


def restock(sku, qty):
    _STOCK[sku] += qty
