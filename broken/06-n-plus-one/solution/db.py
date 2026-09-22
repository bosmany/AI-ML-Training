"""SQLite helpers for the reporting service."""
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products  (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
  created_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
  product_id INTEGER NOT NULL REFERENCES products(id), qty INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
"""


def connect(path, latency_ms=0.0):
    """Open a connection. latency_ms simulates the network round trip of a real database server,
    charged once per statement (this is what makes chatty code slow in production)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    if latency_ms:
        conn.set_trace_callback(lambda _sql: time.sleep(latency_ms / 1000.0))
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()
