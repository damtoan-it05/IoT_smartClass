"""Counting and status helpers, independent of camera/YOLO."""
import json
import math
import os
from pathlib import Path


def occupancy(initial, entered, exited):
    return max(0, initial + entered - exited)


class LineCounter:
    def __init__(self, initial=0, positive_enter=True, margin=15, cooldown=0.8, ttl=2.0):
        self.positive_enter = positive_enter
        self.margin, self.cooldown, self.ttl = margin, cooldown, ttl
        self.reset(initial)

    def reset(self, initial=0):
        if isinstance(initial, bool) or not isinstance(initial, int) or initial < 0:
            raise ValueError('initial must be a nonnegative integer')
        self.initial, self.entered, self.exited = initial, 0, 0
        self.tracks = {}

    @property
    def people_count(self):
        return occupancy(self.initial, self.entered, self.exited)

    def update(self, positions, now):
        # positions: {track_id: signed distance from line in pixels}.
        self.tracks = {k: v for k, v in self.tracks.items() if now - v[1] <= self.ttl}
        for track_id, distance in positions.items():
            side = 1 if distance > self.margin else -1 if distance < -self.margin else 0
            old_side, _, last_cross = self.tracks.get(track_id, (0, now, -math.inf))
            if side and old_side and side != old_side and now - last_cross >= self.cooldown:
                if (side > 0) == self.positive_enter:
                    self.entered += 1
                else:
                    self.exited += 1
                last_cross = now
            self.tracks[track_id] = (side or old_side, now, last_cross)


def atomic_write_json(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def validate_device(data):
    if not isinstance(data, dict):
        raise ValueError('status must be an object')
    for key in ('temperature', 'humidity', 'light'):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'invalid {key}')
    if not 0 <= data['humidity'] <= 100 or data['light'] < 0:
        raise ValueError('invalid humidity/light range')
    for key in ('fan', 'light_on'):
        if not isinstance(data.get(key), bool):
            raise ValueError(f'invalid {key}')
    return data
