"""Explicit live broker smoke test, fake occupancy only; also updates Dashboard."""
import argparse
import time
import uuid
from datetime import datetime
from pathlib import Path
from classroom_core import atomic_write_json
from mqtt_config import add_mqtt_args, resolve_prefix
from mqtt_client import MQTTESP32Client
from mqtt_mock_esp32 import MQTTMockESP32


def wait_for(predicate, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError('MQTT round-trip/status timeout; check Internet and outbound TCP 1883')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_mqtt_args(parser)
    parser.add_argument('--timeout', type=float, default=30)
    args = parser.parse_args()
    # Isolate every test, including from a running classroom mock.
    prefix = resolve_prefix(args) + '/test/' + uuid.uuid4().hex
    print(f'Broker={args.mqtt_host}:{args.mqtt_port}; test prefix={prefix}', flush=True)
    mock = MQTTMockESP32(args.mqtt_host, args.mqtt_port, prefix).start()
    client = MQTTESP32Client(args.mqtt_host, args.mqtt_port, prefix).start()
    try:
        wait_for(lambda: mock.connected.is_set() and client.broker.is_set(), args.timeout)
        # on_connect precedes SUBACK; periodic occupancy refresh handles this race.
        for count in (0, 5, 2):
            client.submit(count)
            wait_for(lambda: client.snapshot()['device'] is not None and
                     client.snapshot()['device']['people_count'] == count, args.timeout)
            state = client.snapshot()
            assert state['esp32_connected']
            assert state['device']['fan'] == (count > 0)
            assert state['device']['light_on'] == (count > 0)
            atomic_write_json(Path(__file__).resolve().parent / 'status.json', dict(
                people_count=count, initial=count, entered=0, exited=0,
                camera_state='simulation', camera_message='MQTT smoke test; no camera used',
                updated_at=datetime.now().astimezone().isoformat(timespec='seconds'), **state))
            print(f'PASS occupancy={count} -> mock -> status, fan={state["device"]["fan"]}', flush=True)
        mock.close()
        wait_for(lambda: not client.snapshot()['esp32_connected'], 15)
        assert client.snapshot()['device']['people_count'] == 2
        print('PASS mock offline -> stale status detected; last count retained', flush=True)
    finally:
        client.close()
        if not mock.stop.is_set():
            mock.close()


if __name__ == '__main__':
    main()
