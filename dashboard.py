"""Live dashboard from periodic CV snapshot; no network in the UI."""
import json
import os
from datetime import datetime
from pathlib import Path
import streamlit as st
import requests

STATS_FILE = Path(__file__).resolve().parent / 'status.json'
st.set_page_config(page_title='Smart Classroom', layout='wide')
st.title('Smart Classroom Dashboard')
PREVIEW_URL = os.environ.get('CAMERA_PREVIEW_URL', 'http://127.0.0.1:8765/frame')


@st.fragment(run_every=0.2)
def show_camera():
    st.subheader('Camera trực tiếp — YOLO / Tracking')
    try:
        response = requests.get(PREVIEW_URL, timeout=0.5)
        response.raise_for_status()
        if not response.headers.get('Content-Type', '').startswith('image/jpeg'):
            raise ValueError('Invalid camera response')
        st.image(response.content, width='stretch')
    except (requests.RequestException, ValueError):
        st.info('Chưa có hình camera mới. Chạy count_people.py; nếu đang chạy bản cũ, hãy dừng rồi chạy lại.')


@st.fragment(run_every='2s')
def show_live_data():
    st.subheader('Thông số lớp học')
    try:
        stats = json.loads(STATS_FILE.read_text(encoding='utf-8'))
        age = (datetime.now().astimezone() - datetime.fromisoformat(stats['updated_at'])).total_seconds()
    except (OSError, ValueError, KeyError, TypeError):
        st.info('Chưa có dữ liệu hợp lệ. Chạy count_people.py trước.')
        return
    a, b, c = st.columns(3)
    a.metric('Sĩ số gần nhất', stats['people_count'])
    b.metric('Tổng lượt vào', stats['entered'])
    c.metric('Tổng lượt ra', stats['exited'])
    st.write('Cập nhật CV:', stats['updated_at'])
    if age > 10:
        st.warning(f'Dữ liệu CV đã cũ ({age:.0f} giây). Sĩ số được giữ nguyên.')
    if stats.get('camera_state') != 'running':
        st.warning(f"Camera: {stats.get('camera_state')} — {stats.get('camera_message', '')}")
    connected = stats.get('esp32_connected') and age <= 10 and stats.get('camera_state') == 'running'
    if connected:
        st.success('ESP32 / Mock: kết nối thành công tại lần kiểm tra gần nhất')
    else:
        st.warning('ESP32: mất kết nối hoặc CV đã dừng; ' + stats.get('esp32_message', ''))
    device = stats.get('device')
    if device:
        st.caption('Cảm biến cập nhật: ' + str(stats.get('device_updated_at')))
        if not connected:
            st.caption('Các giá trị cảm biến bên dưới là dữ liệu cũ.')
        sensor_cols = st.columns(3)
        for col, label, value in zip(sensor_cols, ['Nhiệt độ', 'Độ ẩm', 'Ánh sáng'],
                [f"{device['temperature']} °C", f"{device['humidity']} %", f"{device['light']} lux"]):
            col.metric(label, value)
        relay_cols = st.columns(2)
        for col, label, value in zip(relay_cols, ['Quạt', 'Đèn'],
                ['ON' if device['fan'] else 'OFF', 'ON' if device['light_on'] else 'OFF']):
            col.metric(label, value)
        if device.get('mock'):
            st.info('Mock Server: cảm biến giả lập, relay tính theo sĩ số nhận qua MQTT hoặc HTTP.')
    else:
        st.info('Chưa nhận được cảm biến. Kiểm tra MQTT Mock hoặc --esp32 khi dùng HTTP.')


camera_column, stats_column = st.columns([3, 2], gap='large')
with camera_column:
    show_camera()
with stats_column:
    show_live_data()
