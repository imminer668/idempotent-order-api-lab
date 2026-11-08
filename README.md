# Idempotent Order API Lab

What happens when an order is committed, but the client never receives the response?

Run a small Python and SQLite API, drop a response after commit, then retry the request. The saved order is returned with the same ID. Seven tests also cover concurrent calls, conflicting purchases and a server restart.

Follow the [step-by-step walkthrough on Fone](https://fone.cc/insights/python-sqlite-idempotent-order-api/?utm_source=github&utm_medium=referral&utm_campaign=gh_order_api_20261102) alongside the code. It shows the HTTP requests and the saved order after each retry.

## Run the tests

Use Python 3.10+ with SQLite support. There are no pip dependencies. Download this repository and run these commands inside its directory.

```sh
python3 -B -m unittest -v
python3 checkout.py --db checkout-demo.sqlite --port 8765
```

Keep the server running. Open a second terminal for the requests below. The curl examples use macOS/Linux or Windows WSL shell syntax.

## Create an order, then retry

```sh
curl -i http://127.0.0.1:8765/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: reader-attempt-0001' \
  -d '{"sku":"field-kit"}'
```

The first request returns `201`. Run the same command again. It returns `200` with the same order ID, SKU and amount.

## Lose the response after commit

Use a fresh key for this experiment.

```sh
curl -i http://127.0.0.1:8765/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: lost-response-0001' \
  -H 'X-Demo-Drop-Response: yes' \
  -d '{"sku":"field-kit"}'
```

curl reports an empty response, usually exit code `52`. The server has already saved the order. Retry with the same key and omit the fault header.

```sh
curl -i http://127.0.0.1:8765/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: lost-response-0001' \
  -d '{"sku":"field-kit"}'
```

Expect `200` and the saved order. The test suite checks that the database contains one order for this experiment.

## Reuse the key for a different purchase

```sh
curl -i http://127.0.0.1:8765/orders \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: lost-response-0001' \
  -d '{"sku":"field-notes"}'
```

Expect `409` with `idempotency_conflict`. A client-supplied `amount` is rejected with `400`; prices come from the local catalog. Amount strings are illustrative integer values with no real currency or token attached.

## How it works

`BEGIN IMMEDIATE` serializes SQLite writers. Within that transaction, the handler looks up the key and either returns the stored order, rejects a different SKU, or inserts a new order. A unique constraint also protects the stored request key.

A key represents one purchase attempt. Using a new key creates another order. Keep the same database path across restarts to retain saved keys. Use a fresh database filename to repeat the manual experiments from scratch.

| Test | What it checks |
| --- | --- |
| Retry | Same key and SKU return the saved order |
| Lost response | Retry finds the order after an injected disconnect |
| Conflicting purchase | Same key with another SKU returns 409 |
| Concurrency | Twelve requests create one order, with one 201 response |
| Restart | Saved keys survive a server restart |
| Client price | An extra amount field is rejected |
| Missing key | A request without a key is rejected |

## Where this example fits

This localhost lab isolates order creation. Payment verification and delivery are separate steps in a checkout workflow. It contains no wallet integration or upstream payment call.

The server binds to `127.0.0.1`. Keep it local. It has no authentication, tenant isolation, TLS or key expiration. The deliberate disconnect hook is for the experiment. SQLite serializes writes; the concurrency test does not measure production throughput.

Read the [full walkthrough on Fone](https://fone.cc/insights/python-sqlite-idempotent-order-api/?utm_source=github&utm_medium=referral&utm_campaign=gh_order_api_20261102) for the order-state discussion. For the related merchant checkout and delivery product, see [StableIn Payments](https://fone.cc/products/stablein-payments/?utm_source=github&utm_medium=referral&utm_campaign=gh_order_api_20261102). This standalone example uses Python and SQLite; StableIn has a separate implementation.

The tutorial is also available on [DEV](https://dev.to/imminer668/your-order-api-needs-more-than-an-idempotency-key-46j0) and [Hashnode](https://0xfone.hashnode.dev/your-order-api-needs-more-than-an-idempotency-key).

## Reuse

The original companion notice is retained in [README.txt](README.txt). You may copy and adapt the lab with attribution and its scope notice retained.
