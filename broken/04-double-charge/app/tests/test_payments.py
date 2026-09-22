import pytest

BODY = {"customer_id": "c1", "order_id": "o1", "currency": "USD", "amount_cents": 1250}


def test_charge_is_recorded(svc):
    status, resp = svc.handle_charge({}, dict(BODY))
    assert status == 201
    assert resp["status"] == "succeeded" and resp["amount_cents"] == 1250
    rows = svc.ledger()
    assert len(rows) == 1 and rows[0]["id"] == resp["charge_id"]


@pytest.mark.parametrize("patch", [
    {"amount_cents": 0}, {"amount_cents": -5}, {"amount_cents": "12"}, {"currency": "XXX"},
    {"customer_id": ""}, {"order_id": None}])
def test_validation_errors(svc, patch):
    status, resp = svc.handle_charge({}, dict(BODY, **patch))
    assert status == 400 and "error" in resp
    assert svc.ledger() == []


def test_two_purchases_are_two_charges(svc):
    svc.handle_charge({"Idempotency-Key": "k1"}, dict(BODY, order_id="o1"))
    svc.handle_charge({"Idempotency-Key": "k2"}, dict(BODY, order_id="o2"))
    assert len(svc.ledger()) == 2


def test_processor_failure_returns_502(tmp_path):
    from payments import PaymentService, ProcessorError

    class Down:
        def authorize(self, *a):
            raise ProcessorError()

    svc = PaymentService(str(tmp_path / "p.db"), Down())
    assert svc.handle_charge({}, dict(BODY))[0] == 502
    assert svc.ledger() == []
