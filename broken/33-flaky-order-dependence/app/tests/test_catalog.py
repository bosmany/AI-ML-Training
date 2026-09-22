import pytest

from shop import catalog


def test_initial_apple_stock():
    assert catalog.stock("apple") == 10


def test_reserve_reduces_stock():
    catalog.reserve("apple", 3)
    assert catalog.stock("apple") == 7


def test_reserve_out_of_stock_raises():
    with pytest.raises(catalog.OutOfStock):
        catalog.reserve("fig", 1)


def test_restock_adds_units():
    catalog.restock("pear", 6)
    assert catalog.stock("pear") == 10
