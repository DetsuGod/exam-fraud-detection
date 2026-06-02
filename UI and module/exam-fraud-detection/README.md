# AI Exam Proctoring System - Hệ Thống Giám Sát Phòng Thi Thông Minh

Hệ thống giám sát phòng thi thông minh sử dụng mô hình học sâu **YOLOv8** và framework **FastAPI** để phát hiện các hành vi vi phạm quy chế thi cử theo thời gian thực từ webcam của thí sinh.

---

# 🚀 Hướng Dẫn Chạy Hệ Thống

Hệ thống hỗ trợ chạy tự động qua file script trên hệ điều hành Windows hoặc cài đặt thủ công.

---

## ⚡ Cách 1: Chạy Tự Động (Khuyên Dùng trên Windows)

1. Kích đúp vào file `run.bat` tại thư mục gốc của dự án.

2. Script sẽ tự động thực hiện các bước:

   * Kiểm tra cài đặt Python
   * Khởi tạo môi trường ảo Python (`.venv`) nếu chưa có
   * Nâng cấp `pip`
   * Tự động cài đặt toàn bộ thư viện trong `requirements.txt`
   * Khởi động máy chủ Web Uvicorn

3. Truy cập hệ thống tại:

```text
http://127.0.0.1:8000
```

---

## 🛠️ Cách 2: Cài Đặt và Chạy Thủ Công

### 1. Tạo môi trường ảo

```bash
python -m venv .venv
```

---

### 2. Kích hoạt môi trường ảo

#### Windows CMD

```bash
.venv\Scripts\activate.bat
```

#### Windows PowerShell

```bash
.venv\Scripts\Activate.ps1
```

#### Linux/macOS

```bash
source .venv/bin/activate
```

---

### 3. Cài đặt thư viện

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 4. Chạy Uvicorn Server

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### 5. Truy cập hệ thống

```text
http://127.0.0.1:8000
```

---

# 🛠️ Các Chức Năng Chính Của Hệ Thống

## 1. Phân Tích Video Thời Gian Thực

* Streaming webcam qua WebSocket
* Phân tích khung hình bằng YOLOv8
* Hiển thị detection theo thời gian thực
* Độ trễ thấp

---

## 2. Theo Dõi & Định Danh Thí Sinh

* Sử dụng thuật toán Centroid Tracker
* Gán ID tự động (`id01`, `id02`, ...)
* Theo dõi liên tục kể cả khi che khuất ngắn hạn

---

## 3. Quản Lý Phiên Thi

* Bắt đầu phiên thi
* Khóa vị trí ban đầu của thí sinh
* Kết thúc phiên thi
* Theo dõi trạng thái phiên thi realtime

---

## 4. Hệ Thống Phát Hiện Vi Phạm

### 🚨 Các hành vi được phát hiện

* Rời khỏi vị trí
* Di chuyển quá xa vị trí ban đầu
* Xuất hiện người lạ
* Sử dụng điện thoại
* Mang sách/tài liệu
* Phát hiện laptop hoặc màn hình phụ

---

## 5. Hệ Thống Cảnh Báo AI

### 🔊 Bao gồm:

* Còi cảnh báo
* Giọng nói AI tiếng Việt
* Đọc ID thí sinh vi phạm
* Tùy chỉnh bật/tắt âm thanh

Ví dụ:

```text
"Cảnh báo. Thí sinh id01 đã rời khỏi vị trí!"
```

---

## 6. Suspicion Index

* Chỉ số nghi vấn từ `0% - 100%`
* Biểu đồ realtime
* Lịch sử vi phạm
* Log theo thời gian thực

---

# 🧠 Công Nghệ Sử Dụng

| Công Nghệ  | Vai Trò             |
| ---------- | ------------------- |
| YOLOv8     | Object Detection    |
| FastAPI    | Backend API         |
| WebSocket  | Real-time Streaming |
| OpenCV     | Xử lý ảnh           |
| JavaScript | Frontend            |
| HTML/CSS   | Dashboard UI        |
| Uvicorn    | ASGI Server         |

---

# 📁 Cấu Trúc Thư Mục Dự Án

```text
model/
│
├── app/
│   ├── templates/
│   │   └── index.html
│   └── main.py
│
├── .venv/
├── requirements.txt
├── run.bat
├── yolov8n.pt
└── README.md
```

---

# 📦 Cài Đặt Thư Viện Chính

```bash
pip install ultralytics fastapi uvicorn opencv-python websockets numpy
```

---

# 🎯 Mô Hình AI Sử Dụng

* YOLOv8 Nano (`yolov8n.pt`)
* Pretrained trên COCO Dataset
* Fine-tune cho môi trường phòng thi

---

# 📸 Các Đối Tượng Được Nhận Diện

| Đối Tượng  | Trạng Thái |
| ---------- | ---------- |
| Person     | ✅          |
| Cell Phone | ✅          |
| Book       | ✅          |
| Laptop     | ✅          |

---

# 🔥 Hướng Phát Triển Trong Tương Lai

* Face Recognition
* Pose Estimation
* Multi-camera Tracking
* Transformer-based Action Recognition
* AI Report Generation
* Cloud Deployment
* Database Logging
* Anti-Spoofing Detection

---

# 👨‍💻 Tác Giả

Developed by **DetsuGod**

---

# ⭐ License

This project is developed for educational and research purposes.
