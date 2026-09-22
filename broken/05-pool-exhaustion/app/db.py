"""A small blocking connection pool for SQLite (what a real driver's pool does, minus the network)."""
import contextlib
import queue
import sqlite3
import threading


class PoolTimeout(Exception):
    """No connection became available within the timeout."""


class ConnectionPool:
    def __init__(self, database, size=5, timeout=1.0):
        self.size = size
        self.timeout = timeout
        self._idle = queue.Queue()
        self._leased = set()
        self._lock = threading.Lock()
        for _ in range(size):
            conn = sqlite3.connect(database, check_same_thread=False, timeout=5)
            conn.row_factory = sqlite3.Row
            self._idle.put(conn)

    @property
    def in_use(self):
        with self._lock:
            return len(self._leased)

    def acquire(self):
        try:
            conn = self._idle.get(timeout=self.timeout)
        except queue.Empty:
            raise PoolTimeout("timed out waiting for a database connection (%d/%d in use)"
                              % (self.in_use, self.size)) from None
        with self._lock:
            self._leased.add(id(conn))
        return conn

    def release(self, conn):
        with self._lock:
            if id(conn) not in self._leased:
                raise RuntimeError("connection is not leased from this pool")
            self._leased.discard(id(conn))
        conn.rollback()
        self._idle.put(conn)

    @contextlib.contextmanager
    def connection(self):
        """Lease a connection for the duration of a `with` block; always returned."""
        conn = self.acquire()
        try:
            yield conn
        finally:
            self.release(conn)

    def close(self):
        while not self._idle.empty():
            self._idle.get_nowait().close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY, customer TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', total_cents INTEGER NOT NULL);
"""


def init_db(database):
    conn = sqlite3.connect(database)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
