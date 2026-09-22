"""Payments service: POST /charges.  See API.md for the documented contract."""
import contextlib
import hashlib
import json
import sqlite3
import time
import uuid

CURRENCIES = {"USD", "EUR", "GBP"}


class ProcessorError(Exception):
    """The card processor could not be reached / errored."""


class Processor:
    """Stand-in for the card processor. Takes ~20 ms, like the real thing on a good day."""

    def __init__(self, latency=0.02):
        self.latency = latency

    def authorize(self, customer_id, amount_cents, currency):
        time.sleep(self.latency)
        return "auth_" + uuid.uuid4().hex[:12]


class PaymentService:
    def __init__(self, db_path, processor=None):
        self.db_path = db_path
        self.processor = processor or Processor()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS charges ("
                " id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, amount_cents INTEGER NOT NULL,"
                " currency TEXT NOT NULL, order_id TEXT NOT NULL, auth_id TEXT NOT NULL, created_at REAL NOT NULL)")
            # One row per (customer, key): claimed atomically BEFORE the processor is called.
            conn.execute(
                "CREATE TABLE IF NOT EXISTS idempotency_keys ("
                " customer_id TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,"
                " status TEXT NOT NULL, status_code INTEGER, response TEXT, created_at REAL NOT NULL,"
                " PRIMARY KEY (customer_id, key))")

    @contextlib.contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _validate(body):
        if not isinstance(body, dict):
            return "body must be an object"
        for field in ("customer_id", "order_id", "currency"):
            if not isinstance(body.get(field), str) or not body[field]:
                return "%s is required" % field
        if body["currency"] not in CURRENCIES:
            return "unsupported currency"
        amount = body.get("amount_cents")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return "amount_cents must be a positive integer"
        return None

    @staticmethod
    def _key(headers):
        for name, value in (headers or {}).items():
            if name.lower() == "idempotency-key" and value:
                return str(value)[:255]
        return None

    def handle_charge(self, headers, body):
        """Create a charge. Returns (http_status, response_body)."""
        error = self._validate(body)
        if error:
            return 400, {"error": error}
        key = self._key(headers)
        if key is None:
            return self._create_charge(body)
        request_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        customer = body["customer_id"]
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")          # serialises concurrent claims on the same key
            row = conn.execute("SELECT * FROM idempotency_keys WHERE customer_id=? AND key=?",
                               (customer, key)).fetchone()
            if row is None:
                conn.execute("INSERT INTO idempotency_keys (customer_id, key, request_hash, status, created_at)"
                             " VALUES (?,?,?,?,?)", (customer, key, request_hash, "pending", time.time()))
                conn.execute("COMMIT")
            else:
                conn.execute("COMMIT")
                if row["request_hash"] != request_hash:
                    return 409, {"error": "Idempotency-Key was already used with a different request"}
                if row["status"] == "done":
                    return row["status_code"], json.loads(row["response"])
                return 409, {"error": "a request with this Idempotency-Key is still in progress"}
        status, response = self._create_charge(body)
        with self._connect() as conn:
            if status == 201:
                conn.execute("UPDATE idempotency_keys SET status='done', status_code=?, response=?"
                             " WHERE customer_id=? AND key=?", (status, json.dumps(response), customer, key))
            else:                                    # processor failed: release the key so a retry can succeed
                conn.execute("DELETE FROM idempotency_keys WHERE customer_id=? AND key=?", (customer, key))
        return status, response

    def _create_charge(self, body):
        try:
            auth_id = self.processor.authorize(body["customer_id"], body["amount_cents"], body["currency"])
        except ProcessorError:
            return 502, {"error": "payment processor unavailable"}
        charge = {
            "charge_id": "ch_" + uuid.uuid4().hex[:12],
            "customer_id": body["customer_id"],
            "amount_cents": body["amount_cents"],
            "currency": body["currency"],
            "order_id": body["order_id"],
            "auth_id": auth_id,
            "status": "succeeded",
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO charges (id, customer_id, amount_cents, currency, order_id, auth_id, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (charge["charge_id"], charge["customer_id"], charge["amount_cents"], charge["currency"],
                 charge["order_id"], charge["auth_id"], time.time()))
        return 201, charge

    def ledger(self):
        """Every charge we have recorded (this is what finance reconciles against)."""
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM charges ORDER BY created_at, id")]
