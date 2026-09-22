# Root cause: missing index on orders.customer_id

**Cause.** Both hot queries filter on `customer_id`, but the only index on `orders` was on `status` (three
distinct values, useless here). SQLite had no choice but `SCAN orders`: it read every row of the table
and, for the list, then sorted the survivors (`USE TEMP B-TREE FOR ORDER BY`).

**Why the symptoms.** Cost per page view is O(table size), independent of how many orders the customer has.
That is why a customer with 25 orders is as slow as one with 25,000, why it degraded silently as the table
grew, and why more traffic just multiplied CPU. Locally 150k rows is small enough to hide it in ~8 ms; the
query plan (about 900k VM instructions vs 600) is the reliable signal.

**Fix.** `CREATE INDEX idx_orders_customer_created ON orders(customer_id, created_at)`. The equality column
comes first, the sort column second, so both queries become `SEARCH ... USING INDEX (customer_id=?)` and
the list needs no sort. Also valid: an index on `(customer_id)` alone.

**Prevention.**
- Review every new query with `EXPLAIN QUERY PLAN`; fail CI on `SCAN` of a large table (this verifier does).
- Test with production-shaped data volumes, and alert on rows-examined / query latency percentiles, not averages.
- Index the columns you filter by (equality first, then range/sort columns); do not index low-cardinality columns alone.
