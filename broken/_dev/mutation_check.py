#!/usr/bin/env python3
"""Maintainer tool (spoilers!): mutation sanity for the runnable labs.

Applies plausible WRONG fixes (band-aids) and a few alternative CORRECT fixes to a copy of the code and runs
the lab's verify.py against it via BROKEN_APP_DIR.  Every wrong fix must FAIL, every alternative must PASS.

    python broken/_dev/mutation_check.py            # all
    python broken/_dev/mutation_check.py 04
"""
import os
import shutil
import subprocess
import sys
import tempfile

BROKEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = "solution"

# (lab number, name, base dir ('app' or 'solution'), expected verdict, [(file, old, new), ...])
M = [
    ("01", "remove the cache entirely", "app", "fail",
     [("service.py", "report = _CACHE[key] = _render(key)", "report = _render(key)")]),
    ("01", "cap so large it never triggers", "app", "fail",
     [("service.py", "        report = _CACHE[key] = _render(key)\n",
       "        report = _CACHE[key] = _render(key)\n        if len(_CACHE) > 10_000_000:\n            _CACHE.clear()\n")]),
    ("01", "clear the whole cache every 100 entries", "app", "fail",
     [("service.py", "        report = _CACHE[key] = _render(key)\n",
       "        if len(_CACHE) >= 100:\n            _CACHE.clear()\n        report = _CACHE[key] = _render(key)\n")]),
    ("01", "gc.collect() after each miss", "app", "fail",
     [("service.py", "        report = _CACHE[key] = _render(key)\n",
       "        report = _CACHE[key] = _render(key)\n        import gc; gc.collect()\n")]),
    ("01", "ALT CORRECT: functools.lru_cache(maxsize=2048)", "app", "pass",
     [("service.py", "_CACHE = {}", "import functools"),
      ("service.py", "    key = _normalise(query)\n    report = _CACHE.get(key)\n    if report is None:\n        report = _CACHE[key] = _render(key)\n    return report\n",
       "    return _cached(_normalise(query))\n\n\n@functools.lru_cache(maxsize=2048)\ndef _cached(key):\n    return _render(key)\n")]),

    ("02", "truncate the input to 24 chars", S, "fail",
     [("validators.py", "def is_valid_username(value):\n", "def is_valid_username(value):\n    value = value[:24] if isinstance(value, str) else value\n"),
      ("validators.py", "def is_valid_tag_list(value):\n", "def is_valid_tag_list(value):\n    value = value[:24] if isinstance(value, str) else value\n")]),
    ("02", "reject anything containing '!'", "app", "fail",
     [("validators.py", "def is_valid_username(value):\n", "def is_valid_username(value):\n    if isinstance(value, str) and '!' in value:\n        return False\n"),
      ("validators.py", "def is_valid_tag_list(value):\n", "def is_valid_tag_list(value):\n    if isinstance(value, str) and '!' in value:\n        return False\n")]),
    ("02", "tighter length cap (20 chars)", "app", "fail",
     [("validators.py", "3 <= len(value) <= 64", "3 <= len(value) <= 20"),
      ("validators.py", "len(value) <= 256", "len(value) <= 20")]),
    ("02", "timeout in a helper thread (keeps burning CPU)", "app", "fail",
     [("validators.py", "import re\n", "import re\nimport threading\n\n\ndef _limited(pattern, value):\n    box = [False]\n\n    def run():\n        box[0] = bool(pattern.match(value))\n    t = threading.Thread(target=run, daemon=True)\n    t.start()\n    t.join(0.01)\n    return box[0]\n"),
      ("validators.py", "bool(_USERNAME.match(value))", "_limited(_USERNAME, value)"),
      ("validators.py", "bool(_TAGS.match(value))", "_limited(_TAGS, value)")]),
    ("02", "ALT CORRECT: possessive quantifiers", "app", "pass",
     [("validators.py", r'r"^([a-zA-Z0-9]+[._-]?)+$"', r'r"^(?:[a-zA-Z0-9]++[._-]?+)++$"'),
      ("validators.py", r'r"^([\w-]+,?)*$"', r'r"^(?:[\w-]++,?+)*+$"')]),

    ("04", "disable client retries", "app", "fail",
     [("client.py", "max_attempts=3", "max_attempts=1")]),
    ("04", "in-memory set of seen keys", "app", "fail",
     [("payments.py", "    def handle_charge(self, headers, body):\n",
       "    _SEEN = {}\n\n    def handle_charge(self, headers, body):\n        k = (headers or {}).get('Idempotency-Key')\n        if k and (body.get('customer_id'), k) in self._SEEN:\n            return self._SEEN[(body.get('customer_id'), k)]\n        r = self._handle(headers, body)\n        if k:\n            self._SEEN[(body.get('customer_id'), k)] = r\n        return r\n\n    def _handle(self, headers, body):\n")]),
    ("04", "de-duplicate on customer+amount within 60 s", "app", "fail",
     [("payments.py", "        try:\n            auth_id",
       "        with self._connect() as conn:\n            dup = conn.execute('SELECT * FROM charges WHERE customer_id=? AND amount_cents=? AND created_at > ?',\n                               (body['customer_id'], body['amount_cents'], time.time() - 60)).fetchone()\n        if dup:\n            return 201, {'charge_id': dup['id'], 'customer_id': dup['customer_id'], 'amount_cents': dup['amount_cents'],\n                         'currency': dup['currency'], 'order_id': dup['order_id'], 'auth_id': dup['auth_id'], 'status': 'succeeded'}\n        try:\n            auth_id")]),
    ("04", "de-duplicate on order_id (check then act)", "app", "fail",
     [("payments.py", "        try:\n            auth_id",
       "        with self._connect() as conn:\n            dup = conn.execute('SELECT * FROM charges WHERE order_id=?', (body['order_id'],)).fetchone()\n        if dup:\n            return 201, {'charge_id': dup['id'], 'customer_id': dup['customer_id'], 'amount_cents': dup['amount_cents'],\n                         'currency': dup['currency'], 'order_id': dup['order_id'], 'auth_id': dup['auth_id'], 'status': 'succeeded'}\n        try:\n            auth_id")]),
    ("04", "solution without the atomic claim (no BEGIN IMMEDIATE, no unique key)", S, "fail",
     [("payments.py", 'conn.execute("BEGIN IMMEDIATE")          # serialises concurrent claims on the same key\n', ""),
      ("payments.py", " PRIMARY KEY (customer_id, key))", " UNIQUE (customer_id, key, created_at))")]),

    ("05", "fix only get_order", "app", "fail",
     [("service.py", '''        conn = self.pool.acquire()
        row = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise NotFound("order %s not found" % order_id)
        self.pool.release(conn)
        return dict(row)''', '''        with self.pool.connection() as conn:
            row = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise NotFound("order %s not found" % order_id)
        return dict(row)''')]),
    ("05", "swallow the errors that leak (return None)", "app", "fail",
     [("service.py", '        if row is None:\n            raise NotFound("order %s not found" % order_id)\n        self.pool.release(conn)\n        return dict(row)',
       '        if row is None:\n            self.pool.release(conn)\n            return None\n        self.pool.release(conn)\n        return dict(row)'),
      ("service.py", '            raise ValidationError("customer and a positive integer total_cents are required")',
       '            self.pool.release(conn)\n            return None'),
      ("service.py", '        if row["status"] == "shipped":\n            return False',
       '        if row["status"] == "shipped":\n            self.pool.release(conn)\n            return False')]),
    ("05", "bigger pool and longer timeout by default", "app", "fail",
     [("db.py", "size=5, timeout=1.0", "size=200, timeout=30.0")]),
    ("05", "ALT CORRECT: try/finally in every handler", "app", "pass",
     [("service.py", '''        conn = self.pool.acquire()
        row = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise NotFound("order %s not found" % order_id)
        self.pool.release(conn)
        return dict(row)''', '''        conn = self.pool.acquire()
        try:
            row = conn.execute("SELECT id, customer, status, total_cents FROM orders WHERE id = ?", (order_id,)).fetchone()
        finally:
            self.pool.release(conn)
        if row is None:
            raise NotFound("order %s not found" % order_id)
        return dict(row)'''),
      ("service.py", '''        conn = self.pool.acquire()
        if not customer or not isinstance(total_cents, int) or total_cents <= 0:
            raise ValidationError("customer and a positive integer total_cents are required")
        cur = conn.execute("INSERT INTO orders (customer, total_cents) VALUES (?, ?)", (customer, total_cents))
        conn.commit()
        order_id = cur.lastrowid
        self.pool.release(conn)
        return order_id''', '''        if not customer or not isinstance(total_cents, int) or total_cents <= 0:
            raise ValidationError("customer and a positive integer total_cents are required")
        conn = self.pool.acquire()
        try:
            cur = conn.execute("INSERT INTO orders (customer, total_cents) VALUES (?, ?)", (customer, total_cents))
            conn.commit()
            return cur.lastrowid
        finally:
            self.pool.release(conn)'''),
      ("service.py", '''        conn = self.pool.acquire()
        row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            self.pool.release(conn)
            raise NotFound("order %s not found" % order_id)
        if row["status"] == "shipped":
            return False
        conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        conn.commit()
        self.pool.release(conn)
        return True''', '''        conn = self.pool.acquire()
        try:
            row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                raise NotFound("order %s not found" % order_id)
            if row["status"] == "shipped":
                return False
            conn.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
            conn.commit()
            return True
        finally:
            self.pool.release(conn)''')]),

    ("06", "prefetch all products (still a query per order)", "app", "fail",
     [("repo.py", '''            product = conn.execute("SELECT name, price_cents FROM products WHERE id = ?",
                                   (line["product_id"],)).fetchone()''', '''            product = PRODUCTS[line["product_id"]]'''),
      ("repo.py", "    report = {\"customer\"", "    PRODUCTS = {r['id']: r for r in conn.execute('SELECT id, name, price_cents FROM products')}\n    report = {\"customer\"")]),
    ("06", "paginate: LIMIT 50 orders", "app", "fail",
     [("repo.py", "ORDER BY created_at DESC, id DESC\"", "ORDER BY created_at DESC, id DESC LIMIT 50\"")]),
    ("06", "INNER JOIN drops orders without lines", S, "fail",
     [("repo.py", "LEFT JOIN order_items", "JOIN order_items")]),
    ("06", "join but lose the id tie-break", S, "fail",
     [("repo.py", "ORDER BY o.created_at DESC, o.id DESC, l.id", "ORDER BY o.created_at DESC, l.id")]),
    ("06", "ALT CORRECT: three IN-batched queries", "app", "pass",
     [("repo.py", "    for order in orders:\n", "    ids = [o['id'] for o in orders]\n    marks = ','.join('?' * len(ids))\n    lines_by = {}\n    for l in conn.execute('SELECT id, order_id, product_id, qty FROM order_items WHERE order_id IN (%s) ORDER BY id' % marks, ids):\n        lines_by.setdefault(l['order_id'], []).append(l)\n    prods = {p['id']: p for p in conn.execute('SELECT id, name, price_cents FROM products')}\n    for order in orders:\n"),
      ("repo.py", '''        lines = conn.execute("SELECT id, product_id, qty FROM order_items WHERE order_id = ? ORDER BY id",
                             (order["id"],)).fetchall()''', '        lines = lines_by.get(order["id"], [])'),
      ("repo.py", '''            product = conn.execute("SELECT name, price_cents FROM products WHERE id = ?",
                                   (line["product_id"],)).fetchone()''', '            product = prods[line["product_id"]]')]),
]


def main():
    wanted = {a.zfill(2) for a in sys.argv[1:]}
    bad = 0
    for num, name, base, expect, edits in M:
        if wanted and num not in wanted:
            continue
        lab = [d for d in os.listdir(BROKEN) if d.startswith(num + "-")][0]
        tmp = tempfile.mkdtemp()
        dst = os.path.join(tmp, "code")
        shutil.copytree(os.path.join(BROKEN, lab, base), dst, ignore=shutil.ignore_patterns("__pycache__"))
        try:
            for fname, old, new in edits:
                path = os.path.join(dst, fname)
                text = open(path).read()
                if old not in text:
                    raise SystemExit("mutation %s/%s: pattern not found in %s: %r" % (num, name, fname, old[:60]))
                open(path, "w").write(text.replace(old, new, 1))
            env = dict(os.environ, BROKEN_APP_DIR=dst, PYTHONDONTWRITEBYTECODE="1")
            p = subprocess.run([sys.executable, os.path.join(BROKEN, lab, "verify.py")], cwd=os.path.join(BROKEN, lab),
                               env=env, capture_output=True, text=True, timeout=120)
            verdict = "pass" if p.returncode == 0 else "fail"
            ok = verdict == expect
            bad += not ok
            print("%s  %s  %-62s verify %s (expected %s)" % ("ok " if ok else "BAD", num, name, verdict, expect))
            if not ok:
                print(p.stdout[-600:], p.stderr[-300:])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("\nmutation sanity: %s" % ("all as expected" if not bad else "%d unexpected" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
