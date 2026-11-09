# Smart Classroom CV — Thành viên 2

Camera laptop/điện thoại → YOLO pretrained → ByteTrack → đếm IN/OUT → MQTT hoặc HTTP → ESP32/Mock → Dashboard Streamlit. Chạy CPU, không train model và không sửa firmware ESP32.

## 1. Chuẩn bị CMD Windows

Trong **mỗi cửa sổ CMD**, chạy:

```bat
cd /d D:\09_Document\IoT\SmartClassroom-CV\smart_classroom_cv
call .venv\Scripts\activate.bat
```

Môi trường đã kiểm tra: Python 3.13.0, Ultralytics 8.4.190, OpenCV 5.0.0, Torch 2.14.1+cpu, Streamlit 1.66.1. Kiểm tra mới nhất xác nhận **paho-mqtt 2.1.0 và lap 0.5.13 đã có trong `.venv`**, không cần cài lại.

Kiểm tra thư viện:

```bat
python -m pip show paho-mqtt lap
python -m pip check
```

Khi dựng môi trường mới, cần Internet để cài dependencies:

```bat
py -3.13 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### Tải model YOLO

File model `yolo26n.pt` được bỏ qua bởi `.gitignore`, nên khi clone từ GitHub bạn cần tải riêng. Sau khi cài dependencies và kích hoạt `.venv`, chạy lệnh sau trong thư mục dự án (cùng cấp với `count_people.py`), khi có Internet:

```bat
python -c "from ultralytics import YOLO; YOLO('yolo26n.pt')"
```

Ultralytics sẽ tải model pretrained nếu chưa có. Nếu file đã tồn tại, lệnh sẽ dùng file hiện có. Kiểm tra file sau khi tải:

```bat
dir yolo26n.pt
```

Chỉ cần tải một lần. Chương trình của dự án không tự tải model hoặc tự cài thư viện; `--model` phải trỏ đến file `.pt` local. Mặc định chương trình dùng `yolo26n.pt` trong thư mục làm việc. Nếu lưu model ở nơi khác, truyền đường dẫn khi chạy, ví dụ:

```bat
python count_people.py --model "D:\Models\yolo26n.pt" --source 0
```

## 2. Prefix và topic MQTT đã cấu hình

Broker: **broker.hivemq.com**, cổng **1883**, MQTT 3.1.1 qua TCP, không username/password.

File `mqtt_config.json` đã lưu prefix:

```text
smartclassroom/group2/b49deeab1b5f4154a763e95db036f461
```

CV và MQTT Mock tự đọc file này, **không cần nhập `--topic-prefix`**. Hai topic chính xác để gửi cho thành viên phụ trách ESP32:

| Chức năng | Topic |
|---|---|
| Python publish, ESP32 subscribe | `smartclassroom/group2/b49deeab1b5f4154a763e95db036f461/occupancy` |
| ESP32 publish, Python subscribe | `smartclassroom/group2/b49deeab1b5f4154a763e95db036f461/status` |

`<prefix>` trong các mô tả giao thức chỉ là ký hiệu thay thế, không nhập nguyên chữ đó vào topic.

`mqtt_config.json` được bỏ qua bởi `.gitignore`. Khi chuyển sang máy khác, sao chép file này hoặc thêm cùng `--topic-prefix` cho cả CV và Mock. Nếu file bị mất, chương trình sẽ tạo prefix ngẫu nhiên mới. Có thể xem cấu hình bằng CMD:

```bat
type mqtt_config.json
```

Không chạy Mock và ESP32 thật cùng prefix khi tích hợp. Broker public/1883 không mã hóa và người khác có thể đọc/ghi topic: chỉ dùng thử nghiệm, không gửi dữ liệu nhạy cảm. Python không gửi video lên MQTT.

## 3. Chạy demo MQTT với ba CMD

Dừng CV cũ bằng `Q` trước khi chạy CV mới. Chỉ một chương trình CV hoặc smoke test được ghi `status.json` tại một thời điểm.

**CMD 1 — MQTT Mock ESP32:**

```bat
python mqtt_mock_esp32.py
```

**CMD 2 — YOLO + ByteTrack + đếm + MQTT, dùng camera laptop:**

```bat
python count_people.py --transport mqtt --source 0 --imgsz 320 --line horizontal --enter down --initial 0
```

Nếu dùng điện thoại, thay lệnh CMD 2 bằng lệnh DroidCam trong mục 4.

**CMD 3 — Dashboard:**

```bat
python -m streamlit run dashboard.py
```

Mở http://localhost:8501. Dashboard đọc `status.json` do CV xuất, gồm sĩ số, tổng IN/OUT, trạng thái camera/kết nối, nhiệt độ, độ ẩm, ánh sáng, quạt/đèn và thời điểm cập nhật. Không cần đặt biến `ESP32_BASE_URL`.

Demo lần lượt:

1. Kiểm tra hình camera và đặt điện thoại/camera cố định.
2. Với `--enter down`, đi từ trên xuống qua đường để tăng IN; đi ngược để tăng OUT.
3. Kiểm tra sĩ số, cảm biến và relay trên Dashboard. Mock hiển thị nhãn giả lập; relay được tính theo sĩ số nhận qua MQTT.
4. Dừng Mock bằng Ctrl+C, đợi hơn 10 giây để kiểm tra cảnh báo; dữ liệu gần nhất được giữ lại.
5. Chạy lại Mock để thử phục hồi. CV làm mới occupancy mỗi 15 giây để đồng bộ lại.
6. Nhấn `Q` ở cửa sổ CV để thoát; Ctrl+C ở các CMD server để dừng.

Có thể cấu hình cảm biến giả lập:

```bat
python mqtt_mock_esp32.py --temperature 31 --humidity 75 --light 100
```

## 4. DroidCam không cần Client Windows

Điện thoại và laptop kết nối cùng mạng Wi-Fi. Mở DroidCam trên điện thoại, lấy WiFi IP và port. Ví dụ URL `http://192.168.1.20:4747/video`; **thay IP và port bằng giá trị thực trên điện thoại**.

Mở URL trên trình duyệt laptop trước. Sau khi thấy video, thử nguồn ảnh:

```bat
python camera_test.py --source "http://192.168.1.20:4747/video"
```

Thử phát hiện person:

```bat
python detect_people.py --source "http://192.168.1.20:4747/video" --imgsz 320
```

Thoát chương trình kiểm tra rồi chạy CV qua MQTT:

```bat
python count_people.py --transport mqtt --source "http://192.168.1.20:4747/video" --imgsz 320 --line horizontal --enter down --initial 0
```

Nguồn live được đọc liên tục ở luồng nền, chỉ giữ frame mới nhất để tránh tích tụ ảnh cũ. File video vẫn đọc tuần tự. HTTP/RTSP dùng backend FFmpeg với timeout mở/đọc 10 giây.

Nếu `camera_test.py` cũng trễ, kiểm tra luồng điện thoại/mạng. Nếu chỉ nhận diện trễ, thử `--imgsz 320`. Cơ chế lấy frame mới nhất không loại bỏ thời gian truyền ảnh/inference; bỏ frame có thể làm tracking kém hơn khi người đi nhanh. Chưa đo độ trễ trên điện thoại của người dùng.

## 5. Kiểm thử MQTT không cần camera

Dừng CV đang chạy trước, rồi chạy:

```bat
python mqtt_smoke_test.py --timeout 30
```

Script tự khởi động MQTT Mock và client, dùng nhánh topic `/test/<UUID>` riêng, không cần mở Mock ở CMD khác. Gửi sĩ số **0 → 5 → 2**, xác nhận status/relay trả về, dừng Mock và kiểm tra dữ liệu hết hạn nhưng vẫn giữ sĩ số 2. Có timeout và trả mã lỗi nếu không kết nối/nhận phản hồi.

Script ghi snapshot để Dashboard xem dữ liệu giả lập; camera được đánh dấu `simulation` nên Dashboard cảnh báo camera không chạy là đúng. Test này không kiểm tra YOLO hoặc độ chính xác IN/OUT.

Unit/integration test local:

```bat
python -m unittest -v test_mqtt test_video_source test_classroom
python -m pip check
```

## 6. Hợp đồng MQTT cho ESP32

Python gửi vào topic occupancy:

```json
{"people_count":5}
```

ESP32/Mock gửi vào topic status:

```json
{"people_count":5,"temperature":30.5,"humidity":70,"light":180,"fan":true,"light_on":true}
```

Mock thêm `"mock":true`; ESP32 thật không cần trường này. `people_count` trong status là tùy chọn với CV nhưng hữu ích để đối chiếu.

- QoS 1, retain=false; chương trình bỏ qua thông điệp retained nhận vào.
- ESP32 đặt sĩ số bằng giá trị nhận, không cộng dồn vì QoS 1 có thể nhận trùng.
- Publish chạy nền, chờ ACK ngoài vòng lặp video; gửi khi đổi số, làm mới mỗi 15 giây. Hàng đợi Paho giới hạn 4 thông điệp.
- Mock gửi status mỗi 2 giây sau khi nhận occupancy và khi nhận cập nhật. ESP32 thật cần gửi status định kỳ nhanh hơn 10 giây.
- Kết nối broker chưa đủ để báo ESP32 online: phải có status hợp lệ trong 10 giây gần nhất. Mất kết nối giữ số liệu cũ, tự reconnect với backoff.
- `temperature`, `humidity`, `light` là số hữu hạn; độ ẩm 0..100, ánh sáng không âm; `fan`, `light_on` là boolean.

Tham khảo API: [Paho MQTT Python](https://eclipse.dev/paho/clients/python/docs/), [HiveMQ Public Broker](https://www.hivemq.com/mqtt/public-mqtt-broker/).

## 7. HTTP dự phòng và offline

HTTP được chọn rõ ràng, không tự chuyển qua lại khi MQTT mất kết nối. Để tương thích lệnh cũ, mặc định `--transport` vẫn là `http`; muốn MQTT phải thêm `--transport mqtt`.

CMD riêng cho HTTP Mock:

```bat
python mock_esp32.py
```

CMD riêng cho CV:

```bat
python count_people.py --transport http --source 0 --imgsz 320 --esp32 http://127.0.0.1:8000
```

Với ESP32 thật, thay URL bằng IP thiết bị. Có thể thay `--source 0` bằng URL DroidCam. Dashboard chạy cùng lệnh như MQTT.

- `POST /api/occupancy`: `{"people_count":5}`, mã 2xx là thành công.
- `GET /api/status`: các trường cảm biến/relay như JSON MQTT ở trên.
- Worker nền: timeout 1.5 giây/request, chu kỳ 2 giây; chỉ POST khi thay đổi, retry khi lỗi. GET định kỳ.
- Nếu status trả `people_count` khác số đã gửi, client đồng bộ lại. Nếu ESP32 không trả trường này, Python không phát hiện được thiết bị đã quên sĩ số sau reboot; cần chạy lại với `--initial` đúng.

Chạy offline, không gửi mạng:

```bat
python count_people.py --transport http --source 0 --imgsz 320
```

## 8. Camera, tracking và counting

| Tham số | Ý nghĩa |
|---|---|
| `--source 0` | Camera laptop; thử 1/2 cho webcam khác, hoặc URL/file video |
| `--line horizontal` | Đường ngang; hướng vào `down` hoặc `up` |
| `--line vertical` | Đường dọc; hướng vào `right` hoặc `left` |
| `--position 0.5` | Vị trí đường theo tỷ lệ ảnh, lớn hơn 0 và nhỏ hơn 1 |
| `--initial 3` | Số người đã có trong phòng khi bắt đầu |
| `--margin 15` | Vùng đệm 15 pixel mỗi phía để hạn chế rung gần đường |
| `--cooldown 0.8` | Thời gian tối thiểu giữa hai lượt đếm cùng ID |
| `--conf 0.3` | Ngưỡng confidence |
| `--imgsz 320` | Kích thước inference; có thể dùng 416/640 |
| `--headless --max-frames 30` | Chạy thử không cửa sổ, giới hạn frame |

Sĩ số = `max(0, initial + IN - OUT)`. Tâm bounding box phải chuyển hẳn sang phía đối diện ngoài vùng đệm mới tính lượt. ID vắng mặt quá 2 giây bị xóa lịch sử. Nhấn `R` để xóa IN/OUT và tracking, đặt lại sĩ số về `--initial`; muốn số khác, chạy lại với `--initial N`.

Ví dụ video sẵn có:

```bat
python count_people.py --source "D:\video\door.mp4" --initial 3 --enter down
```

`detect_people.py` chỉ phát hiện person, không suy ra sĩ số từ số người nhìn thấy. YOLO dùng pretrained, chỉ class person, CPU mặc định; API `YOLO.track(..., persist=True, tracker='bytetrack.yaml')` đã đối chiếu bản cài.

Camera lỗi xuất trạng thái error và giữ sĩ số cuối; video hết xuất ended. Dashboard cảnh báo snapshot cũ trên 10 giây. Snapshot ghi nguyên tử tối đa mỗi giây và ở sự kiện quan trọng, không ghi ảnh/video hoặc log mỗi frame.

## 9. Kết quả đã kiểm tra và giới hạn

- **22 test đạt**: counting, vùng đệm/cooldown/reset, nhiều ID, frame mới nhất, HTTP thật với Mock local, validation, MQTT client giả, reconnect/status cũ, QoS 1/retain=false và khử publish trùng.
- `pip check` đạt trong lần chạy kiểm thử đã ghi nhận.
- Đã chạy camera laptop 640×480 với YOLO/ByteTrack qua HTTP Mock; snapshot xác nhận camera running, ESP32 connected và đủ cảm biến. Dashboard health trả 200; giao diện từng được kiểm tra bằng Streamlit AppTest.
- Đã chạy inference CPU trên video đen 5 frame tự tạo; đây chỉ là smoke test. Nguồn video lỗi được kiểm tra giữ sĩ số và báo cảnh báo.
- **Đã xác nhận cài paho-mqtt 2.1.0 và lap 0.5.13. Chưa có kết quả xác nhận Publish/Subscribe thật qua HiveMQ**; cần chạy `mqtt_smoke_test.py` để xác nhận trên mạng hiện tại. Lần cài Paho trước từng bị môi trường công cụ chặn mạng với WinError 10013; tình trạng thiếu thư viện đó hiện đã được khắc phục.
- Chưa đánh giá độ chính xác người thật qua cửa, che khuất/đi sát nhau, rút camera ngoài hoặc ESP32/cảm biến/relay thật. ByteTrack có thể đổi ID và làm sai đếm; đây là ước lượng sĩ số, không nhận diện danh tính.

## 10. Các file chính

| File | Vai trò |
|---|---|
| `count_people.py` | Camera, YOLO/ByteTrack, counting và chọn transport |
| `detect_people.py`, `camera_test.py` | Kiểm tra phát hiện hoặc chỉ camera |
| `video_source.py`, `classroom_core.py` | Đọc nguồn live, bộ đếm và xử lý dữ liệu |
| `mqtt_config.py`, `mqtt_config.json` | Cấu hình broker/CLI và prefix đã lưu |
| `mqtt_client.py`, `mqtt_mock_esp32.py` | MQTT client và Mock ESP32 |
| `mqtt_smoke_test.py` | Kiểm thử dữ liệu giả lập qua broker thật |
| `esp32_client.py`, `mock_esp32.py` | HTTP dự phòng |
| `dashboard.py`, `status.json` | Dashboard và snapshot runtime |
| `test_classroom.py`, `test_video_source.py`, `test_mqtt.py` | Kiểm thử local |
| `requirements.txt` | Dependencies |
| `RUN_RESULTS.md` | Kết quả của phiên chạy trước, mang tính lịch sử |

## 11. Xem camera nhận diện ngay trên web

Dashboard đã có khung camera với bounding box/confidence, đường đếm, sĩ số và FPS từ CV. Cần dừng rồi chạy lại CV sau khi cập nhật code để bật preview. Không mở nguồn camera lần thứ hai trong Dashboard.

CMD 1 (MQTT Mock):

```bat
python mqtt_mock_esp32.py
```

CMD 2 (CV; thay IP bằng điện thoại thực tế):

```bat
python count_people.py --transport mqtt --source "http://192.168.1.20:4747/video" --imgsz 320 --headless
```

Dùng camera laptop thì thay URL bằng `0`. `--headless` chỉ tắt cửa sổ OpenCV, nhận diện/tracking/counting và preview web vẫn chạy. Dừng bằng Ctrl+C ở CMD; phím Q/R chỉ dùng khi có cửa sổ OpenCV. Muốn đặt lại sĩ số khi headless, dừng và chạy lại với `--initial N`.

CMD 3:

```bat
python -m streamlit run dashboard.py
```

Mở http://localhost:8501. Dashboard nhận JPEG từ endpoint local `http://127.0.0.1:8765/frame`, cập nhật tối đa 5 lần/giây. Preview chỉ giữ ảnh mới nhất trong RAM, không ghi ảnh từng frame vào ổ cứng, không gửi video qua MQTT. Ảnh quá 3 giây sẽ bị từ chối để web báo chưa có hình mới thay vì giữ ảnh cũ như video đang chạy.

HTTP và offline cũng tự bật preview như MQTT. Tắt bằng `--preview-port 0`. Nếu cổng 8765 bị chiếm, dừng CV cũ hoặc chọn cổng khác cho CV và đặt URL tương ứng trong CMD chạy Dashboard:

```bat
python count_people.py --source 0 --imgsz 320 --headless --preview-port 8766
```

```bat
set CAMERA_PREVIEW_URL=http://127.0.0.1:8766/frame
python -m streamlit run dashboard.py
```

Preview endpoint chỉ lắng nghe loopback trên máy chạy CV; Dashboard lấy ảnh phía server rồi hiển thị qua Streamlit. Tốc độ thực tế phụ thuộc camera, mạng và CPU. Preview không làm YOLO chạy nhanh hơn.

Đã chạy **23 kiểm thử đạt**, gồm kiểm tra JPEG giải mã được, thiếu ảnh/ảnh hết hạn trả 503 và Dashboard render ảnh bằng Streamlit AppTest. File mới: `camera_preview.py`, `test_camera_preview.py`; cập nhật `count_people.py`, `dashboard.py` và README.
