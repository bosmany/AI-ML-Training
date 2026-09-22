import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import ConnectionPool, init_db  # noqa: E402
from service import OrderService  # noqa: E402


@pytest.fixture
def svc(tmp_path):
    path = str(tmp_path / "shop.db")
    init_db(path)
    pool = ConnectionPool(path, size=3, timeout=0.2)
    yield OrderService(pool)
    pool.close()
