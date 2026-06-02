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
* **Tách biệt ảnh bằng chứng theo nguồn**:
  * Vi phạm từ **camera webcam** (điện thoại, nhìn lệch, v.v.) → lưu và hiển thị **ảnh webcam**.
  * Vi phạm từ **trang thi** (chuyển tab, copy, dừng chia sẻ) → lưu và hiển thị **ảnh chụp màn hình** thí sinh thật sự đang làm gì.
* **Bắt trọn 4 loại sự kiện vi phạm**:
  * `BLUR`: Chuyển tab hoặc nhấp chuột ra ngoài màn hình thi.
  * `VISIBILITY_CHANGE`: Ẩn màn hình làm bài thi (chuyển sang phần mềm khác).
  * `COPY_DETECTED`: Thí sinh thực hiện sao chép nội dung câu hỏi (`Ctrl + C`).
  * `SCREEN_SHARE_STOPPED`: Dừng chia sẻ màn hình làm bài thi (hệ thống lập tức khóa màn hình làm bài và yêu cầu kết nối lại).

### 3. Dashboard Giám Sát Thời Gian Thực
* **Màn hình kép trực tiếp**: Xem đồng thời webcam khuôn mặt (CAM: TRỰC DIỆN) và màn hình làm bài (MÀN HÌNH LÀM BÀI - SCREEN) của từng thí sinh.
* **Giữ nguyên frame màn hình cuối**: Khi tín hiệu chia sẻ màn hình không liên tục (gián đoạn), Dashboard giữ nguyên frame màn hình cuối thay vì chớp về màn hình trống.
* **Chỉ số nghi vấn (Suspicion Index)**: AI tự động tính và cập nhật chỉ số nghi vấn theo thời gian thực dựa trên tổng hợp nhiều hành vi.
* **Hiển thị cấu hình Blacklist từ khóa** cho cả hai chế độ Trắc Nghiệm và Thực Hành.
* **Kết nối lại tự động**: Khi thí sinh mất kết nối webcam hoặc chia sẻ màn hình, Dashboard hiển thị cảnh báo yêu cầu kết nối lại.

### 4. Nút Điều Khiển Phiên Thi & Khóa Trạng Thái 15 Giây
* **Nút kích hoạt toàn cục (Global Session Toggle)**: Nút bật/tắt phiên thi thiết kế neon động rực rỡ tại Header. AI chỉ ghi nhận log vi phạm và lưu bằng chứng khi phiên thi được BẬT.
* **Cơ chế Khóa trạng thái 15 giây (Status Lock)**: Khi xảy ra vi phạm từ trang thi, Dashboard sẽ khóa cứng thẻ trạng thái thí sinh trong **15 giây** để đảm bảo giám thị kịp phát hiện.

### 5. Tái Cấu Trúc Thư Mục LOG Phiên Thi Khoa Học
Khi bắt đầu phiên thi, hệ thống tự động tạo thư mục phiên thi mới dạng `LOG_phien/ngày... phiên.../` bên trong chứa sẵn 2 thư mục con theo từng thí sinh:
* **`Camera/`**: Lưu ảnh chụp bằng AI webcam khi thí sinh vi phạm trực diện (nhìn lệch, dùng điện thoại, v.v.).
* **`Exam/`**: Lưu ảnh chụp màn hình bài thi do React gửi về khi thí sinh chuyển tab, copy bài, dừng chia sẻ màn hình.

### 6. Cảnh Báo Phát Giọng Nói AI (Text-to-Speech)
Khi giám thị nhấp vào nút **"Cảnh cáo thoại"**, hệ thống tự động phát âm thanh cảnh báo bằng giọng nói tiếng Việt tự nhiên hướng thẳng đến thí sinh.

---

## 🧠 Công Nghệ Sử Dụng

| Công Nghệ | Vai Trò |
| :--- | :--- |
| **YOLOv8** (base + custom) | Nhận diện vật thể thông minh (Điện thoại, Sách, Máy tính Casio). |
| **Centroid Tracker** | Theo dõi, gán ID và giám sát chuyển vị trí của thí sinh thời gian thực. |
| **Haar Cascades** | Phân tích hướng quay đầu (Profile) và liếc mắt (Eye Glance). |
| **EasyOCR** | Nhận diện văn bản trong ảnh webcam để phát hiện tài liệu gian lận. |
| **FastAPI + WebSocket** | Backend máy chủ API & WebSocket tốc độ cao, xử lý đa luồng thí sinh. |
| **React JS + Vite** | Giao diện làm bài thi của thí sinh (`/exam`) mượt mà, bảo mật. |
| **Vanilla HTML/CSS/JS** | Giao diện Dashboard Admin Glassmorphism tối Neon cao cấp. |

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
exam-fraud-detection/
│
├── app/
│   ├── templates/
│   │   └── dashboard.html          # Giao diện chính của Giám thị
│   ├── main.py                     # API Server & WebSocket Handler
│   └── best.pt                     # ⚠️ KHÔNG có trên GitHub - cần copy thủ công
│
├── UI and module/
│   └── Exam screen/                # Dự án React JS làm bài thi của Thí sinh
│       ├── src/
│       │   ├── hooks/
│       │   │   └── useExamMonitor.js   # Hooks bắt sự kiện chuyển tab, copy
│       │   ├── pages/
│       │   │   ├── ExamPage.jsx        # Giao diện bài thi
│       │   │   └── AdminPage.jsx       # Giao diện quản lý
│       │   └── data/
│       │       └── examData.js         # Dữ liệu đề thi
│       └── dist/                   # ⚠️ KHÔNG có trên GitHub - cần build thủ công
│
├── LOG_phien/                      # Tự tạo khi chạy - lưu ảnh vi phạm
│   └── ngay_DD_thang_MM_nam_YYYY_phien_N/
│       └── <lop_hoc>/<student_id>/
│           ├── Camera/             # Ảnh webcam AI phát hiện vi phạm
│           └── Exam/               # Ảnh chụp màn hình vi phạm từ trang thi
│
├── yolov8n.pt                      # ⚠️ KHÔNG có trên GitHub - tự tải khi chạy lần đầu
├── requirements.txt                # Khai báo các thư viện Python
├── run.bat                         # File chạy tự động (localhost)
├── run_lan.bat                     # File chạy tự động (LAN)
└── README.md
```

---

## ⚙️ Hướng Dẫn Cài Đặt Sau Khi Clone

> **Lưu ý**: Các file model (`.pt`) và bản build frontend (`dist/`) **không có trên GitHub**. Cần thực hiện các bước bổ sung sau.

### Bước 1: Cài đặt thư viện Python

```bash
python -m venv .venv

# Windows CMD
.venv\Scripts\activate.bat

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt
```

> **Lưu ý**: `easyocr` sẽ tự tải thêm model OCR (~1GB) trong lần chạy đầu tiên. `yolov8n.pt` cũng sẽ tự tải (~6MB) nếu có kết nối internet.

### Bước 2: Copy file model custom

Copy file `best.pt` (được cung cấp riêng) vào thư mục:
```
exam-fraud-detection/app/best.pt
```

> Nếu không có `best.pt`, hệ thống vẫn chạy được nhưng chỉ dùng model YOLOv8 chuẩn — độ chính xác nhận diện điện thoại/sách sẽ thấp hơn.

### Bước 3: Build Frontend (Trang thi thí sinh)

```bash
cd "UI and module/Exam screen"
npm install
npm run build
```

Lệnh này tạo ra thư mục `dist/` mà FastAPI dùng để phục vụ trang thi tại `/exam`.

### Bước 4: Khởi động hệ thống

```bash
# Chạy nội bộ (localhost)
run.bat

# Hoặc chạy trong mạng LAN
run_lan.bat

# Hoặc thủ công
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

**Truy cập:**
* 🖥️ **Dashboard Giám Thị**: `http://127.0.0.1:8001/`
* 📝 **Trang Bài Thi Thí Sinh**: `http://127.0.0.1:8001/exam`
* 🌐 **Chạy LAN**: `http://<IP_Của_Bạn>:8001/exam`

---

## 📸 Các Đối Tượng Được Nhận Diện & Trạng Thái

| Đối Tượng | Model | Class ID | Mức Độ Vi Phạm |
| :--- | :---: | :---: | :---: |
| **Cell Phone** | Base + Custom | 67 / Custom 0 | 🔴 Critical |
| **Book / Document** | Base + Custom | 73 / Custom 1 | 🟡 Warning |
| **Casio Calculator** | Custom | Custom 2 | 🟡 Warning |
| **Quay đầu** | Haar Cascade | — | 🟡 Warning |
| **Liếc mắt** | Haar Cascade | — | 🟡 Warning |
| **Rời khỏi khung hình** | Tracking | — | 🔴 Critical |
| **Chuyển tab / Ẩn màn hình** | React Hook | — | 🔴 Critical |
| **Copy nội dung** | React Hook | — | 🟡 Warning |
| **Dừng chia sẻ màn hình** | React Hook | — | 🔴 Critical |

---

## 👨‍💻 Tác Giả & Bản Quyền

* Dự án được phát triển bởi **Huỳnh Châu Kiệt**.
* Phát triển phục vụ cho mục đích học tập, nghiên cứu khoa học và báo cáo đồ án tốt nghiệp.
