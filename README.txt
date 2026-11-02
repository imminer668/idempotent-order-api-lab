Idempotent order API lab

Files
checkout.py             localhost API and persistent SQLite order storage
test_checkout.py        seven tests including HTTP retries and concurrent calls

Run
python3 -B -m unittest -v
python3 checkout.py --db checkout-demo.sqlite --port 8765

In a second terminal (macOS/Linux or Windows WSL)
curl -i http://127.0.0.1:8765/orders -H 'Content-Type: application/json' -H 'Idempotency-Key: reader-attempt-0001' -d '{"sku":"field-kit"}'
Repeat that exact command. First response 201, next response 200 with the same id.

To inject a disconnect after commit, use a fresh key and add this header
-H 'X-Demo-Drop-Response: yes'
Expected curl empty response, usually exit 52. Retry the same key without that
header. Expect 200 with the saved order. This deliberately injected failure is
part of the teaching API, not a network-availability benchmark.

Change the SKU to field-notes under the same key. Expect 409 conflict.
Adding an amount field is rejected with 400. Prices belong to the local catalog.
Stop with Ctrl+C. Restart with the SAME database path to retain the saved keys.
Use a new filename for a clean manual run. Tests use temporary databases and ports.

The server binds to 127.0.0.1 only. It has no authentication, tenant boundaries,
TLS, key expiration or upstream payment call. Remove the disconnect hook before
adapting the logic. SQLite writes are serialized, not a high-throughput benchmark.

Python 3.10+ with sqlite3. No pip dependencies, credentials, wallet or real assets.
Tested on Python 3.13.3, macOS. Other operating systems were not executed here.
Run commands inside the extracted directory. Do not expose the HTTP lab publicly.

Original Fone educational companion. You may copy and adapt this material with
attribution and its scope notice retained. This is not a production payment system
or a security assessment. Product source files are not bundled in this download.
