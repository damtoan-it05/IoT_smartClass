"""MQTT Mock ESP32: consumes occupancy and publishes simulated sensors."""
import argparse
import json
import threading

from mqtt_config import add_mqtt_args, resolve_prefix, new_client


class MQTTMockESP32:
    def __init__(self, host, port, prefix, temperature=30.5, humidity=70, light=180):
        self.host, self.port = host, port
        self.occupancy_topic, self.status_topic = prefix + '/occupancy', prefix + '/status'
        self.temperature, self.humidity, self.light = temperature, humidity, light
        self.people_count = None
        self.lock = threading.Lock()
        self.connected = threading.Event()
        self.changed = threading.Event()
        self.stop = threading.Event()
        self.client = new_client('mock')
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            rc, _ = client.subscribe(self.occupancy_topic, qos=1)
            if rc == 0:
                self.connected.set()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected.clear()

    def _on_message(self, client, userdata, message):
        if message.topic != self.occupancy_topic or message.retain or len(message.payload) > 4096:
            return
        try:
            count = json.loads(message.payload)['people_count']
            if type(count) is not int or count < 0:
                return
        except (ValueError, KeyError, TypeError, UnicodeError):
            return
        with self.lock:
            self.people_count = count
        self.changed.set()

    def start(self):
        self.client.connect_async(self.host, self.port, keepalive=20)
        self.client.loop_start()
        self.thread.start()
        return self

    def _run(self):
        while not self.stop.is_set():
            self.changed.wait(2)
            self.changed.clear()
            with self.lock:
                count = self.people_count
            if self.connected.is_set() and count is not None:
                status = dict(people_count=count, temperature=self.temperature, humidity=self.humidity,
                    light=self.light, fan=count > 0 and self.temperature >= 29,
                    light_on=count > 0 and self.light < 250, mock=True)
                self.client.publish(self.status_topic, json.dumps(status), qos=1, retain=False)

    def close(self):
        self.stop.set()
        self.changed.set()
        self.thread.join(3)
        self.client.disconnect()
        self.client.loop_stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    add_mqtt_args(parser)
    parser.add_argument('--temperature', type=float, default=30.5)
    parser.add_argument('--humidity', type=float, default=70)
    parser.add_argument('--light', type=float, default=180)
    args = parser.parse_args()
    prefix = resolve_prefix(args)
    print(f'MQTT mock {args.mqtt_host}:{args.mqtt_port}; prefix={prefix}', flush=True)
    mock = MQTTMockESP32(args.mqtt_host, args.mqtt_port, prefix, args.temperature, args.humidity, args.light).start()
    try:
        while True:
            mock.stop.wait(1)
    except KeyboardInterrupt:
        pass
    finally:
        mock.close()
