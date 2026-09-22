# Root cause: unbounded cache keyed by user-controlled input

**Cause.** `get_report()` stores every rendered report in a module-level dict keyed by the normalised
query string. Users type arbitrary searches, so the key space is effectively infinite, and nothing ever
evicts an entry. Each entry is about 1.3 KB, so at ~20 one-off searches per second the worker gains
tens of MB per hour until the container limit kills it.

**Why the symptoms look the way they do.**
* Memory grows with *distinct* queries, not with request volume: repeat traffic does not add entries.
* Latency and CPU stay healthy (a bigger dict is still O(1)), so nothing alerts until the OOM kill.
* A restart empties the dict, which is why the cycle repeats.
* Half the traffic is one-off searches that will never hit the cache again, so they are pure retained garbage.

**Fix.** Bound the cache (LRU, `MAX_ENTRIES = 1000`, well above the ~200 popular queries) so the hot set stays
resident and the cold tail is evicted. Removing the cache would also stop the leak but re-creates the
expensive render on every request (the verifier checks for that band-aid). Raising the container limit or
restarting on a schedule only hides it. `gc.collect()` does nothing because the objects are still reachable.

**Prevention.** A regression test that pushes more distinct keys than the cap and asserts the size
(see `tests/test_regression_bounded_cache.py`); a memory-growth alert on the worker (RSS slope over
6 hours); a code-review checklist item: every module-level cache needs a size or lifetime bound.
