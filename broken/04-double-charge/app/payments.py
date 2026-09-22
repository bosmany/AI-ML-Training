"""Payments service: POST /charges.  See API.md for the documented contract."""
import contextlib
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

    def handle_charge(self, headers, body):
        """Create a charge. Returns (http_status, response_body)."""
        error = self._validate(body)
        if error:
            return 400, {"error": error}
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
