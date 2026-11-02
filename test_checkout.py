import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from checkout import make_server

class CheckoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'orders.sqlite')
        self.start()

    def start(self):
        self.server = make_server(self.db, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def tearDown(self):
        self.stop(); self.tmp.cleanup()

    def post(self, key='attempt-0001', payload=None, drop=False):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            headers = {'Content-Type':'application/json', 'Idempotency-Key':key}
            if drop: headers['X-Demo-Drop-Response'] = 'yes'
            c.request('POST', '/orders', json.dumps(payload or {'sku':'field-kit'}), headers)
            r = c.getresponse()
            return r.status, json.loads(r.read())
        finally: c.close()

    def count(self):
        with closing(sqlite3.connect(self.db)) as c:
            return c.execute('SELECT count(*) FROM orders').fetchone()[0]

    def test_retry_reuses_order(self):
        first, again = self.post(), self.post()
        self.assertEqual((first[0], again[0]), (201, 200))
        self.assertEqual(first[1], again[1]); self.assertEqual(self.count(), 1)

    def test_lost_response_after_commit(self):
        with self.assertRaises(http.client.RemoteDisconnected): self.post(drop=True)
        self.assertEqual(self.count(), 1)
        status, result = self.post()
        self.assertEqual(status, 200); self.assertEqual(result['amount'], '100000000')
        self.assertEqual(self.count(), 1)

    def test_same_key_different_purchase_is_conflict(self):
        self.post()
        self.assertEqual(self.post(payload={'sku':'field-notes'})[0], 409)
        self.assertEqual(self.count(), 1)

    def test_twelve_concurrent_calls_create_one_order(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(lambda _:self.post(), range(12)))
        self.assertEqual(sum(code == 201 for code, _ in responses), 1)
        self.assertEqual({code for code, _ in responses}, {200,201})
        self.assertEqual(len({body['id'] for _, body in responses}), 1)
        self.assertEqual(self.count(), 1)

    def test_restart_retains_idempotency(self):
        initial = self.post()[1]
        self.stop(); self.start()
        self.assertEqual(self.post(), (200, initial))

    def test_client_price_rejected(self):
        self.assertEqual(self.post(payload={'sku':'field-kit','amount':'1'})[0], 400)
        self.assertEqual(self.count(), 0)

    def test_missing_key_rejected(self):
        self.assertEqual(self.post(key='')[0], 400)
        self.assertEqual(self.count(), 0)

if __name__ == '__main__': unittest.main()
