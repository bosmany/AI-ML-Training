import repo


def test_unknown_customer(conn):
    assert repo.orders_report(conn, 999) is None


def test_customer_without_orders(conn):
    assert repo.orders_report(conn, 3) == {"customer": {"id": 3, "name": "Cy"}, "orders": []}


def test_order_and_ties(conn):
    r = repo.orders_report(conn, 1)
    assert [o["id"] for o in r["orders"]] == [12, 11, 10, 13]      # newest first, tie -> higher id first


def test_lines_and_totals(conn):
    r = repo.orders_report(conn, 1)
    by_id = {o["id"]: o for o in r["orders"]}
    assert by_id[10]["items"] == [
        {"product_id": 1, "name": "pen", "qty": 2, "unit_cents": 150, "line_cents": 300},
        {"product_id": 2, "name": "ink", "qty": 1, "unit_cents": 900, "line_cents": 900}]
    assert by_id[10]["total_cents"] == 1200
    assert by_id[11]["total_cents"] == 2700


def test_orders_without_lines_are_kept(conn):
    r = repo.orders_report(conn, 1)
    empty = [o for o in r["orders"] if o["id"] in (12, 13)]
    assert len(empty) == 2 and all(o["items"] == [] and o["total_cents"] == 0 for o in empty)


def test_other_customers_are_not_mixed_in(conn):
    assert [o["id"] for o in repo.orders_report(conn, 2)["orders"]] == [20]
