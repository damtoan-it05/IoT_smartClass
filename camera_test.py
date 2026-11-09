"""Camera preview without loading a model."""
import argparse
import os
from pathlib import Path
import cv2
from count_people import parse_source
from video_source import VideoSource


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='0')
    args = parser.parse_args()
    source = parse_source(args.source)
    cap = VideoSource(source, live=not (isinstance(source, str) and Path(source).is_file()))
    try:
        if not cap.isOpened():
            raise RuntimeError('Cannot open camera/video.')
        while True:
            ok, frame = cap.read()
            if not ok:
                print('Video ended or camera read failed.')
                break
            cv2.imshow('Camera Test - Q to quit', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
