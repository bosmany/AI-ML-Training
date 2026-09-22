"""Prevention: after ANY kind of request the pool must be fully available again."""
import pytest

from service import NotFound, ValidationError


def _run(fn, *args):
    try:
        fn(*args)
    except (NotFound, ValidationError):
        pass


def test_no_request_type_leaks_a_connection(svc):
    oid = svc.create_order("a", 100)
    with svc.pool.connection() as conn:
        conn.execute("UPDATE orders SET status='shipped' WHERE id=?", (oid,))
        conn.commit()
    for fn, args in [(svc.get_order, (oid,)), (svc.get_order, (999,)), (svc.create_order, ("", 1)),
                     (svc.create_order, ("b", 1)), (svc.cancel_order, (oid,)), (svc.cancel_order, (999,)),
                     (svc.list_orders, ("a",))]:
        _run(fn, *args)
        assert svc.pool.in_use == 0, "%s%r leaked a connection" % (fn.__name__, args)
