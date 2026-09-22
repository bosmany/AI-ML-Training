"""Data access for GET /reports/orders."""


def orders_report(conn, customer_id):
    """The customer's orders, newest first (ties broken by id, newest first), each with its lines.

    Returns None if the customer does not exist. Orders without lines are included with items == [].
    """
    customer = conn.execute("SELECT id, name FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if customer is None:
        return None
    report = {"customer": {"id": customer["id"], "name": customer["name"]}, "orders": []}
    orders = conn.execute(
        "SELECT id, created_at, status FROM orders WHERE customer_id = ? ORDER BY created_at DESC, id DESC",
        (customer_id,)).fetchall()
    for order in orders:
        lines = conn.execute("SELECT id, product_id, qty FROM order_items WHERE order_id = ? ORDER BY id",
                             (order["id"],)).fetchall()
        items = []
        for line in lines:
            product = conn.execute("SELECT name, price_cents FROM products WHERE id = ?",
                                   (line["product_id"],)).fetchone()
            items.append({"product_id": line["product_id"], "name": product["name"], "qty": line["qty"],
                          "unit_cents": product["price_cents"], "line_cents": product["price_cents"] * line["qty"]})
        report["orders"].append({"id": order["id"], "created_at": order["created_at"], "status": order["status"],
                                 "items": items, "total_cents": sum(i["line_cents"] for i in items)})
    return report
