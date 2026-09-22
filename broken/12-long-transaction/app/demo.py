"""Reproduce the symptom:  python app/demo.py   (uses a temp dir, takes ~2 s)"""
import os
import sqlite3
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import queue_worker as qw  # noqa: E402

qw.BUSY_TIMEOUT_S = 0.3  # keep the demo short

with tempfile.TemporaryDirectory() as tmp:
    db = os.path.join(tmp, "app.db")
    qw.init_db(db)
    for i in range(3):
        qw.enqueue(db, f"job-{i}")
    slow = lambda payload: (time.sleep(0.4), payload.upper())[1]  # stands in for the partner API
    t = threading.Thread(target=qw.process_pending, args=(db, slow))
    t.start()
    time.sleep(0.2)
    start = time.perf_counter()
    try:
        qw.record_event(db, "GET /")
        print("event recorded")
    except sqlite3.OperationalError as e:
        print(f"record_event failed after {time.perf_counter() - start:.2f}s: {e}")
    t.join()
