# Root cause: N+1 queries (a query per order and per line)

**Cause.** `orders_report()` loads the orders with one query and then, inside a loop, runs one query per order
for its lines and one more per line for the product. A customer with 300 orders and ~900 lines costs about
1,200 statements for a single request; a customer with 3 orders costs about 13.

**Why the symptoms look the way they do.**
* Latency is proportional to the size of the customer's data (statement count x round-trip time), not to server load.
* Every statement is fast (well under a millisecond in the database), so the slow-query log is empty and
  database CPU stays low. The cost is round trips, which is also why a closer database helped a little.
* More application servers do not help: each request is still serial and chatty.
* Local development hides it: with a database on localhost, 1,200 statements finish in milliseconds.

**Fix.** Ask for everything at once and assemble in Python: one `orders LEFT JOIN order_items LEFT JOIN products`
query with an explicit `ORDER BY o.created_at DESC, o.id DESC, l.id`, plus the customer lookup. Two statements
whatever the data size. Pitfalls the verifier checks: an INNER JOIN silently drops orders without lines; losing
the `id` tie-break changes ordering; a per-row cache or an `lru_cache` still issues N queries on a cold cache;
adding `LIMIT`/pagination "fixes" the time by changing the output.

**Prevention.** A test that counts statements and asserts they do not grow with the data
(`tests/test_regression_query_count.py`); in production, emit statements-per-request as a metric and alert on
outliers; use the ORM's eager-loading options (`selectinload`/`joinedload`) and review any query inside a loop.
