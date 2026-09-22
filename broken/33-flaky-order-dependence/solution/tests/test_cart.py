from shop import catalog
from shop.cart import Cart


def test_new_cart_has_no_notes():
    assert Cart().notes == []


def test_add_note():
    cart = Cart()
    cart.note("gift wrap")
    assert cart.notes == ["gift wrap"]


def test_checkout_total_includes_tax():
    cart = Cart()
    cart.add("plum", 2)
    assert cart.checkout() == (480, "USD")      # 2 x 200 + 20% tax


def test_checkout_reserved_the_stock():
    cart = Cart()
    cart.add("plum", 2)
    cart.checkout()                              # does its own setup instead of relying on another test
    assert catalog.stock("plum") == 3           # 5 - 2 reserved
