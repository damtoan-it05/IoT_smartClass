"""Continuously drain live sources; retain only the latest decoded frame."""
import os
import threading
import time

import cv2


class VideoSource:
    def __init__(self, source, live=True, timeout=10.0):
        self.live, self.timeout = live, timeout
        if isinstance(source, int) and os.name == 'nt':
            self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        elif isinstance(source, str) and source.lower().startswith(('http://', 'https://', 'rtsp://')):
            self.cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000),
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(timeout * 1000)])
        else:
            self.cap = cv2.VideoCapture(source)
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.frame = None
        self.sequence = self.consumed = 0
        self.failed = False
        self.thread = None
        if live and self.cap.isOpened():
            self.thread = threading.Thread(target=self._capture, daemon=True)
            self.thread.start()

    def isOpened(self):
        return self.cap.isOpened()

    def _capture(self):
        try:
            while not self.stop.is_set():
                ok, frame = self.cap.read()
                with self.condition:
                    if not ok:
                        self.failed = True
                        self.condition.notify_all()
                        return
                    self.frame = frame
                    self.sequence += 1
                    self.condition.notify_all()
        finally:
            self.cap.release()

    def read(self):
        if not self.live:
            return self.cap.read()
        deadline = time.monotonic() + self.timeout
        with self.condition:
            while self.sequence == self.consumed and not self.failed and not self.stop.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None
                self.condition.wait(remaining)
            if self.failed or self.stop.is_set():
                return False, None
            self.consumed = self.sequence
            return True, self.frame

    def release(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread is not None:
            self.thread.join(self.timeout + 1)
        else:
            self.cap.release()
