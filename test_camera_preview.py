import time
import unittest
import cv2
import numpy as np
import requests
from camera_preview import CameraPreview
from streamlit.testing.v1 import AppTest


class PreviewTests(unittest.TestCase):
    def test_preview_jpeg_expiry_and_dashboard(self):
        preview = CameraPreview(port=0, stale_after=30).start()
        url = f'http://127.0.0.1:{preview.server.server_port}/frame'
        try:
            self.assertEqual(requests.get(url, timeout=2).status_code, 503)
            frame = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(frame, 'YOLO PREVIEW TEST', (10, 50), 0, 0.5, (0, 255, 0), 1)
            preview.submit(frame)
            response = requests.get(url, timeout=2)
            self.assertEqual(response.status_code, 200)
            decoded = cv2.imdecode(np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(decoded.shape, frame.shape)
            import os
            from unittest.mock import patch
            with patch.dict(os.environ, {'CAMERA_PREVIEW_URL': url}):
                app = AppTest.from_file('dashboard.py').run(timeout=30)
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.get('image')), 1)
            preview.updated = time.monotonic() - 31
            self.assertEqual(requests.get(url, timeout=2).status_code, 503)
        finally:
            preview.close()


if __name__ == '__main__':
    unittest.main()
