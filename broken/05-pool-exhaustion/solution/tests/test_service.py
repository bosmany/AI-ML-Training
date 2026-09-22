import pytest

from service import NotFound, ValidationError


def test_create_and_get(svc):
    oid = svc.create_order("alice", 1999)
    assert svc.get_order(oid) == {"id": oid, "customer": "alice", "status": "new", "total_cents": 1999}


def test_get_missing_raises_not_found(svc):
    with pytest.raises(NotFound):
        svc.get_order(12345)


@pytest.mark.parametrize("customer,total", [("", 100), ("bob", 0), ("bob", -1), ("bob", "12")])
def test_invalid_create_raises(svc, customer, total):
    with pytest.raises(ValidationError):
        svc.create_order(customer, total)


def test_cancel_flow(svc):
    oid = svc.create_order("alice", 500)
    assert svc.cancel_order(oid) is True
    assert svc.get_order(oid)["status"] == "cancelled"
    with pytest.raises(NotFound):
        svc.cancel_order(999)


def test_shipped_orders_cannot_be_cancelled(svc):
    oid = svc.create_order("alice", 500)
    with svc.pool.connection() as conn:
        conn.execute("UPDATE orders SET status='shipped' WHERE id=?", (oid,))
        conn.commit()
    assert svc.cancel_order(oid) is False
    assert svc.get_order(oid)["status"] == "shipped"


def test_list_orders(svc):
    a = svc.create_order("alice", 1)
    svc.create_order("bob", 2)
    b = svc.create_order("alice", 3)
    assert [o["id"] for o in svc.list_orders("alice")] == [a, b]
