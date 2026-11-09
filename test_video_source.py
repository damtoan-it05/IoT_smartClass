import threading
import time
import unittest
from unittest.mock import patch
from video_source import VideoSource


class FakeCapture:
    def __init__(self, *args):
        self.n = 0
        self.released = False
    def isOpened(self):
        return True
    def read(self):
        time.sleep(0.005)
        self.n += 1
        return True, self.n
    def release(self):
        self.released = True


class VideoTests(unittest.TestCase):
    @patch('video_source.cv2.VideoCapture', FakeCapture)
    def test_slow_consumer_gets_latest_and_cleanup(self):
        source = VideoSource(0)
        try:
            ok, first = source.read()
            self.assertTrue(ok)
            time.sleep(0.1)
            ok, latest = source.read()
            self.assertTrue(ok)
            self.assertGreater(latest, first + 5)
            ok, following = source.read()
            self.assertGreater(following, latest)
        finally:
            source.release()
        self.assertFalse(source.thread.is_alive())
        self.assertTrue(source.cap.released)

    @patch('video_source.cv2.VideoCapture', FakeCapture)
    def test_file_preserves_all_frames(self):
        source = VideoSource('video.avi', live=False)
        try:
            self.assertEqual([source.read()[1] for _ in range(3)], [1, 2, 3])
        finally:
            source.release()

    def test_disconnect(self):
        class BrokenCapture(FakeCapture):
            def read(self):
                return False, None
        with patch('video_source.cv2.VideoCapture', BrokenCapture):
            source = VideoSource(0, timeout=0.1)
            try:
                self.assertEqual(source.read(), (False, None))
            finally:
                source.release()


if __name__ == '__main__':
    unittest.main()
