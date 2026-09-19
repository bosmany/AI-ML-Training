# Lab: Candidate Scoring API (FastAPI + SQLAlchemy + JWT)

Build the internals of a real, production-shaped REST API: async SQLAlchemy 2 on SQLite,
Pydantic v2 schemas, pagination + filtering + sorting, JWT auth with roles, one consistent
error format, a timing middleware and a background task. A test-suite that drives the real
app through `TestClient` tells you when it is right.

## Why it matters in a real job

"Build a small CRUD API with auth" is the standard backend take-home and the daily work of
most ML-platform teams (feature stores, labelling tools, model-serving control planes). What
separates a junior from a mid-level solution is exactly what this lab grades: correct status
codes, one error shape, no account enumeration, expired/tampered tokens rejected, stable
pagination, and no shared global state between tests.

## Prerequisites (course chapters)

- [FastAPI fundamentals](../../fastapi/ch36-fastapi-fundamentals.html)
- [Dependency injection and error handling](../../fastapi/ch37-dependency-injection-error-handling.html)
- [Databases with SQLAlchemy](../../fastapi/ch38-databases-sqlalchemy.html)
- [Authentication and security](../../fastapi/ch39-authentication-security.html)
- [Testing, middleware, background tasks](../../fastapi/ch40-testing-middleware-background-tasks.html)

## Run it

```bash
cd labs/fastapi-candidate-api
python -m venv .venv && source .venv/bin/activate    # optional but recommended
pip install -r requirements.txt
pytest -q                     # starter: everything fails until you implement it
LAB_TARGET=solution pytest -q # maintainers / CI: the reference solution passes
```

Edit only files under `starter/lab/`. The tests import `from lab import ...` and pick
`starter/` or `solution/` from the `LAB_TARGET` environment variable. Peek at `solution/` only
after you have tried.

To poke at your finished API by hand (needs `uvicorn`, `pip install uvicorn`):

```bash
cd starter && uvicorn --factory lab.app:create_app --reload   # then open http://127.0.0.1:8000/docs
```

## What is provided vs what you write

| File in `starter/lab/` | Status |
| --- | --- |
| `app.py` (app factory), `settings.py`, `models.py`, `db.py`, `events.py` | provided - read them, do not edit |
| `errors.py` | exception classes provided; **you write `register_exception_handlers`** |
| `middleware.py` | **you write `add_timing_middleware`** |
| `schemas.py` | classes provided; **you add the validation constraints** (4 TODOs) |
| `security.py` | **you write** password hashing + JWT create/decode |
| `service.py` | **you write** the database logic (register, authenticate, list/get/create/update/delete) |
| `deps.py` | **you write** `get_current_user` and `require_roles` |
| `routers/*.py` | **you write** the endpoint bodies (decorators and signatures given) |

## The API you are building

| Method + path | Auth | Behaviour |
| --- | --- | --- |
| `GET /health` | none | `{"status": "ok"}` |
| `POST /auth/register` | none | `201` -> `{id, email, role}`; role is always `recruiter`; duplicate email `409`; `role` in the body is `422` |
| `POST /auth/login` | none | `{access_token, token_type: "bearer"}`; bad credentials `401` |
| `GET /candidates` | none | `page`, `page_size` (1-100), `min_score` (0-100, inclusive), `city` (case-insensitive), `sort` = `id`/`score`/`-score`/`name`/`-name` -> `{items, total, page, page_size, pages}` |
| `GET /candidates/{id}` | none | `200` / `404` |
| `POST /candidates` | recruiter or admin | `201`; duplicate email `409`; queues a background `candidate.created` event |
| `PATCH /candidates/{id}` | recruiter or admin | partial update (`exclude_unset`); `404` / `409` / `422` |
| `DELETE /candidates/{id}` | admin | `204`; recruiter gets `403` |

Every error - yours, FastAPI's routing errors, validation errors, crashes - uses one shape:

```json
{"error": {"code": "not_found", "message": "Candidate 7 not found", "details": null}}
```

## Tasks

1. **Error envelope** (`errors.py`): register four handlers (AppError, Starlette `HTTPException`,
   `RequestValidationError`, catch-all `Exception`). Read the docstring in `app.py` first.
2. **Timing middleware** (`middleware.py`): `X-Process-Time-Ms` on every response, including errors.
3. **Schemas** (`schemas.py`): email pattern, name/score constraints, `extra="forbid"` on register,
   the 72-*byte* password limit, and "explicit `null` is not allowed in a PATCH".
4. **Security** (`security.py`): bcrypt hash/verify and JWT create/decode.
5. **Service layer** (`service.py`): users first, then candidates (filters, count, sorting, paging).
6. **Dependencies** (`deps.py`): current user from the bearer token; role checks.
7. **Routers**: wire the endpoints to the service. Run `pytest -q` after each task; failures
   explain what is wrong.

## Hints

<details><summary>Exception handlers: which class catches a 404 for an unknown URL?</summary>

Routing errors are raised as **Starlette's** `HTTPException`, not FastAPI's. Register your handler
for `starlette.exceptions.HTTPException` (FastAPI's subclass is then covered too).
</details>

<details><summary>My 422 handler crashes with "Object of type ValueError is not JSON serializable"</summary>

`RequestValidationError.errors()` can carry the original exception under `ctx`. Build the detail
list yourself from `loc`, `msg`, `type`.
</details>

<details><summary>bcrypt raises "password cannot be longer than 72 bytes"</summary>

bcrypt reads only the first 72 **bytes** (not characters - an emoji is 4 bytes). Version 5 raises,
older versions silently truncate, so two different long passwords could verify as equal. Refuse
long passwords at registration (schema), raise in `hash_password`, and make `verify_password`
return `False` instead of raising so a huge login attempt is a 401, never a 500.
</details>

<details><summary>PyJWT: "Subject must be a string" / an unsigned token is accepted</summary>

Put `str(user.id)` in `sub`. On decode always pass `algorithms=[settings.jwt_algorithm]`; without an
explicit allow-list PyJWT cannot protect you from `alg` confusion. Use
`options={"require": ["exp", "sub"]}` so a token with no expiry is rejected.
</details>

<details><summary>Pagination shows duplicated / missing rows when scores tie</summary>

`ORDER BY score DESC` alone is not deterministic for equal scores. Add the primary key as the last
sort key.
</details>

<details><summary>Sorting by name puts "alice" after "Zed"</summary>

SQLite compares text case-sensitively by default. Sort on `func.lower(Candidate.name)`.
</details>

## Stretch goals

- Add `GET /auth/me` and refresh tokens (short access token + long refresh token).
- Replace offset pagination with keyset ("cursor") pagination and explain when it wins.
- Add a rate limit middleware for `/auth/login` (inject a clock so it stays testable).
- Run against Postgres (`asyncpg`) - which of your tests would need to change, and why not the code?

## How this comes up in interviews

- "Where do you register exception handlers, and why did my handler not fire?" (Starlette freezes
  the middleware stack on the first request - hence the app factory in `app.py`.)
- "401 vs 403?" (unauthenticated vs authenticated-but-not-allowed.)
- "Why do login errors say the same thing for unknown email and wrong password?" (enumeration.)
- "How do you test an endpoint that needs a database?" (dependency override + a fresh in-memory DB
  per test; see `tests/conftest.py`.)
- "What is wrong with `algorithms` being omitted when decoding a JWT?" and "Why not trust the role
  claim in the token?"
