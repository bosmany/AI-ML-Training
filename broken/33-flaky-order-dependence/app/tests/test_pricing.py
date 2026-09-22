from shop import pricing


def test_default_tax():
    assert pricing.with_tax(1000) == 1200


def test_default_currency():
    assert pricing.currency() == "USD"


def test_zero_tax_when_configured():
    pricing.configure(tax_rate=0.0)
    assert pricing.with_tax(1000) == 1000


def test_currency_can_change():
    pricing.configure(currency="EUR")
    assert pricing.currency() == "EUR"
