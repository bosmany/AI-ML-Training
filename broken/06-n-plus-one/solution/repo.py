"""Data access for GET /reports/orders."""


def orders_report(conn, customer_id):
    """The customer's orders, newest first (ties broken by id, newest first), each with its lines.

    Returns None if the customer does not exist. Orders without lines are included with items == [].
    Two statements no matter how many orders: the customer, then orders LEFT JOIN lines LEFT JOIN products.
    """
    customer = conn.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if customer is None:
        return None
    rows = conn.execute(
        "SELECT o.id AS order_id, o.created_at, o.status, l.product_id, l.qty, p.name, p.price_cents "
        "FROM orders o "
        "LEFT JOIN order_items l ON l.order_id = o.id "
        "LEFT JOIN products p ON p.id = l.product_id "
        "WHERE o.customer_id = ? "
        "ORDER BY o.created_at DESC, o.id DESC, l.id", (customer_id,)).fetchall()
    orders = {}
    for r in rows:                                   # dicts keep insertion order, which is the SQL order
        order = orders.get(r["order_id"])
        if order is None:
            order = orders[r["order_id"]] = {"id": r["order_id"], "created_at": r["created_at"],
                                             "status": r["status"], "items": [], "total_cents": 0}
        if r["product_id"] is not None:
            line = r["price_cents"] * r["qty"]
            order["items"].append({"product_id": r["product_id"], "name": r["name"], "qty": r["qty"],
                                   "unit_cents": r["price_cents"], "line_cents": line})
            order["total_cents"] += line
    return {"customer": {"id": customer["id"], "name": customer["name"]}, "orders": list(orders.values())}
