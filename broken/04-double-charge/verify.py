#!/usr/bin/env python3
"""Verifier for 04-double-charge.  Usage: python verify.py   (BROKEN_TARGET=solution to check the reference)"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_common"))
from harness import Verifier  # noqa: E402

BODY = {"customer_id": "cust_1", "order_id": "order_1", "currency": "USD", "amount_cents": 4999}


def probe_scenarios():
    import json
    import tempfile
    import threading
    from client import ChargeClient
    from payments import PaymentService, Processor, ProcessorError

    class Lossy:
        """Server commits, then the response is lost on the first `lose` calls."""
        def __init__(self, svc, lose):
            self.svc, self.lose = svc, lose

        def post(self, path, headers, body):
            result = self.svc.handle_charge(headers, body)
            if self.lose > 0:
                self.lose -= 1
                raise TimeoutError("lost")
            return result

    class Flaky:
        def __init__(self, fail):
            self.fail = fail
            self.inner = Processor(latency=0)

        def authorize(self, *a):
            if self.fail > 0:
                self.fail -= 1
                raise ProcessorError()
            return self.inner.authorize(*a)

    out = {}
    import atexit
    import shutil
    d = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, d, True)

    def fresh(name, processor=None):
        return PaymentService(os.path.join(d, name + ".db"), processor or Processor(latency=0.02))

    def key(k):
        return {"Idempotency-Key": k}

    # 1. response lost, client retries (twice)
    for lose in (1, 2):
        s = fresh("lost%d" % lose)
        try:
            status, resp = ChargeClient(Lossy(s, lose), sleep=lambda x: None).charge(
                "cust_1", 4999, "USD", "order_1")
            out["retry_%d" % lose] = [status, len(s.ledger())]
        except Exception as exc:
            out["retry_%d" % lose] = ["error: %r" % exc, len(s.ledger())]

    # 2. sequential replay returns the original response
    s = fresh("replay")
    a = s.handle_charge(key("k1"), dict(BODY))
    b = s.handle_charge(key("k1"), dict(BODY))
    out["replay"] = [a == b and a[0] == 201, len(s.ledger())]

    # 3. different keys, same customer and amount: both must be charged
    s = fresh("distinct")
    s.handle_charge(key("k1"), dict(BODY, order_id="order_1"))
    s.handle_charge(key("k2"), dict(BODY, order_id="order_2"))
    out["distinct"] = len(s.ledger())

    # 4. no key: legacy clients are not de-duplicated
    s = fresh("nokey")
    s.handle_charge({}, dict(BODY))
    s.handle_charge({}, dict(BODY))
    out["nokey"] = len(s.ledger())

    # 5. same key, different body -> 409
    s = fresh("mismatch")
    s.handle_charge(key("k1"), dict(BODY))
    status, _ = s.handle_charge(key("k1"), dict(BODY, amount_cents=1))
    out["mismatch"] = [status, len(s.ledger())]

    # 6. key is scoped per customer
    s = fresh("scope")
    s.handle_charge(key("shared"), dict(BODY, customer_id="cust_A"))
    s.handle_charge(key("shared"), dict(BODY, customer_id="cust_B"))
    out["scope"] = len(s.ledger())

    # 7. eight concurrent duplicates
    s = fresh("race")
    barrier = threading.Barrier(8)
    results = []

    def worker():
        barrier.wait()
        results.append(s.handle_charge(key("race-key"), dict(BODY)))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    created = [r for r in results if r[0] == 201]
    out["race"] = {"ledger": len(s.ledger()), "statuses": sorted({r[0] for r in results}),
                   "same_body": all(r == created[0] for r in created) if created else False}

    # 8. processor failure must not burn the key
    s = fresh("procfail", Flaky(1))
    first = s.handle_charge(key("k9"), dict(BODY))
    second = s.handle_charge(key("k9"), dict(BODY))
    out["procfail"] = [first[0], second[0], len(s.ledger())]

    # 9. keys survive a restart
    p = os.path.join(d, "restart.db")
    s1 = PaymentService(p, Processor(latency=0))
    s1.handle_charge(key("k1"), dict(BODY))
    s2 = PaymentService(p, Processor(latency=0))
    s2.handle_charge(key("k1"), dict(BODY))
    out["restart"] = len(s2.ledger())
    print(json.dumps(out))


def main():
    v = Verifier(__file__)
    o, err = v.probe(__file__, "scenarios", timeout=40)
    if o is None:
        v.check("scenarios run", False, err)
    else:
        v.check("lost response + 1 retry -> exactly one charge", o["retry_1"] == [201, 1], str(o["retry_1"]))
        v.check("lost responses + 2 retries -> exactly one charge", o["retry_2"] == [201, 1], str(o["retry_2"]))
        v.check("replayed request returns the original response, no new charge", o["replay"] == [True, 1], str(o["replay"]))
        v.check("different keys are different charges", o["distinct"] == 2, "ledger rows: %s" % o["distinct"])
        v.check("requests without a key are not de-duplicated", o["nokey"] == 2, "ledger rows: %s" % o["nokey"])
        v.check("same key with a different body is rejected with 409", o["mismatch"] == [409, 1], str(o["mismatch"]))
        v.check("keys are scoped per customer", o["scope"] == 2, "ledger rows: %s" % o["scope"])
        r = o["race"]
        v.check("8 concurrent duplicates -> exactly one charge",
                r["ledger"] == 1 and set(r["statuses"]) <= {201, 409} and 201 in r["statuses"] and r["same_body"], str(r))
        v.check("processor failure does not burn the key (502 then retry succeeds once)",
                o["procfail"][0] >= 500 and o["procfail"][1:] == [201, 1], str(o["procfail"]))
        v.check("keys survive a service restart", o["restart"] == 1, "ledger rows: %s" % o["restart"])
    v.pytest()
    v.finish()


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--probe":
        sys.path.insert(0, os.environ["BROKEN_TARGET_DIR"])
        globals()["probe_" + sys.argv[2]]()
    else:
        main()
