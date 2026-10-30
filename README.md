# ANCARAT Image SKU Processor V3

**Ứng dụng web chạy cục bộ giúp nhận diện SKU từ tên file hoặc mã QR, đổi tên ảnh sản phẩm hàng loạt và xuất dữ liệu QR — không cần AI, OCR, máy chủ bên ngoài hay kết nối Internet trong lúc xử lý.**

**Phiên bản:** `3.0.1` (V3 + bản đóng gói GitHub) · **Ngôn ngữ:** Python 3.10+ · **Nền tảng ưu tiên:** Windows 10/11 · [English README](README.en.md)

## Tính năng

- **Ưu tiên tên file:** phát hiện SKU chính xác hoặc SKU có hậu tố như `_final`, `(copy)`; không giải mã QR nếu tên file đã đủ tin cậy.
- **Quét QR khi cần:** OpenCV `QRCodeDetector`, tùy chọn quét nâng cao gồm xoay ảnh 90°/180°/270°, chỉnh phối cảnh, tăng tương phản, giải mã dự phòng qua `pyzbar`/ZBar.
- **Cấu hình tiền tố bỏ qua:** `AMI` mặc định không được xem là SKU từ tên ảnh; dữ liệu QR bên trong vẫn được xử lý.
- **SKU đặc biệt:** hỗ trợ quy tắc như `TMV.C001C`, `MDTP.13`, `VDD-01` và SKU chứa chữ/số thông thường.
- **Xuất ảnh an toàn:** sao chép giữ nguyên byte và phần mở rộng, đặt tên `SKU (1).jpg`, `SKU (2).png`...; không sửa hay xóa ảnh gốc.
- **Chạy lại an toàn:** manifest ngăn sao chép lại những nhóm không đổi, giữ tên đã xuất và không ghi đè ảnh hiện có.
- **Báo cáo dễ kiểm tra:** số nhóm thành công/lỗi, danh sách lỗi và file `du_lieu_qr.txt` UTF-8 BOM.
- **Chạy offline:** giao diện HTML/CSS/JS thuần với HTTP server thuộc thư viện chuẩn Python, chỉ lắng nghe `127.0.0.1:5050`.

> **Phạm vi:** Đây là hệ thống đọc QR/nhận SKU, **không phải** AI nhận diện vật thể hoặc hệ thống đánh giá độ giống nhau giữa hai hình ảnh.

## Bắt đầu trên Windows

1. Cài **Python 3.10 trở lên** từ [python.org](https://www.python.org/downloads/), bật **Add Python to PATH** khi cài.
2. Tải ZIP của repository này, giải nén vào thư mục không bị giới hạn quyền ghi.
3. Nhấp đúp **`CHAY_TREN_WINDOWS.bat`**. Lần chạy đầu sẽ tự tạo `.venv` riêng và cài phụ thuộc (cần Internet một lần).
4. Trình duyệt thường tự mở, hoặc truy cập **http://127.0.0.1:5050**.
5. Nhập đường dẫn thư mục **nguồn** và **đích**, giữ `AMI` trong danh sách tiền tố bỏ qua nếu ảnh có tên dạng `AMI07927.JPG`, sau đó bấm **BẮT ĐẦU XỬ LÝ**.

Ví dụ nguồn:

```text
D:\ANH_SAN_PHAM\
  SAN_PHAM_001\
    IMG_001.jpg
    G3SMD00M0660038.jpg
  SAN_PHAM_002\
    AMI07927.JPG
    IMG_002.png
```

Ví dụ kết quả (tên ở nhóm thứ hai phụ thuộc SKU đọc được trong QR thực tế):

```text
D:\ANH_DA_XU_LY\
  G3SMD00M0660038 (1).jpg
  G3SMD00M0660038 (2).jpg
  G75D1ZTD1680009 (1).JPG
  G75D1ZTD1680009 (2).png
  du_lieu_qr.txt
  .sku_processor_manifest.json
```

Đầu ra `du_lieu_qr.txt` chứa một dòng cho mỗi nhóm ảnh đã xử lý: `SKU|NOI_DUNG_QR`. Nếu SKU lấy từ tên file, phần sau `|` để trống. File manifest ẩn theo dõi file đã xuất; **đừng xóa nếu muốn chạy tiếp vào cùng thư mục đích**.

## Cài thủ công / phát triển

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Linux / macOS:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

**Linux cần ZBar** trước khi dùng `pyzbar`, ví dụ Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y libzbar0
```

Trên macOS, có thể cài ZBar bằng Homebrew (`brew install zbar`). Hệ thống ưu tiên Windows; các nền tảng khác cần kiểm thử theo môi trường cụ thể.

Để chạy kiểm thử:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Cách hoạt động

```text
Thư mục nguồn
   │
   ├─ Duyệt đệ quy những thư mục lá có ảnh
   │
   ├─ Tìm SKU hợp lệ trong tên file
   │    ├─ Có SKU → kiểm tra xung đột → xuất
   │    └─ Không có → đọc QR thông thường
   │                   └─ Thất bại → thử xử lý nâng cao (nếu bật)
   │
   ├─ Kiểm tra manifest / tên file đã có
   ├─ Copy ảnh, giữ nguyên định dạng và metadata
   └─ Đồng bộ du_lieu_qr.txt
```

**Stack:** Python standard library (`http.server`, `pathlib`, `shutil`, `json`, `re`) + OpenCV + NumPy + pyzbar. Không sử dụng Flask, React, dịch vụ cloud hoặc API ngoài.

## Cấu trúc repository

```text
ancarat-image-sku-processor/
├── app.py                          # Backend, thuật toán, và UI local
├── requirements.txt                # Phụ thuộc khi chạy
├── requirements-dev.txt            # Công cụ kiểm thử
├── CHAY_TREN_WINDOWS.bat           # Tạo venv, cài và chạy trên Windows
├── HUONG_DAN.txt                   # Hướng dẫn ngắn gọn
├── tests/
│   └── test_app.py                 # Unit tests và integration tests
├── .github/workflows/tests.yml     # CI trên Windows và Ubuntu
├── .gitignore
├── .gitattributes
├── README.md
├── README.en.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── GITHUB_UPLOAD_GUIDE.md
└── SECURITY.md
```

## Giới hạn & nguyên tắc an toàn

- **Không xác thực sản phẩm bằng hình dạng:** nếu nhãn file bị đặt sai nhưng trông như một SKU hợp lệ, hệ thống có thể chọn nhãn đó; không xác minh QR nữa trong trường hợp tên file đủ tin cậy.
- **Một thư mục lá tương ứng một sản phẩm:** không trộn ảnh nhiều sản phẩm vào cùng thư mục.
- **Không phải công cụ kiểm tra ảnh hỏng tổng quát:** nếu lấy SKU trực tiếp từ tên file, chương trình có thể sao chép ảnh bị lỗi dữ liệu mà không mở giải mã ảnh.
- Nếu ảnh đã xuất thay đổi, chương trình sẽ cảnh báo thay vì ghi đè; hãy dùng thư mục đích khác nếu muốn xuất một phiên bản mới.
- Nếu đã dùng V1/V2 và từng nhận nhầm `AMI` thành SKU, nên dùng **thư mục đích mới** để chạy lại với V3.
- Chương trình chỉ lắng nghe loopback, từ chối yêu cầu POST không phải JSON / trình duyệt nguồn ngoài localhost; **không mở cổng 5050 ra Internet**.
- **Không đăng ảnh sản phẩm nội bộ, dữ liệu QR thực, thông tin khách hàng hoặc manifest từ máy làm việc lên repository công khai.**

## Kiểm thử và đóng góp

Bộ kiểm thử kiểm tra nhận dạng SKU, xử lý tên AMI, SKU chứa dấu chấm, QR tổng hợp, nhiều thư mục trùng SKU, xung đột mã, chạy lại không trùng, và an toàn HTTP localhost. CI chạy trên Windows và Ubuntu với Python 3.11/3.12. Xem [CONTRIBUTING.md](CONTRIBUTING.md) và [CHANGELOG.md](CHANGELOG.md).

## Đưa mã nguồn lên GitHub

Hướng dẫn đầy đủ: [GITHUB_UPLOAD_GUIDE.md](GITHUB_UPLOAD_GUIDE.md). Cách đơn giản: tạo repository trống trên GitHub, giải nén gói ZIP và dùng **GitHub Desktop** để tạo commit và **Publish repository**. Nếu dùng Git CLI (sau khi tạo repository trống):

```bash
git init
git add .
git commit -m "Initial release - ANCARAT Image SKU Processor V3"
git branch -M main
git remote add origin https://github.com/USERNAME/ancarat-image-sku-processor.git
git push -u origin main
```

Thay `USERNAME` bằng tài khoản hoặc tổ chức GitHub của bạn. Kiểm tra quyền công bố mã nguồn trước khi chọn repository **Public**.

**Bản đóng gói này chưa kèm LICENSE:** việc đẩy lên GitHub không tự động cho phép bên thứ ba sử dụng hoặc phân phối lại mã nguồn. Chủ sở hữu nên xác nhận quyền sở hữu và lựa chọn giấy phép phù hợp trước khi công bố công khai.
