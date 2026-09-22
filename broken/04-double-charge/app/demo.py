"""Reproduce the incident: the server commits, the response is lost, the client retries.

    python demo.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from client import ChargeClient  # noqa: E402
from payments import PaymentService  # noqa: E402


class LossyTransport:
    """Delivers the request, then loses the first `lose` responses (timeout at the client)."""

    def __init__(self, service, lose=1):
        self.service, self.lose = service, lose

    def post(self, path, headers, body):
        result = self.service.handle_charge(headers, body)
        if self.lose > 0:
            self.lose -= 1
            raise TimeoutError("response lost")
        return result


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        svc = PaymentService(os.path.join(d, "pay.db"))
        client = ChargeClient(LossyTransport(svc, lose=1), sleep=lambda s: None)
        print(client.charge("cust_1", 4999, "USD", "order_77"))
        print("ledger rows:", len(svc.ledger()))
