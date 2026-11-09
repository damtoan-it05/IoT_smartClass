"""Latest-value HTTP worker: network never blocks the video loop."""
import logging
import threading
import time
from datetime import datetime

import requests
from classroom_core import validate_device


class ESP32Client:
    def __init__(self, base_url='', timeout=1.5, interval=2.0):
        self.url = base_url.rstrip('/')
        self.timeout, self.interval = timeout, interval
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.desired = None
        self.last_sent = None
        self.state = dict(esp32_connected=False, esp32_message='offline', device=None,
                          device_updated_at=None)
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def submit(self, count):
        with self.lock:
            self.desired = count

    def snapshot(self):
        with self.lock:
            return dict(self.state)

    def close(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(self.timeout * 4 + 1)

    def _run(self):
        with requests.Session() as session:
            while not self.stop_event.is_set():
                if self.url:
                    self._exchange(session)
                self.stop_event.wait(self.interval)

    def _exchange(self, session):
        try:
            with self.lock:
                count = self.desired
            if count is not None and count != self.last_sent:
                response = session.post(self.url + '/api/occupancy', json={'people_count': count}, timeout=self.timeout)
                response.raise_for_status()
                self.last_sent = count
            response = session.get(self.url + '/api/status', timeout=self.timeout)
            response.raise_for_status()
            device = validate_device(response.json())
            # If a device restarted and reports its count, synchronize again.
            if 'people_count' in device and device['people_count'] != self.last_sent:
                self.last_sent = None
            with self.lock:
                self.state.update(esp32_connected=True, esp32_message='connected', device=device,
                                  device_updated_at=datetime.now().astimezone().isoformat(timespec='seconds'))
        except (requests.RequestException, ValueError) as exc:
            with self.lock:
                was_connected = self.state['esp32_connected']
                self.state.update(esp32_connected=False, esp32_message=str(exc))
            if was_connected:
                logging.warning('ESP32 disconnected: %s', exc)
