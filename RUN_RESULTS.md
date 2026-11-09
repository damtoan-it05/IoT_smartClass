# Kết quả chạy ngày 2026-11-03

- `lap 0.5.13` đã có trong .venv.
- Cài `paho-mqtt>=2.1,<3` vào .venv thất bại: kết nối pip ra Internet bị chặn, WinError 10013. Chưa cài được Paho, chưa kiểm thử HiveMQ thật.
- 22 unit/integration test offline đạt, `pip check` đạt.
- Đã khởi động HTTP Mock tại http://127.0.0.1:8000 và Dashboard tại http://127.0.0.1:8501; health trả 200.
- Đã khởi động count_people.py với --transport http --source 0 --imgsz 320 --esp32 http://127.0.0.1:8000. Snapshot xác nhận camera_state=running và esp32_connected=true, nhận đủ dữ liệu cảm biến giả lập.
- Chưa có URL DroidCam từ người dùng nên phiên demo này dùng camera laptop.

Để cài MQTT từ CMD của người dùng (ngoài môi trường công cụ bị hạn chế mạng):

```bat
cd /d D:\09_Document\IoT\SmartClassroom-CV\smart_classroom_cv
.venv\Scripts\python.exe -m pip install "paho-mqtt>=2.1,<3"
```

Sau khi dừng chương trình CV hiện chạy để tránh cùng ghi status.json:

```bat
.venv\Scripts\python.exe mqtt_smoke_test.py
```
