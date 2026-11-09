"""Camera/video -> YOLO person tracking -> IN/OUT -> async ESP32."""
import argparse
import importlib.util
import logging
import os
import time
from datetime import datetime
from pathlib import Path

# Do not let Ultralytics install packages implicitly.
os.environ['YOLO_AUTOINSTALL'] = 'false'
os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(__file__).resolve().parent / '.ultralytics'))

from classroom_core import LineCounter, atomic_write_json
from esp32_client import ESP32Client
from mqtt_config import add_mqtt_args, resolve_prefix

STATUS_PATH = Path(__file__).resolve().parent / 'status.json'


def parse_source(source):
    return int(source) if source.isdigit() else source


def make_region(width, height, line_axis, position=0.5):
    if line_axis == 'horizontal':
        y = round((height - 1) * position)
        return [(0, y), (width - 1, y)]
    x = round((width - 1) * position)
    return [(x, 0), (x, height - 1)]


def parser_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='0')
    parser.add_argument('--line', choices=['horizontal', 'vertical'], default='horizontal')
    parser.add_argument('--enter', choices=['up', 'down', 'left', 'right'], default='down')
    parser.add_argument('--position', type=float, default=0.5, help='Line position, fraction 0..1')
    parser.add_argument('--margin', type=int, default=15, help='Dead band on each side, pixels')
    parser.add_argument('--cooldown', type=float, default=0.8)
    parser.add_argument('--initial', type=int, default=0)
    parser.add_argument('--esp32', default='')
    parser.add_argument('--transport', choices=['mqtt', 'http'], default='http',
                        help='Select MQTT or legacy HTTP/offline transport')
    add_mqtt_args(parser)
    parser.add_argument('--model', default=str(Path(__file__).resolve().parent / 'yolo26n.pt'))
    parser.add_argument('--conf', type=float, default=0.3)
    parser.add_argument('--imgsz', type=int, default=640)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--preview-port', type=int, default=8765, help='Local web preview port; 0 disables')
    parser.add_argument('--max-frames', type=int, default=0, help='0 = unlimited')
    parser.add_argument('--detect-only', action='store_true')
    args = parser.parse_args()
    if not 0 <= args.preview_port <= 65535:
        parser.error('--preview-port must be 0..65535')
    if args.transport == 'mqtt':
        try:
            args.topic_prefix = resolve_prefix(args)
        except ValueError as exc:
            parser.error(str(exc))
    if args.initial < 0 or not 0 < args.position < 1 or args.margin < 0 or args.cooldown < 0:
        parser.error('Invalid initial/position/margin/cooldown')
    if not 0 < args.conf <= 1 or args.imgsz < 32 or args.max_frames < 0:
        parser.error('Invalid conf/imgsz/max-frames')
    if args.enter not in (('up', 'down') if args.line == 'horizontal' else ('left', 'right')):
        parser.error('--enter does not match --line')
    if not Path(args.model).is_file():
        parser.error('Model missing: supply a local .pt file (no automatic download).')
    if not args.detect_only and importlib.util.find_spec('lap') is None:
        parser.error('ByteTrack requires lap>=0.5.12 installed in .venv (see README).')
    return args


def main():
    args = parser_args()
    import cv2
    from ultralytics import YOLO
    from video_source import VideoSource
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    counter = LineCounter(args.initial, args.enter in ('down', 'right'), args.margin, args.cooldown)
    source = parse_source(args.source)
    is_file = isinstance(source, str) and Path(source).is_file()
    if args.transport == 'mqtt':
        from mqtt_client import MQTTESP32Client
        logging.info('MQTT %s:%s prefix=%s', args.mqtt_host, args.mqtt_port, args.topic_prefix)
        client = MQTTESP32Client(args.mqtt_host, args.mqtt_port, args.topic_prefix).start()
    else:
        client = ESP32Client(args.esp32).start()
    cap = None
    preview = None
    camera_state, message = 'starting', ''
    frames, last_saved = 0, 0

    def publish():
        atomic_write_json(STATUS_PATH, dict(people_count=counter.people_count,
            entered=counter.entered, exited=counter.exited, initial=counter.initial,
            camera_state=camera_state, camera_message=message,
            updated_at=datetime.now().astimezone().isoformat(timespec='seconds'),
            **client.snapshot()))

    try:
        if args.preview_port:
            from camera_preview import CameraPreview
            preview = CameraPreview(args.preview_port).start()
            logging.info('Web camera preview on 127.0.0.1:%s', args.preview_port)
        client.submit(counter.people_count)
        publish()
        model = YOLO(args.model)
        cap = VideoSource(source, live=not is_file)
        if not cap.isOpened():
            raise RuntimeError('Cannot open camera/video; try --source 1 or a local video.')
        while True:
            started = time.monotonic()
            ok, frame = cap.read()
            if not ok:
                if is_file:
                    camera_state, message = 'ended', 'Video ended; last occupancy retained.'
                    break
                raise RuntimeError('Camera disconnected/read failed; last occupancy retained.')
            height, width = frame.shape[:2]
            region = make_region(width, height, args.line, args.position)
            options = dict(classes=[0], conf=args.conf, imgsz=args.imgsz, device='cpu', verbose=False, save=False)
            if args.detect_only:
                result = model.predict(frame, **options)[0]
            else:
                result = model.track(frame, persist=True, tracker='bytetrack.yaml', **options)[0]
                positions = {}
                if result.boxes is not None and result.boxes.id is not None:
                    for track_id, box in zip(result.boxes.id.int().cpu().tolist(), result.boxes.xyxy.cpu().tolist()):
                        x1, y1, x2, y2 = box
                        distance = (y1 + y2) / 2 - region[0][1] if args.line == 'horizontal' else (x1 + x2) / 2 - region[0][0]
                        positions[track_id] = distance
                counter.update(positions, time.monotonic())
            camera_state, message = 'running', ''
            client.submit(counter.people_count)
            annotated = result.plot(conf=True)
            cv2.line(annotated, region[0], region[1], (0, 255, 255), 2)
            fps = 1 / max(time.monotonic() - started, 1e-6)
            label = f'Visible:{len(result.boxes)}' if args.detect_only else f'IN:{counter.entered} OUT:{counter.exited} PEOPLE:{counter.people_count}'
            cv2.putText(annotated, f'{label} FPS:{fps:.1f}', (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.putText(annotated, f'ENTER:{args.enter} | Q:quit R:reset to {args.initial}', (15, height - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            now = time.monotonic()
            if preview is not None:
                preview.submit(annotated)
            if now - last_saved >= 1:
                publish()
                last_saved = now
            key = -1
            if not args.headless:
                cv2.imshow('Smart Classroom', annotated)
                key = cv2.waitKey(1) & 0xFF
            if key == ord('r'):
                counter.reset(args.initial)
                for tracker in getattr(model.predictor, 'trackers', []):
                    tracker.reset()
                client.submit(counter.people_count)
                publish()
                logging.info('Reset occupancy to %s', args.initial)
            frames += 1
            if key == ord('q') or (args.max_frames and frames >= args.max_frames):
                camera_state, message = 'stopped', 'Stopped; last occupancy retained.'
                break
    except Exception as exc:
        camera_state, message = 'error', str(exc)
        logging.error('%s', message)
        raise
    except KeyboardInterrupt:
        camera_state, message = 'stopped', 'Interrupted; last occupancy retained.'
    finally:
        if preview is not None:
            preview.close()
        client.close()
        publish()
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        logging.info('%s: %s', camera_state, message)


if __name__ == '__main__':
    main()
