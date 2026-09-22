import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.db"))
    db.init_schema(c)
    c.executescript("""
      INSERT INTO customers VALUES (1,'Ada'),(2,'Bob'),(3,'Cy');
      INSERT INTO products VALUES (1,'pen',150),(2,'ink',900);
      INSERT INTO orders VALUES (10,1,'2025-01-02','paid'),(11,1,'2025-01-03','paid'),(12,1,'2025-01-03','new'),
                                (13,1,'2025-01-01','paid'),(20,2,'2025-01-05','paid');
      INSERT INTO order_items (order_id,product_id,qty) VALUES (10,1,2),(10,2,1),(11,2,3),(20,1,1);
    """)
    c.commit()
    yield c
    c.close()
