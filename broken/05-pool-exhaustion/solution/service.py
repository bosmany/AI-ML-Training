"""Order service (the layer the HTTP handlers call).

Every connection is leased with `with self.pool.connection()`, so it goes back to the pool on
every path: normal return, early return, and exception.
"""


class NotFound(Exception):
    pass


class ValidationError(Exception):
    pass


class OrderService:
    def __init__(self, pool):
        self.pool = pool

    def get_order(self, order_id):
        with self.pool.connection() as conn:
            row = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise NotFound("order %s not found" % order_id)
        return dict(row)

    def create_order(self, customer, total_cents):
        if not customer or not isinstance(total_cents, int) or total_cents <= 0:   # validate before leasing anything
            raise ValidationError("customer and a positive integer total_cents are required")
        with self.pool.connection() as conn:
            cur = conn.execute("INSERT INTO orders (customer, total_cents) VALUES (?, ?)", (customer, total_cents))
            conn.commit()
            return cur.lastrowid

    def cancel_order(self, order_id):
        """Returns True if cancelled, False if it can no longer be cancelled (already shipped)."""
        with self.pool.connection() as conn:
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise NotFound("order %s not found" % order_id)
            if row["status"] == "shipped":
                return False
            conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
            conn.commit()
            return True

    def list_orders(self, customer):
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE customer = ? ORDER BY id",
                                (customer,)).fetchall()
        return [dict(r) for r in rows]
