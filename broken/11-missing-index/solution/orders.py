"""Read side of the order-history API. Both functions are called on every page view."""

RECENT_SQL = """
    SELECT id, total_cents, created_at
    FROM orders
    WHERE customer_id = ?
    ORDER BY created_at DESC, id DESC
    LIMIT ?
"""

SUMMARY_SQL = """
    SELECT COUNT(*), COALESCE(SUM(total_cents), 0)
    FROM orders
    WHERE customer_id = ? AND status != 'cancelled'
"""


def recent_orders(conn, customer_id, limit=20):
    """Newest orders first: [(id, total_cents, created_at), ...]"""
    return conn.execute(RECENT_SQL, (customer_id, limit)).fetchall()


def customer_summary(conn, customer_id):
    """(number of non-cancelled orders, their total in cents)"""
    return conn.execute(SUMMARY_SQL, (customer_id,)).fetchone()
