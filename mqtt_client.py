"""MQTT transport with the same submit/snapshot interface as HTTP."""
import json
import threading
import time
from datetime import datetime

from classroom_core import validate_device
from mqtt_config import new_client, validate_prefix


class MQTTESP32Client:
    def __init__(self, host, port, prefix, stale_after=10, client=None):
        self.host, self.port = host, port
        prefix = validate_prefix(prefix)
        self.occupancy_topic, self.status_topic = prefix + '/occupancy', prefix + '/status'
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.broker = threading.Event()
        self.desired = None
        self.last_sent = None
        self.last_publish = 0
        self.last_status = None
        self.stale_after = stale_after
        self.state = dict(esp32_connected=False, esp32_message='MQTT connecting', device=None, device_updated_at=None)
        self.client = client if client is not None else new_client('cv')
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_message = self._on_message
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.client.connect_async(self.host, self.port, keepalive=20)
        self.client.loop_start()
        self.thread.start()
        return self

    def submit(self, count):
        if type(count) is not int or count < 0:
            raise ValueError('people_count must be nonnegative integer')
        with self.lock:
            self.desired = count

    def snapshot(self):
        with self.lock:
            state = dict(self.state)
            fresh = self.last_status is not None and time.monotonic() - self.last_status <= self.stale_after
            state['esp32_connected'] = self.broker.is_set() and fresh
            if self.broker.is_set() and not fresh:
                state['esp32_message'] = 'MQTT broker connected; waiting for fresh ESP32 status'
            return state

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            return self._on_connect_fail(client, userdata)
        rc, _ = client.subscribe(self.status_topic, qos=1)
        if rc != 0:
            return self._on_connect_fail(client, userdata)
        with self.lock:
            self.last_sent = None
            self.last_status = None
            self.state['esp32_message'] = 'MQTT subscribed; waiting for ESP32'
        self.broker.set()

    def _on_connect_fail(self, client, userdata):
        self.broker.clear()
        with self.lock:
            self.state['esp32_message'] = 'MQTT broker unavailable; reconnecting'

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self._on_connect_fail(client, userdata)

    def _on_message(self, client, userdata, message):
        if message.topic != self.status_topic or message.retain or len(message.payload) > 16384:
            return
        try:
            device = validate_device(json.loads(message.payload))
        except (ValueError, TypeError, UnicodeError):
            return
        with self.lock:
            self.last_status = time.monotonic()
            self.state.update(device=device, esp32_message='MQTT ESP32 status received',
                device_updated_at=datetime.now().astimezone().isoformat(timespec='seconds'))

    def _run(self):
        while not self.stop.is_set():
            with self.lock:
                count = self.desired
                send = count is not None and (count != self.last_sent or time.monotonic() - self.last_publish >= 15)
            if self.broker.is_set() and send:
                try:
                    info = self.client.publish(self.occupancy_topic, json.dumps({'people_count': count}), qos=1, retain=False)
                    info.wait_for_publish(timeout=2)
                    if info.rc == 0 and info.is_published():
                        with self.lock:
                            self.last_sent, self.last_publish = count, time.monotonic()
                except (RuntimeError, ValueError):
                    pass  # Retry on next worker cycle, never in the video loop.
            self.stop.wait(0.5)

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(3)
        self.client.disconnect()
        self.client.loop_stop()
        self.broker.clear()
        with self.lock:
            self.state['esp32_message'] = 'MQTT stopped'
