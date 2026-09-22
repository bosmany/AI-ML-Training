"""Client used by the checkout service to call POST /charges."""
import time
import uuid


class ChargeClient:
    """Retries when the response is lost (timeout). One logical charge = one Idempotency-Key,
    re-sent unchanged on every retry, as the API documentation asks."""

    def __init__(self, transport, max_attempts=3, sleep=time.sleep):
        self.transport = transport
        self.max_attempts = max_attempts
        self.sleep = sleep

    def charge(self, customer_id, amount_cents, currency, order_id, idempotency_key=None):
        key = idempotency_key or str(uuid.uuid4())
        body = {"customer_id": customer_id, "amount_cents": amount_cents,
                "currency": currency, "order_id": order_id}
        last = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.transport.post("/charges", {"Idempotency-Key": key}, body)
            except TimeoutError as exc:
                last = exc
                self.sleep(0.05 * attempt)
        raise last
