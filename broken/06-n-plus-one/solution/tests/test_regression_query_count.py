"""Prevention: the number of statements must not depend on how much data the customer has."""
import repo


def _count(conn, customer_id):
    seen = []
    conn.set_trace_callback(seen.append)
    repo.orders_report(conn, customer_id)
    conn.set_trace_callback(None)
    return len(seen)


def test_query_count_is_constant(conn):
    small = _count(conn, 2)
    for o in range(100, 300):
        conn.execute("INSERT INTO orders VALUES (?,1,'2025-02-01','paid')", (o,))
        conn.execute("INSERT INTO order_items (order_id,product_id,qty) VALUES (?,1,1)", (o,))
    conn.commit()
    assert _count(conn, 1) == small
    assert _count(conn, 1) <= 4
