# Lab: Async Link Checker (semaphores, timeouts, retries, cancellation)

Build a concurrency-limited link checker on `asyncio` and `httpx`: it crawls same-host pages, checks every link with
`HEAD` (falling back to `GET`), classifies the outcome, retries transient failures with backoff and stops cleanly
when cancelled. This is the **guided** tier of the project *Async Link Checker*: you complete a scaffold that uses
`asyncio.gather` plus a semaphore for a known list of URLs and a level-by-level crawl on top of it.

## Why it matters in a real job

Checking docs sites, sitemaps and service health endpoints is bread-and-butter DevOps automation, and it is the
canonical place where async mistakes hurt: unbounded concurrency that DoS-es your own server, a request that hangs
forever, a retry storm, tasks left running after Ctrl-C. Here every one of those is proven by a test that talks
to a **local fixture server** and reads its counters.

## Prerequisites (course chapters)

- [Professional Python](../../python/ch06-professional-python.html)
- [Python for DevOps and APIs](../../python/ch07-python-devops-apis.html)
- [APIs and HTTP fundamentals](../../systems/sf01-apis-http-fundamentals.html)
- [Networking and microservices communication](../../systems/sf02-networking-microservices.html)

## Run it

```bash
cd labs/python-async-link-checker
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

**Hermetic by design.** `tests/fixture_server.py` starts a real HTTP server on `127.0.0.1` (random port) inside the test
process. It has routes with configurable status, latency, hanging, fail-the-first-N-requests, a different answer to
`HEAD`, and counters (requests per method/path, maximum simultaneous requests). An autouse fixture makes any
connection to a non-loopback address, or any lookup of a non-local host name, fail the test. Backoff sleeps are injected, so nothing waits for a
retry delay. Tests are ordinary sync functions using `asyncio.run`, so no pytest plugin is needed.

## What is provided vs what you write

Provided: `models.py` (`Status`, `CheckConfig`, `LinkResult`, `Report` fields), the constants in `checker.py`, `build_parser()`
in `cli.py`, `python -m lab`. You write:

1. `parsing.py`: `normalize_url`, `is_same_host`, `extract_links`.
2. `classify.py`: `classify_status`, `classify_exception`, `backoff_delay`.
3. `models.py`: `CheckConfig.validate`, `Report.broken`, `Report.to_json_dict`.
4. `checker.py`: `make_timeout`, `make_client`, `check_url` (HEAD/GET fallback, redirects, timeout, retries),
   `check_urls` (dedupe + semaphore + gather + no leftover tasks), `crawl` (breadth-first, depth, cancellation).
5. `cli.py`: `main` with exit codes and the partial report on Ctrl-C.

## Behaviour to implement

- Statuses: `ok`, `redirect` (followed, final answer 2xx, `final_url` set), `client_error`, `server_error`, `timeout`,
  `dns_error`, `connection_error`, `too_many_redirects`. Only `ok` and `redirect` are healthy.
- At most `--concurrency N` requests are in flight - the fixture server measures it. Each URL is checked at most once.
- The whole attempt (including redirect hops) is bounded by `--timeout`; a hung server never blocks the run longer than that.
- HEAD first; only `405`/`501` trigger a GET fallback. Redirects are followed by your code, capped at `max_redirects`.
- Transient failures (timeout, connection/DNS error, 5xx) are retried `--retries` times with `min(30, base * 2**n)` delays; 4xx never.
- `crawl` fetches pages closer than `--depth` with GET and parses only same-host HTML; other links only get a HEAD.
- Exit code: `0` all healthy, `1` something broken, `2` usage error, `130` interrupted (partial report printed and written).
- `--report FILE` writes JSON with `source`, `url`, `status`, `http_status`, `final_url`, `latency_ms` per link.

## Hints

<details><summary>Semaphore and gather</summary>

Create the `asyncio.Semaphore(n)` once per `check_urls` call and wrap the *whole* per-URL work in `async with sem:`.
Then `await asyncio.gather(*tasks)`. Do not size httpx's connection pool to `n` instead - the test wants the semaphore.
</details>

<details><summary>Timeouts</summary>

`async with asyncio.timeout(seconds):` raises `TimeoutError` when the block runs too long (Python 3.11+). It bounds
the *total* time of the redirect chain, which httpx's per-phase timeouts do not. Keep the connect timeout in the
client's `httpx.Timeout` too.
</details>

<details><summary>Classifying exceptions</summary>

`httpx.ConnectTimeout` is both a timeout and a transport error - test for timeouts first. A DNS failure is an
`httpx.ConnectError` whose `__cause__` chain contains a `socket.gaierror`; walk the chain.
</details>

<details><summary>Do not leave tasks behind</summary>

If one task raises, `gather` propagates but the others keep running. Cancel the tasks you created and `await
asyncio.gather(*tasks, return_exceptions=True)` before re-raising. `async with client:` closes the client even when cancelled.
</details>

<details><summary>Retries and the fake sleep</summary>

Take `sleep` as a parameter (default `asyncio.sleep`) and call `await sleep(backoff_delay(n, base))`, where `n` counts retries from 0.
The tests pass a recorder, so they can assert the exact delays without waiting.
</details>

## Stretch goals

- Replace `gather` with an `asyncio.Queue` and N worker tasks so discovery and checking overlap (the *spec* tier).
- Jittered backoff (`random.uniform(0, delay)`) with an injectable RNG; honour `Retry-After` on 429/503.
- Per-host concurrency limits and a `--baseline` file that only fails on *new* broken links.
- Stream GET responses and stop reading after the first 1 MB; ignore `rel="nofollow"` and `robots.txt`.
- Strip default ports in `normalize_url` (`:80` / `:443`) and canonicalise trailing slashes.

## How this comes up in interviews

"Fetch 10,000 URLs without overloading anything" tests whether you know a semaphore or worker pool, timeouts on every
network call, cancellation and cleanup (`try/finally`, `async with`), and how to test concurrency deterministically
(server-side counters, injected clocks/sleeps) instead of `sleep()`. Follow-ups: backoff with jitter, idempotency of
retries, HEAD vs GET, and why `asyncio.gather` alone does not bound the number of tasks.

## What this lab does not cover

- Real internet behaviour: TLS certificate errors, HTTP/2, proxies, rate limiting by real sites, robots.txt.
- Real DNS failures (they are unit-tested by classifying a constructed exception, because a lookup would leave the machine); the connect timeout is verified as configuration, not by a black-holed host.
- Ctrl-C delivered by the OS: cancellation is tested by cancelling the task, and the CLI's `KeyboardInterrupt` path with an injected crawler.
- Worker-queue crawling, per-host limits and baseline files (stretch goals), packaging and the container image deliverable.
