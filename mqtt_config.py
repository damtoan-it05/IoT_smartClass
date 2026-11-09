"""Shared MQTT CLI and per-project topic namespace."""
import argparse
import json
import uuid
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / 'mqtt_config.json'


def validate_prefix(prefix):
    if not isinstance(prefix, str) or not prefix.strip('/') or any(c in prefix for c in '+#\x00'):
        raise ValueError('Topic prefix must be nonempty and contain no +, # or NUL')
    return prefix.strip('/')


def default_prefix():
    if CONFIG.exists():
        return validate_prefix(json.loads(CONFIG.read_text(encoding='utf-8'))['topic_prefix'])
    prefix = 'smartclassroom/group2/' + uuid.uuid4().hex
    try:
        with CONFIG.open('x', encoding='utf-8') as stream:
            json.dump({'topic_prefix': prefix}, stream, indent=2)
    except FileExistsError:
        return default_prefix()
    return prefix


def add_mqtt_args(parser):
    parser.add_argument('--mqtt-host', default='broker.hivemq.com')
    parser.add_argument('--mqtt-port', type=int, default=1883)
    parser.add_argument('--topic-prefix', help='Shared unique prefix; default saved in mqtt_config.json')


def resolve_prefix(args):
    if not 1 <= args.mqtt_port <= 65535:
        raise ValueError('MQTT port must be 1..65535')
    return validate_prefix(args.topic_prefix) if args.topic_prefix is not None else default_prefix()


def new_client(role):
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise RuntimeError('MQTT requires paho-mqtt>=2.1,<3 in .venv; see README') from exc
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f'sccv-{role}-{uuid.uuid4().hex[:16]}',
                         protocol=mqtt.MQTTv311)
    client.reconnect_delay_set(min_delay=1, max_delay=15)
    client.max_queued_messages_set(4)
    client.connect_timeout = 5
    return client
