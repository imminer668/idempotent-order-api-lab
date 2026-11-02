"""Single-merchant localhost teaching API. No payments, auth or production server."""
import argparse
import json
import re
import socket
import sqlite3
import uuid
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CATALOG = {'field-kit':'100000000', 'field-notes':'25000000'}


def create_order(db_path, key, body):
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', key or ''):
        return 400, {'error':'invalid_idempotency_key'}
    if not isinstance(body, dict) or set(body) != {'sku'} or body['sku'] not in CATALOG:
        return 400, {'error':'send_only_a_known_sku'}
    with closing(sqlite3.connect(db_path, timeout=10, isolation_level=None)) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            row = db.execute('SELECT id, sku, amount FROM orders WHERE request_key=?', (key,)).fetchone()
            if row:
                db.commit()
                if row[1] != body['sku']: return 409, {'error':'idempotency_conflict'}
                return 200, {'id':row[0], 'sku':row[1], 'amount':row[2], 'status':'open'}
            order_id, amount = str(uuid.uuid4()), CATALOG[body['sku']]
            db.execute('INSERT INTO orders VALUES (?,?,?,?)', (order_id,key,body['sku'],amount))
            db.commit()
            return 201, {'id':order_id, 'sku':body['sku'], 'amount':amount, 'status':'open'}
        except BaseException:
            db.rollback(); raise


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/orders': self.respond(404, {'error':'not_found'}); return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096: raise ValueError('body size')
            body = json.loads(self.rfile.read(size))
            status, data = create_order(self.server.db_path, self.headers.get('Idempotency-Key'), body)
        except (ValueError, TypeError, UnicodeError):
            self.respond(400, {'error':'invalid_request'}); return
        except sqlite3.OperationalError:
            self.respond(503, {'error':'database_busy_retry_same_key'}); return
        # Explicit teaching fault, after commit and before any response bytes.
        if status in (200,201) and self.headers.get('X-Demo-Drop-Response') == 'yes':
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)
            return
        self.respond(status, data)

    def respond(self, status, data):
        raw = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        try: self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError): pass

    def log_message(self, *args): pass


def make_server(db_path, port):
    with closing(sqlite3.connect(db_path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE, sku TEXT NOT NULL, amount TEXT NOT NULL)')
        db.commit()
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.db_path = db_path
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='checkout-demo.sqlite')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with make_server(args.db, args.port) as server:
        print('Local teaching API http://127.0.0.1:%s/orders' % server.server_port, flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
