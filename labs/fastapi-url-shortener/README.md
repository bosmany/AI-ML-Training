# Lab: URL Shortener API (FastAPI + SQLAlchemy + SQLite)

Build the service behind `bit.ly`-style links: `POST /links` creates a short code, `GET /{code}` redirects, and the
service has to survive code collisions, hostile input, expiring links, click counting and paging through thousands of
rows. This is the **guided tier** of the *URL Shortener* project: the models, DB helpers, schemas and error envelope
are provided, you write the interesting logic (codes, URL validation, service layer, routes).

## Why it matters in a real job

A shortener looks trivial and is a classic interview and take-home task because every part hides a real backend
decision: who guarantees uniqueness (the database, not an `if`), what a redirect status code promises to browsers and
caches, why user-supplied URLs are an attack surface (`javascript:`, open redirects, loops), and how to count clicks
without losing any. The same patterns show up in invite links, password-reset links and signed download URLs.

## Prerequisites (course chapters)

- [FastAPI fundamentals](../../fastapi/ch36-fastapi-fundamentals.html)
- [Dependency injection and error handling](../../fastapi/ch37-dependency-injection-error-handling.html)
- [Databases with SQLAlchemy](../../fastapi/ch38-databases-sqlalchemy.html)
- [APIs and HTTP fundamentals](../../systems/sf01-apis-http-fundamentals.html)

## Run it

```bash
cd labs/fastapi-url-shortener
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                        # starter: every test fails until you implement it
LAB_TARGET=solution pytest -q    # maintainers / CI: the reference solution passes
```

Everything is hermetic: each test gets its own SQLite file in `tmp_path`, time comes from a fake clock (no sleeping)
and the code generator is injected, so collisions are forced deterministically. No network is used.

## The API you build

| Method and path | Behaviour |
| --- | --- |
| `POST /links` | body `{url, custom_code?, ttl_seconds?, permanent?}` -> **201** `LinkOut`; 409 duplicate custom code; 422 bad input; 503 no free code after retries |
| `GET /links?limit=&offset=` | `{items, total, limit, offset}`, oldest first, `limit` 1-100 (default 10), `offset` >= 0 |
| `GET /links/{code}` | stats (`clicks`, `expires_at`, `expired`); does not count a click |
| `PUT /links/{code}` | change the target URL (same validation as create) |
| `DELETE /links/{code}` | **204**, then the code is a 404 |
| `GET /{code}` | **302** to the stored URL (**301** if the link was created `permanent`), **404** unknown or deleted, **410** expired |

Every error uses one envelope: `{"error": {"code": "...", "message": "...", "details": null}}`.

## What is provided vs what you write

Provided (read, do not edit): `models.py` (the `Link` table with a **unique index** on `code`), `db.py`, `schemas.py`,
`errors.py` (exceptions + envelope handlers). You write, in `starter/lab/`: `codes.py`, `validation.py`,
`service.py`, `app.py`. Each stub's docstring lists its TODOs.

## Tasks

1. **Codes** (`codes.py`) - `generate_code`: 7 random base62 characters from `secrets`. `validate_custom_code`: 3-32 chars of `[A-Za-z0-9_-]`, and the reserved words `docs`, `redoc`, `openapi.json`, `links` are refused in any letter case.
2. **URL validation** (`validation.py`) - http/https only, at most 2048 characters, no whitespace, a real host, not the service itself (loop), and the URL is returned **exactly** as given (no normalisation).
3. **Create with collision handling** (`service.create_link`) - insert and let the unique index reject duplicates (`IntegrityError` -> rollback). Custom code taken -> `ConflictError`; generated code taken -> call the generator again, up to `max_attempts`, then `CodeGenerationError`.
4. **Expiry and clicks** (`is_expired`, `follow_link`) - `ttl_seconds` sets `expires_at`; the link is dead at the exact instant `now >= expires_at`. An expired link is `GoneError` (410) and does **not** count; a live one increments `clicks` with one atomic `UPDATE`.
5. **CRUD and paging** (`get_link`, `update_link`, `delete_link`, `list_links`) - a deleted code is a 404 forever (not a 410); the list returns a page plus the total.
6. **Routes** (`app.py`) - wire the endpoints in the table above, declaring `GET /{code}` last, and treat the request's own host as "the service" for loop detection.

## Hints

<details><summary>Why not "check, then insert"?</summary>

Two requests can both see "code is free" and both insert; one of them then either fails with a 500 or (with no unique
index) silently creates a duplicate. Insert first, catch `sqlalchemy.exc.IntegrityError`, `rollback()`, and only then
decide what it means (409 for a custom code, retry for a generated one). After a failed flush the session is unusable
until you roll back.
</details>

<details><summary>301 vs 302 (and 307)</summary>

`301` is cached by browsers, often indefinitely: if you later `PUT` a new target or delete the link, returning
visitors still go to the old place and your click counter never sees them. So the default is `302` and `301` is opt-in
(`permanent: true`). `307`/`308` are the same pair but promise the HTTP method is preserved; for a `GET`-only redirect
the difference does not matter.
</details>

<details><summary>Why is the URL not run through pydantic's <code>AnyHttpUrl</code>?</summary>

`AnyHttpUrl("http://example.com")` gives back `http://example.com/`: a "harmless" normalisation that changes what you
redirect to. The tests compare the `Location` header byte for byte with what was submitted. Parse with
`urllib.parse.urlsplit` to *check*, return the original string.
</details>

<details><summary>Atomic click counting</summary>

`link.clicks += 1; commit()` reads, adds in Python and writes back: two simultaneous requests both read 7 and both
write 8. `UPDATE links SET clicks = clicks + 1` is one statement the database executes atomically.
SQLAlchemy: `session.execute(update(Link).where(Link.id == link.id).values(clicks=Link.clicks + 1))`.
</details>

<details><summary>Route order</summary>

`GET /{code}` matches any single path segment, including `links`. FastAPI tries routes in declaration order, so
declare `/links...` first and `/{code}` last. `/docs` and `/openapi.json` are registered by FastAPI itself before
yours, which is also why they can never be short codes.
</details>

## Stretch goals (not tested)

- Per-link analytics: clicks by day and by `Referer`, stored in a second table.
- Rate-limit `POST /links` per client IP (token bucket with an injected clock).
- A background job that deletes links expired for more than 30 days.
- Run it for real: `uvicorn` with a small factory module, then `curl -i localhost:8000/<code>` and watch the `Location` header and status line.
- Swap SQLite for Postgres and prove the unique index still protects you with two threads inserting the same code.

## How this comes up in interviews

"Design a URL shortener" (base62 vs hashing, collision strategy, read-heavy caching), "how do you guarantee uniqueness
under concurrency?" (unique constraint + retry, not a pre-check), "301 or 302, and what does that do to analytics?",
"what could go wrong if users can submit any URL?" (`javascript:` XSS, open redirects, SSRF-style internal URLs,
redirect loops to yourself), and "how would you count clicks accurately at scale?" (atomic increments, then batching or
an event stream).

## What this lab does not cover

- Real concurrency: SQLite and `TestClient` are sequential enough that races are argued for, not reproduced.
- Private/internal address blocking (SSRF), redirect-chain following, malware/phishing URL reputation.
- Authentication and per-user ownership of links; rate limiting; caching in front of the redirect.
- Deployment: the catalog project also asks for a deployed URL; that part is not graded by these tests.
- Timezone handling is simplified: times are stored as naive UTC.
