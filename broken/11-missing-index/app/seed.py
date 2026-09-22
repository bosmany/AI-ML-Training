"""Deterministic data generator (a stand-in for production: 150k rows, 3000 customers)."""
import random

N_ROWS = 150_000
N_CUSTOMERS = 3_000


def rows():
    rng = random.Random(11)
    for i in range(1, N_ROWS + 1):
        yield (
            i,
            rng.randrange(N_CUSTOMERS),
            rng.choice(("open", "shipped", "shipped", "cancelled")),
            rng.randrange(500, 50_000),
            1_700_000_000 + i * 37,
        )


def load(conn):
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", rows())
    conn.commit()
