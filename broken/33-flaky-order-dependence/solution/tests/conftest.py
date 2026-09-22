import pytest

from shop import catalog, pricing


@pytest.fixture(autouse=True)
def _fresh_shop_state():
    """Every test starts from (and leaves behind) the pristine module-level state."""
    catalog.reset()
    pricing.reset()
    yield
    catalog.reset()
    pricing.reset()
