"""Prevention: a retried request must never create a second charge."""
import threading

BODY = {"customer_id": "c1", "order_id": "o1", "currency": "USD", "amount_cents": 1250}
KEY = {"Idempotency-Key": "abc"}


def test_replay_is_one_charge(svc):
    first = svc.handle_charge(KEY, dict(BODY))
    assert svc.handle_charge(KEY, dict(BODY)) == first
    assert len(svc.ledger()) == 1


def test_concurrent_duplicates_are_one_charge(svc):
    ts = [threading.Thread(target=svc.handle_charge, args=(KEY, dict(BODY))) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(svc.ledger()) == 1
