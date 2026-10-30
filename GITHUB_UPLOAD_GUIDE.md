# Đưa ANCARAT Image SKU Processor V3 lên GitHub

## Trước khi công bố

- [ ] Đã xác nhận quyền đưa mã nguồn thuộc dự án ANCARAT lên tài khoản/tổ chức GitHub dự định sử dụng.
- [ ] Đã quyết định kho **Private** hay **Public**. Nếu chưa chắc về quyền công bố, hãy dùng **Private**.
- [ ] Không bao gồm ảnh sản phẩm thật, payload QR thật, file `.sku_processor_manifest.json` hoặc `du_lieu_qr.txt` từ dữ liệu vận hành.
- [ ] Đã xem `README.md`, `SECURITY.md`, `CHANGELOG.md` và chạy kiểm thử thành công.
- [ ] Nếu muốn cho cộng đồng sao chép/sửa đổi/phân phối mã, hãy xác nhận giấy phép với chủ sở hữu và thêm file `LICENSE` phù hợp.

## Cách 1 — GitHub Desktop (dễ nhất trên Windows)

1. Giải nén `ANCARAT_IMAGE_SKU_PROCESSOR_V3_GITHUB_READY.zip`.
2. Mở [GitHub Desktop](https://desktop.github.com/) và đăng nhập.
3. Chọn **File → Add local repository → Choose...** và trỏ đến thư mục đã giải nén. Nếu ứng dụng báo chưa phải Git repository, chọn **Create a Repository** tại thư mục đó.
4. Nhập tên repository gợi ý: `ancarat-image-sku-processor`.
5. Kiểm tra danh sách file. Không đưa dữ liệu sản phẩm thật hay output vào commit.
6. Commit: `Initial release: ANCARAT Image SKU Processor V3`.
7. Chọn **Publish repository**, xác nhận quyền truy cập **Private** hoặc **Public** đúng với chính sách tổ chức.

## Cách 2 — Git CLI

Tạo một repository trống trên GitHub trước (không tạo README/.gitignore mẫu vì các file này đã có). Mở terminal trong thư mục đã giải nén:

```bash
git init
git add .
git commit -m "Initial release: ANCARAT Image SKU Processor V3"
git branch -M main
git remote add origin https://github.com/USERNAME/ancarat-image-sku-processor.git
git push -u origin main
```

Đổi `USERNAME` thành tên tài khoản hoặc tổ chức GitHub; đăng nhập theo hướng dẫn của Git khi đẩy lên.

## Cách 3 — Upload trực tiếp trên website GitHub

1. Tạo repository trống.
2. Chọn **Add file → Upload files**.
3. **Giải nén ZIP trước khi tải lên**; repository cần chứa `app.py`, `tests/`, `.github/workflows/`, v.v. dưới dạng file/thư mục, không phải chỉ một tệp ZIP.
4. Kiểm tra các file ẩn `.gitignore`, `.gitattributes` và thư mục `.github` đã được upload đầy đủ; trình duyệt có thể xử lý kéo-thả thư mục khác nhau.
5. Commit các file lên nhánh `main`.

## Kiểm tra sau khi đưa lên

- Tab **Code** hiển thị `README.md` và cây thư mục rõ ràng.
- Tab **Actions** chạy workflow `Python tests` màu xanh (CI kiểm tra Python 3.11/3.12 trên Windows và Ubuntu).
- Tải thử **Code → Download ZIP** và chạy `CHAY_TREN_WINDOWS.bat` trên máy Windows có Python.
- Không có dữ liệu ảnh sản phẩm, đường dẫn thật hoặc thông tin nhạy cảm.

### Gợi ý phần giới thiệu repository

**Description:** `Offline Windows tool for product SKU recognition from filenames and QR codes, safe batch image renaming, and QR metadata export.`

**Topics:** `python`, `opencv`, `numpy`, `qr-code`, `batch-processing`, `image-processing`, `windows`, `offline-tool`

**Release tag:** `v3.0.1` (bản V3 đã đóng gói và bổ sung bản vá an toàn cục bộ).
