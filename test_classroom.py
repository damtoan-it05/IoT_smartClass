import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
import requests
from classroom_core import LineCounter, occupancy, atomic_write_json, validate_device
from count_people import make_region, parse_source
from esp32_client import ESP32Client
from mock_esp32 import MockServer


class CountingTests(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(occupancy(3, 2, 1), 4)
        self.assertEqual(occupancy(0, 0, 4), 0)

    def test_cross_and_return(self):
        c = LineCounter(2)
        for t, distance in enumerate([-30, -5, 3, 8, 30, 4, 25, 30, -30]):
            c.update({1: distance}, t * 0.4)
        self.assertEqual((c.entered, c.exited, c.people_count), (1, 1, 2))

    def test_reverse_direction(self):
        c = LineCounter(0, positive_enter=False)
        c.update({1: 40}, 0)
        c.update({1: -40}, 1)
        self.assertEqual(c.entered, 1)

    def test_cooldown(self):
        c = LineCounter()
        c.update({1: -40}, 0)
        c.update({1: 40}, 1)
        c.update({1: -40}, 1.1)
        self.assertEqual((c.entered, c.exited), (1, 0))

    def test_expiry_and_reset(self):
        c = LineCounter()
        c.update({1: -40}, 0)
        c.update({1: 40}, 5)
        self.assertEqual(c.entered, 0)
        c.reset(7)
        self.assertEqual((c.people_count, c.entered, len(c.tracks)), (7, 0, 0))
        with self.assertRaises(ValueError):
            c.reset(-1)

    def test_multiple_tracks(self):
        c = LineCounter()
        c.update({1: -40, 2: -50}, 0)
        c.update({1: 40, 2: 50}, 1)
        self.assertEqual(c.people_count, 2)

    def test_helpers(self):
        self.assertEqual(parse_source('0'), 0)
        self.assertEqual(parse_source('http://camera'), 'http://camera')
        self.assertEqual(make_region(101, 101, 'vertical', 0.3), [(30, 0), (30, 100)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'status.json'
            atomic_write_json(path, {'people_count': 5})
            self.assertEqual(json.loads(path.read_text())['people_count'], 5)

    def test_bad_sensor_data(self):
        for data in [[], {}, {'temperature': float('nan'), 'humidity': 50, 'light': 10, 'fan': True, 'light_on': False}]:
            with self.assertRaises(ValueError):
                validate_device(data)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = MockServer(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_round_trip_and_validation(self):
        self.assertEqual(requests.post(self.url + '/api/occupancy', json={'people_count': 5}, timeout=2).status_code, 200)
        status = requests.get(self.url + '/api/status', timeout=2).json()
        self.assertEqual(validate_device(status)['people_count'], 5)
        self.assertTrue(status['fan'])
        for payload in [{'people_count': -1}, {'people_count': True}, [], {'people_count': 1.5}]:
            self.assertEqual(requests.post(self.url + '/api/occupancy', json=payload, timeout=2).status_code, 400)
        self.assertEqual(requests.get(self.url + '/missing', timeout=2).status_code, 404)

    def test_worker_dedup_disconnect_recovery(self):
        client = ESP32Client(self.url, timeout=0.1, interval=0.05)
        class Session:
            posts = 0
            fail = False
            def post(s, *a, **kw):
                s.posts += 1
                return requests.post(*a, **kw)
            def get(s, *a, **kw):
                if s.fail:
                    raise requests.Timeout('simulated disconnect')
                return requests.get(*a, **kw)
        session = Session()
        client.submit(4)
        client._exchange(session)
        client._exchange(session)
        self.assertEqual(session.posts, 1)
        self.assertTrue(client.snapshot()['esp32_connected'])
        session.fail = True
        client._exchange(session)
        self.assertFalse(client.snapshot()['esp32_connected'])
        self.assertEqual(client.snapshot()['device']['people_count'], 4)
        session.fail = False
        client._exchange(session)
        self.assertTrue(client.snapshot()['esp32_connected'])

    def test_background_latest_value(self):
        client = ESP32Client(self.url, timeout=0.2, interval=0.05).start()
        try:
            start = time.monotonic()
            for n in range(500):
                client.submit(n)
            self.assertLess(time.monotonic() - start, 0.1)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                device = client.snapshot()['device']
                if device and device['people_count'] == 499:
                    break
                time.sleep(0.02)
            self.assertEqual(client.snapshot()['device']['people_count'], 499)
        finally:
            client.close()

    def test_real_connection_failure(self):
        client = ESP32Client('http://127.0.0.1:1', timeout=0.1)
        client.submit(6)
        with requests.Session() as session:
            client._exchange(session)
        self.assertFalse(client.snapshot()['esp32_connected'])
        self.assertEqual(client.desired, 6)


if __name__ == '__main__':
    unittest.main()
