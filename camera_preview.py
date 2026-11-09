"""Latest annotated JPEG in memory, served only on loopback."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cv2


class CameraPreview:
    def __init__(self, port=8765, fps=5, stale_after=3):
        self.lock = threading.Lock()
        self.jpeg = None
        self.updated = 0
        self.interval = 1 / fps
        self.stale_after = stale_after
        preview = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path != '/frame':
                    self.send_error(404)
                    return
                with preview.lock:
                    jpeg, updated = preview.jpeg, preview.updated
                if jpeg is None or time.monotonic() - updated > preview.stale_after:
                    self.send_error(503, 'No fresh camera frame')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(jpeg)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(jpeg)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def submit(self, frame):
        now = time.monotonic()
        if now - self.updated < self.interval:
            return
        height, width = frame.shape[:2]
        if width > 960:
            frame = cv2.resize(frame, (960, round(height * 960 / width)))
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if ok:
            with self.lock:
                self.jpeg, self.updated = encoded.tobytes(), now

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
