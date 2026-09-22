"""Schema for the order-history service (SQLite). `apply()` is run once on an empty database."""

SCHEMA = [
    """
    CREATE TABLE orders (
        id           INTEGER PRIMARY KEY,
        customer_id  INTEGER NOT NULL,
        status       TEXT    NOT NULL,      -- 'open' | 'shipped' | 'cancelled'
        total_cents  INTEGER NOT NULL,
        created_at   INTEGER NOT NULL       -- unix seconds
    )
    """,
    # status has only three distinct values; it is used by the nightly report.
    "CREATE INDEX idx_orders_status ON orders(status)",
]


def apply(conn):
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()
