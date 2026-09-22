# POST /charges

Request body: `customer_id`, `order_id`, `currency` (USD, EUR, GBP), `amount_cents` (positive integer).
Responses: `201` charge created, `400` validation error, `502` processor unavailable.

## Idempotency

Clients may send an `Idempotency-Key` header (any string up to 255 chars). A key identifies ONE logical
charge; it is scoped to the `customer_id` in the body.

* Same key and same body as an earlier request: no new charge; the ORIGINAL response (status and body) is returned.
* Same key and a different body: `409`, no charge.
* A duplicate that arrives while the first request is still being processed: either wait and return the original
  response, or `409` ("in progress"). Never a second charge.
* Different keys are different charges, even for the same customer and amount (people do buy twice).
* No key: no de-duplication (legacy clients).
* If the processor fails (`502`), nothing is recorded and the key stays usable, so the client can retry.
* Keys are remembered durably (they survive a service restart).
