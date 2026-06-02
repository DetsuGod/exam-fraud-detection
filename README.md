# AI-Proctor: Hệ Thống Giám Sát Phòng Thi Thông Minh Song Song 2 Luồng AI

Hệ thống **AI-Proctor** là giải pháp giám sát phòng thi thông minh toàn diện ứng dụng mô hình học sâu **YOLOv8** tích hợp thuật toán xử lý luồng **Haar Cascades** và **Centroid Tracker**. Hệ thống hoạt động hoàn hảo dưới dạng ứng dụng Web thời gian thực thông qua framework **FastAPI (Python)** kết hợp với giao diện làm bài thi React hiện đại (**Vite + React JS**) giúp giám thị phát hiện mọi hành vi vi phạm quy chế thi cử một cách tự động và chuẩn xác.

---

## 🚀 Các Tính Năng Vượt Trội Của Hệ Thống

### 1. Giám Sát Camera Kép Song Song (Dual-Camera AI)
* **Dò tìm và phân bổ thông minh**: Dashboard tự động nhận dạng tất cả các webcam đang cắm vào máy tính.
* **Camera Thí Sinh (User Cam)**: Mở luồng camera laptop trực diện chạy mô hình AI phát hiện khuôn mặt quay đầu, liếc mắt (Haar Cascades) và sử dụng điện thoại/tài liệu (YOLOv8).
* **Camera Toàn Cảnh (CCTV Cam)**: Tự động kết nối với camera phụ (như ứng dụng **Iriun Webcam** qua điện thoại) truyền luồng hình ảnh CCTV thực tế. AI chạy thuật toán **Centroid Tracker** tự động gán ID và theo dõi mọi người di chuyển xung quanh phòng thi, phát hiện người lạ đột nhập hoặc rời khỏi vị trí thi.
* **Tính năng Cắm-và-Chạy (Plug & Play)**: Tự động chuyển đổi luồng khi camera Iriun được bật/tắt hoặc cắm thêm camera USB mà không cần tải lại trang.

### 2. Đồng Bộ Vi Phạm Trang Exam Thời Gian Thực (Exam Violation Sync)
* **Tích hợp trang thi React cao cấp**: Người dùng đăng nhập làm bài thi tại `/exam` bằng giao diện làm bài thi trắc nghiệm hiện đại.
* **Chụp ảnh màn hình Tab đích trễ 350ms**: Khi thí sinh chuyển tab hoặc mất tập trung, React hook tự động tạo trễ **350ms** để camera chia sẻ màn hình bắt trọn chính xác giao diện tab mới (ví dụ: Google, ChatGPT) làm bằng chứng vi phạm.
* **Bắt trọn 4 loại sự kiện vi phạm**:
  * `BLUR`: Chuyển tab hoặc nhấp chuột ra ngoài màn hình thi.
  * `VISIBILITY_CHANGE`: Ẩn màn hình làm bài thi (chuyển sang phần mềm khác).
  * `COPY_DETECTED`: Thí sinh thực hiện sao chép nội dung câu hỏi (`Ctrl + C`).
  * `SCREEN_SHARE_STOPPED`: Dừng chia sẻ màn hình làm bài thi (hệ thống lập tức khóa màn hình làm bài).

### 3. Nút Điều Khiển Phiên Thi & Khóa Trạng Thái 15 Giây
* **Nút kích hoạt toàn cục (Global Session Toggle)**: Nút bật/tắt phiên thi thiết kế neon động rực rỡ tại Header. AI chỉ ghi nhận log vi phạm và lưu bằng chứng khi phiên thi được BẬT. Khi TẮT, AI vẫn vẽ khung nhận diện nhưng không báo cáo vi phạm để tránh rác dữ liệu trước giờ thi.
* **Cơ chế Khóa trạng thái 15 giây (Status Lock)**: Khi xảy ra vi phạm từ trang thi, Dashboard sẽ khóa cứng thẻ trạng thái thí sinh thành màu đỏ nhấp nháy (`danger`) hoặc vàng (`warning`) trong **15 giây** để đảm bảo giám thị kịp phát hiện, ngăn webcam AI camera tự động reset trạng thái về bình thường ở các khung hình kế tiếp.

### 4. Tái Cấu Trúc Thư Mục LOG Phiên Thi Khoa Học
* Khi bắt đầu phiên thi, hệ thống tự động tạo thư mục phiên thi mới dạng `LOG phiên/ngày... phiên...` bên trong chứa sẵn 2 thư mục con:
  * **`camera/`**: Lưu ảnh chụp bằng AI webcam khi thí sinh vi phạm trực diện (nhìn lệch, dùng điện thoại, v.v.).
  * **`Exam/`**: Lưu ảnh chụp màn hình bài thi do React gửi về khi thí sinh chuyển tab, copy bài, dừng chia sẻ màn hình.

### 5. Cảnh Báo Phát Phát Giọng Nói AI (Text-to-Speech)
* Khi giám thị nhấp vào nút **"Cảnh cáo thoại"** trên thanh chi tiết của thí sinh, hệ thống tự động phát âm thanh cảnh báo bằng giọng nói tiếng Việt tự nhiên hướng thẳng đến thí sinh để yêu cầu tập trung làm bài (ví dụ: *"Thí sinh B202_1, yêu cầu tập trung làm bài thi!"*).

---

## 🧠 Công Nghệ Sử Dụng

| Công Nghệ | Vai Trò |
| :--- | :--- |
| **YOLOv8** | Nhận diện vật thể thông minh (Điện thoại, Sách, Máy tính Casio). |
| **Centroid Tracker** | Theo dõi, gán ID và giám sát chuyển vị trí của thí sinh thời gian thực. |
| **Haar Cascades** | Phân tích hướng quay đầu (Profile) và liếc mắt (Eye Glance). |
| **FastAPI** | Backend máy chủ API & WebSocket tốc độ cao. |
| **React JS + Vite** | Giao diện làm bài thi của thí sinh (`/exam`) mượt mà, bảo mật. |
| **HTML/CSS / Tailwind** | Giao diện Dashboard Admin Glassmorphism tối Neon cao cấp. |

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
model/
│
├── app/
│   ├── templates/
│   │   └── dashboard.html       # Giao diện chính của Giám thị
│   └── main.py                  # API Server & WebSocket Handler
│
├── UI and module/
│   └── Exam screen/             # Dự án React JS làm bài thi của Thí sinh
│       ├── src/
│       │   ├── hooks/
│       │   │   └── useExamMonitor.js  # Hooks bắt sự kiện chuyển tab, copy trễ 350ms
│       │   └── pages/
│       │       └── ExamPage.jsx # Giao diện bài thi
│       └── dist/                # Bản build tĩnh phân phối sang FastAPI
│
├── LOG phiên/                   # Thư mục lưu trữ hình ảnh vi phạm
│   └── ngày DD tháng MM năm YYYY phiên N/
│       ├── camera/              # Lưu ảnh chụp webcam AI phát hiện
│       └── Exam/                # Lưu ảnh chụp màn hình bài thi khi vi phạm
│
├── backups/                     # Các bản sao lưu dự phòng
├── best.pt                      # Mô hình YOLOv8 custom (Casio, Điện thoại, Sách)
├── yolov8n.pt                   # Mô hình YOLOv8 Nano chuẩn
├── requirements.txt             # Khai báo các thư viện Python
├── run.bat                      # File chạy tự động một-nhấp
├── train.py                     # File huấn luyện mô hình YOLOv8 tham khảo
└── README.md                    # Tài liệu hướng dẫn
```

---

## 🚀 Hướng Dẫn Vận Hành Hệ Thống

Hệ thống hỗ trợ chạy tự động qua file script trên hệ điều hành Windows cực kỳ nhanh chóng.

### ⚡ Cách 1: Chạy Tự Động (Khuyên Dùng)

#### A. Chạy nội bộ (Chỉ máy của bạn truy cập)
1. Kích đúp vào file `run.bat` tại thư mục gốc của dự án.
2. Script sẽ tự động thực hiện:
   * Khởi tạo môi trường ảo Python (`.venv`) và nâng cấp `pip`.
   * Tải và cài đặt toàn bộ thư viện cần thiết trong `requirements.txt`.
   * Tự động dò tìm NVIDIA GPU và cài đặt PyTorch hỗ trợ **CUDA** để đạt số khung hình (FPS) cực cao.
   * Khởi động máy chủ Web Uvicorn tại cổng **`8001`** chỉ kết nối được từ máy cục bộ.
3. **Truy cập hệ thống**:
   * **Dashboard Giám Thị**: [http://127.0.0.1:8001/](http://127.0.0.1:8001/)
   * **Trang Bài Thi Thí Sinh**: [http://127.0.0.1:8001/exam](http://127.0.0.1:8001/exam)

#### B. Chạy trong mạng LAN (Mọi người cùng mạng Wi-Fi/LAN đều truy cập được)
1. Kích đúp vào file `run_lan.bat` tại thư mục gốc của dự án.
2. Script sẽ thực hiện toàn bộ quá trình thiết lập môi trường tự động tương tự như trên, đồng thời:
   * Tự động dò tìm địa chỉ IP mạng nội bộ của máy tính của bạn (Local IP).
   * Khởi chạy máy chủ với host `0.0.0.0`, cho phép nhận kết nối từ mọi thiết bị chung mạng Wi-Fi/LAN.
   * Hiển thị trực tiếp địa chỉ link truy cập dạng `http://<IP_Của_Bạn>:8001/` ngay trên màn hình console để bạn dễ dàng chia sẻ cho người khác.
3. **Truy cập hệ thống**:
   * **Dashboard Giám Thị**: `http://<IP_Của_Bạn>:8001/`
   * **Trang Bài Thi Thí Sinh**: `http://<IP_Của_Bạn>:8001/exam` (Đăng nhập bằng SBD bất kỳ, ví dụ: `B202_1`).

---

### 🛠️ Cách 2: Cài Đặt và Chạy Thủ Công

#### 1. Tạo và kích hoạt môi trường ảo
```bash
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt trên Windows CMD
.venv\Scripts\activate.bat

# Kích hoạt trên Windows PowerShell
.venv\Scripts\Activate.ps1
```

#### 2. Cài đặt thư viện
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 3. Chạy Uvicorn Web Server
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

---

## 📸 Các Đối Tượng Được Nhận Diện & Trạng Thái

| Đối Tượng | Lớp Nhận Diện | Trạng Thái Vi Phạm |
| :--- | :---: | :---: |
| **Person** | Class 0 | Theo dõi vị trí và ID |
| **Cell Phone** | Class 67 (Custom 0) | 🚨 Critical (Sử dụng điện thoại) |
| **Book / Document**| Class 73 (Custom 1) | 🚨 Warning (Tài liệu trái phép) |
| **Casio Calculator**| Custom Class 2 | 🚨 Warning (Máy tính Casio) |

---

## 👨‍💻 Tác Giả & Bản Quyền

* Dự án được phát triển bởi **Huỳnh Châu Kiệt**.
* Phát triển phục vụ cho mục đích học tập, nghiên cứu khoa học và báo cáo đồ án tốt nghiệp.
