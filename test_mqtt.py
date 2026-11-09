import json
import time
import unittest
import threading
from types import SimpleNamespace
from mqtt_client import MQTTESP32Client
from mqtt_config import validate_prefix


class FakeClient:
    def subscribe(self, topic, qos):
        self.subscription = (topic, qos)
        return 0, 1


class MQTTTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeClient()
        self.client = MQTTESP32Client('broker.hivemq.com', 1883, 'unique/test', client=self.fake)
        self.client._on_connect(self.fake, None, None, 0, None)

    def deliver(self, payload, retain=False, topic='unique/test/status'):
        self.client._on_message(self.fake, None, SimpleNamespace(topic=topic, payload=payload, retain=retain))

    def test_topics_and_wait_for_device(self):
        self.assertEqual(self.fake.subscription, ('unique/test/status', 1))
        self.assertEqual(self.client.occupancy_topic, 'unique/test/occupancy')
        self.assertFalse(self.client.snapshot()['esp32_connected'])

    def test_status_stale_disconnect_keeps_data(self):
        device = dict(people_count=5, temperature=30.5, humidity=70, light=180, fan=True, light_on=True)
        self.deliver(json.dumps(device).encode())
        self.assertTrue(self.client.snapshot()['esp32_connected'])
        self.client.last_status = time.monotonic() - 11
        self.assertFalse(self.client.snapshot()['esp32_connected'])
        self.assertEqual(self.client.snapshot()['device']['people_count'], 5)
        self.client._on_disconnect(self.fake, None, None, 1, None)
        self.assertFalse(self.client.broker.is_set())

    def test_bad_retained_and_unrelated_status_ignored(self):
        for payload in (b'not json', b'[]', b'{}', b'\xff'):
            self.deliver(payload)
        good = json.dumps(dict(temperature=30, humidity=70, light=180, fan=True, light_on=True)).encode()
        self.deliver(good, retain=True)
        self.deliver(good, topic='other/status')
        self.assertIsNone(self.client.snapshot()['device'])

    def test_latest_submission_and_validation(self):
        for n in range(100):
            self.client.submit(n)
        self.assertEqual(self.client.desired, 99)
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                self.client.submit(value)

    def test_reconnect_resets_publish_and_freshness(self):
        self.client.last_sent = 5
        self.client.last_status = time.monotonic()
        self.client._on_connect(self.fake, None, None, 0, None)
        self.assertIsNone(self.client.last_sent)
        self.assertIsNone(self.client.last_status)

    def test_prefix_rejects_wildcards(self):
        for prefix in ('', '/', 'a/#', 'a/+', 'a\x00b'):
            with self.assertRaises(ValueError):
                validate_prefix(prefix)

    def test_worker_publishes_qos1_without_retain_and_deduplicates(self):
        calls = []
        delivered = threading.Event()
        class Published:
            rc = 0
            def wait_for_publish(self, timeout):
                delivered.set()
            def is_published(self):
                return True
        def publish(topic, payload, qos, retain):
            calls.append((topic, json.loads(payload), qos, retain))
            return Published()
        self.fake.publish = publish
        self.client.submit(5)
        self.client.thread.start()
        try:
            self.assertTrue(delivered.wait(2))
            time.sleep(0.6)
            self.assertEqual(calls, [('unique/test/occupancy', {'people_count': 5}, 1, False)])
        finally:
            self.client.stop.set()
            self.client.thread.join(2)


if __name__ == '__main__':
    unittest.main()
