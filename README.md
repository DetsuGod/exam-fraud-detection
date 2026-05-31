# AI Exam Proctoring System - Hệ Thống Giám Sát Phòng Thi Thông Minh

Hệ thống giám sát phòng thi thông minh sử dụng mô hình học sâu **YOLOv8** và framework **FastAPI** để phát hiện các hành vi vi phạm quy chế thi cử theo thời gian thực từ webcam của thí sinh.

---

## 🚀 Hướng Dẫn Chạy Hệ Thống

Hệ thống hỗ trợ chạy tự động qua file script trên hệ điều hành Windows hoặc cài đặt thủ công.

### Cách 1: Chạy Tự Động (Khuyên Dùng trên Windows)
1. Kích đúp vào file **`run.bat`** tại thư mục gốc của dự án.
2. Script sẽ tự động thực hiện các bước:
   - Kiểm tra cài đặt Python.
   - Khởi tạo môi trường ảo Python (`.venv`) nếu chưa có.
   - Nâng cấp `pip` và tự động cài đặt toàn bộ thư viện cần thiết trong tệp `requirements.txt`.
   - Khởi động máy chủ Web Uvicorn tại địa chỉ: [http://127.0.0.1:8000](http://127.0.0.1:8000)
3. Mở trình duyệt Web và truy cập địa chỉ trên để sử dụng giao diện giám sát.

---

### Cách 2: Cài Đặt và Chạy Thủ Công (Mọi Hệ Điều Hành)
Nếu không chạy bằng `run.bat`, bạn có thể thực hiện tuần tự các lệnh sau trong terminal/cmd:

1. **Tạo môi trường ảo:**v
   ```bash
   python -m venv .venv
   ```

2. **Kích hoạt môi trường ảo:**
   * **Windows (cmd):** `.venv\Scripts\activate.bat`
   * **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
   * **Linux/macOS:** `source .venv/bin/activate`

3. **Cài đặt thư viện:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Chạy Uvicorn Web Server:**
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
5. Mở trình duyệt và truy cập: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🛠️ Các Chức Năng Chính Của Hệ Thống

Hệ thống cung cấp một bảng điều khiển giám sát trực quan (Premium Dashboard) với các tính năng vượt trội:

### 1. Phân Tích Luồng Video Thời Gian Thực (WebSocket Streaming)
- Thu nhận khung hình trực tiếp từ webcam của trình duyệt thí sinh, nén và truyền tải qua giao thức kết nối hai chiều **WebSocket** tốc độ cao.
- Máy chủ backend xử lý khung hình bằng YOLOv8 và gửi lại khung hình đã vẽ nhãn kèm theo dữ liệu phân tích chỉ số thời gian thực với độ trễ cực thấp.

### 2. Định Danh & Theo Dõi Thí Sinh (`id01`, `id02`,...)
- Tích hợp thuật toán theo dõi đối tượng **Centroid Tracker** tự phát triển ở backend.
- Tự động gán nhãn định danh duy nhất tăng dần cho từng thí sinh (`id01`, `id02`,...) dựa trên thứ tự xuất hiện của họ trong khung hình.
- Có khả năng duy trì định danh của thí sinh ngay cả khi bị che khuất tạm thời hoặc mất dấu trong khoảng thời gian ngắn (~2.5 giây).

### 3. Quản Lý Phiên Thi (Exam Session Control)
- Cung cấp nút **Bắt Đầu Phiên Thi** trên bảng điều khiển. Nút này chỉ khả dụng khi camera đang giám sát.
- Khi nhấn **Bắt Đầu Phiên Thi**: Hệ thống sẽ ghi nhận và khóa (lock) số lượng thí sinh hiện tại cùng vị trí tọa độ ban đầu của họ làm mốc tham chiếu giám sát.
- Khi kết thúc bài thi, nhấn **Kết Thúc Phiên Thi** để đưa hệ thống về trạng thái giám sát tự do.

### 4. Hệ Thống Phát Hiện Vi Phạm Thông Minh
Khi phiên thi đang hoạt động, hệ thống liên tục thực hiện các kiểm tra an ninh sau:
- **Thí sinh rời vị trí**: Cảnh báo ngay lập tức nếu thí sinh đã được khóa ban đầu biến mất khỏi khung hình.
- **Di chuyển khỏi ghế ngồi**: Tính toán khoảng cách dịch chuyển của thí sinh so với vị trí ban đầu khi khóa phiên. Nếu khoảng cách vượt ngưỡng an toàn **100 pixels**, hệ thống sẽ kích hoạt cảnh báo thí sinh rời vị trí ngồi làm bài.
- **Phát hiện người lạ/xâm nhập**: Cảnh báo tức thì nếu có bất kỳ người thứ hai/người lạ (`id` mới chưa được khóa ban đầu) xuất hiện trong khung hình.
- **Phát hiện vật dụng cấm**: Tự động nhận diện các vật thể cấm bao gồm **Điện thoại di động (Cell phone)**, **Sách/Tài liệu (Book)**, và **Laptop/Màn hình ngoài (Laptop)**.

### 5. Thống Kê & Chỉ Số Nghi Vấn (Suspicion Index)
- Tính toán chỉ số nghi vấn theo thời gian thực từ **0% đến 100%** dựa trên mức độ nghiêm trọng của hành vi vi phạm.
- Vẽ biểu đồ đường trực quan thể hiện biến thiên mức độ nghi vấn của thí sinh giúp giám thị dễ dàng xem lại lịch sử phiên thi.
- Cung cấp khung **Lịch Sử Vi Phạm (Logs)** hiển thị chi tiết thời gian và loại lỗi vi phạm được sắp xếp theo thời gian thực.

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
model/
│
├── app/
│   ├── templates/
│   │   └── index.html      # Giao diện giám sát Web Dashboard (HTML/CSS/JS)
│   └── main.py             # Backend API, WebSocket, CandidateTracker & YOLOv8
│
├── .venv/                  # Thư mục môi trường ảo Python (được tạo tự động)
├── requirements.txt        # Danh sách thư viện Python phụ thuộc
├── run.bat                 # Script chạy nhanh hệ thống trên Windows
├── yolov8n.pt              # File trọng số mô hình YOLOv8 Nano
└── README.md               # Tài liệu hướng dẫn sử dụng (tệp tin này)
```
