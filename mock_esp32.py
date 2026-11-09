"""Configurable ESP32 REST mock, no firmware changes."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


class MockServer(ThreadingHTTPServer):
    def __init__(self, address, temperature=30.5, humidity=70.0, light=180.0):
        super().__init__(address, Handler)
        self.people_count = 0
        self.temperature, self.humidity, self.light = temperature, humidity, light
        self.lock = Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Polling is intentionally silent.

    def send_json(self, body, status=200):
        encoded = json.dumps(body).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path != '/api/occupancy':
            return self.send_json({'error': 'not found'}, 404)
        try:
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 4096:
                raise ValueError('invalid size')
            self.connection.settimeout(2)
            payload = json.loads(self.rfile.read(n))
            count = payload['people_count']
            if type(count) is not int or count < 0:
                raise ValueError('invalid count')
        except (ValueError, KeyError, TypeError, OSError):
            return self.send_json({'error': 'invalid people_count'}, 400)
        with self.server.lock:
            self.server.people_count = count
        self.send_json({'ok': True, 'people_count': count})

    def do_GET(self):
        if self.path != '/api/status':
            return self.send_json({'error': 'not found'}, 404)
        with self.server.lock:
            count = self.server.people_count
        self.send_json(dict(people_count=count, temperature=self.server.temperature,
            humidity=self.server.humidity, light=self.server.light,
            fan=count > 0 and self.server.temperature >= 29,
            light_on=count > 0 and self.server.light < 250, mock=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--temperature', type=float, default=30.5)
    parser.add_argument('--humidity', type=float, default=70)
    parser.add_argument('--light', type=float, default=180)
    args = parser.parse_args()
    server = MockServer((args.host, args.port), args.temperature, args.humidity, args.light)
    print(f'Mock ESP32: http://{args.host}:{server.server_port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
