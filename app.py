# -*- coding: utf-8 -*-
"""ANCARAT - IMAGE SKU PROCESSOR V3 | Local web app, Python 3.10+.

No AI, OCR, database, external APIs, or web framework required.
OpenCV is the primary QR reader; pyzbar is an offline fallback for difficult QR.
"""

import json
import os
import re
import shutil
import tempfile
import threading
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

try:
    # Gói pyzbar cho Windows có sẵn thư viện ZBar trong wheel.
    from pyzbar.pyzbar import decode as zbar_decode, ZBarSymbol
except (ImportError, OSError):
    zbar_decode = None
    ZBarSymbol = None

HOST = "127.0.0.1"  # Chỉ cho phép truy cập trên máy đang chạy ứng dụng.
PORT = 5050
APP_VERSION = "3.0.1"  # GitHub release: original V3 + local HTTP protections and tests.
SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
UNSUPPORTED_IMAGES = {
    ".gif", ".heic", ".heif", ".avif", ".raw", ".cr2", ".nef",
    ".dng", ".psd", ".svg", ".jp2", ".jfif", ".arw", ".raf",
}
MANIFEST_NAME = ".sku_processor_manifest.json"
QR_TXT_NAME = "du_lieu_qr.txt"
# Có thể sửa danh sách này trên giao diện; không cần thay đổi mã nguồn.
DEFAULT_IGNORE_FILENAME_PREFIXES = "AMI"

# Có thể thêm mẫu SKU chứa dấu chấm (hay dạng đặc biệt) tại đây.
# Mỗi Regex chỉ khớp chính SKU, không khớp phần thông tin QR đằng sau.
SPECIAL_SKU_PATTERNS = [
    re.compile(r"TMV\.[A-Z0-9]+", re.IGNORECASE),
    re.compile(r"MDTP\.\d+", re.IGNORECASE),
]

# Các tiền tố ảnh chụp thông thường; không xem là SKU dù có chữ và số.
CAMERA_NAME = re.compile(
    r"^(?:IMG|DSC|DSCF|DSCN|PXL|IMAGE|PHOTO|PHOTOGRAPH|PIC|PICT|"
    r"SCREENSHOT|SCREEN|CAM|CAMERA|VID|VIDEO|FILE|ZALO|DCIM)[-_ .]?\d+(?:[-.]\d+)*$",
    re.IGNORECASE,
)
CAMERA_PREFIX = re.compile(
    r"^(?:IMG|DSC|DSCF|DSCN|PXL|IMAGE|PHOTO|PIC|PICT|SCREENSHOT|"
    r"SCREEN|CAMERA|VID|VIDEO|FILE|ZALO|DCIM)[-_]?\d",
    re.IGNORECASE,
)
SKU_SHAPE = re.compile(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*\Z")
LEADING_TOKEN = re.compile(r"^[A-Z0-9]+(?:[.-][A-Z0-9]+)*", re.IGNORECASE)
PHOTO_NOTE = re.compile(
    r"[-.](?:FINAL|COPY|EDIT|NEW|MOI|ANH|HINH|ANHMOI|HINHMOI|HINHCHINH|"
    r"CHINH|MOI2|PHOTO|IMAGE|BANMOI|DA-SUA)$",
    re.IGNORECASE,
)
PROCESS_LOCK = threading.Lock()


def natural_key(value):
    """Sắp xếp tên theo thứ tự tự nhiên: 1, 2, 10 thay vì 1, 10, 2."""
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r"(\d+)", str(value))]


def valid_sku(value):
    """Chỉ nhận chữ/số với . và - ở giữa; chống nhận nhầm tên ảnh."""
    code = value.strip().upper()
    if not SKU_SHAPE.fullmatch(code):
        return False
    if not re.search(r"[A-Z]", code) or not re.search(r"\d", code):
        return False
    if CAMERA_NAME.fullmatch(code) or CAMERA_PREFIX.match(code):
        return False
    if re.fullmatch(r"(?:19|20)\d{2}[A-Z]{3}", code):
        return False
    if PHOTO_NOTE.search(code):
        return False
    return True


def ignored_prefixes(raw):
    """Danh sách tiền tố KHÔNG được lấy SKU từ tên file (không ảnh hưởng SKU trong QR)."""
    if raw is None:
        raw = DEFAULT_IGNORE_FILENAME_PREFIXES
    if not isinstance(raw, str) or len(raw) > 500:
        raise ValueError("Danh sách tiền tố bỏ qua phải là chuỗi tối đa 500 ký tự.")
    prefixes = []
    for part in re.split(r"[,;\n\r]+", raw):
        prefix = part.strip().upper()
        if not prefix:
            continue
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,31}", prefix):
            raise ValueError(
                "Tiền tố không hợp lệ: " + repr(prefix) +
                ". Chỉ dùng chữ, số, dấu chấm, gạch ngang, gạch dưới (tối đa 32 ký tự)."
            )
        if prefix not in prefixes:
            prefixes.append(prefix)
    if len(prefixes) > 50:
        raise ValueError("Chỉ nhập tối đa 50 tiền tố cần bỏ qua.")
    return tuple(sorted(prefixes))


def filename_sku(stem, skip_prefixes=()):
    """Trả về SKU từ tên file hoặc None; tên có tiền tố bỏ qua được chuyển sang QR."""
    name = stem.strip().upper()
    if any(name.startswith(prefix) for prefix in skip_prefixes):
        return None

    # SKU có dấu chấm + hậu tố ghi chú: TMV.C001C_hinhchinh.
    for pattern in SPECIAL_SKU_PATTERNS:
        match = pattern.match(name)
        if match and match.end() < len(name) and name[match.end()] in " _(. -":
            code = match.group(0).upper()
            if valid_sku(code):
                return code, "decorated"

    if valid_sku(name):
        return name, "exact"

    match = LEADING_TOKEN.match(name)
    if not match:
        return None
    code = match.group(0)
    while True:
        cleaned = PHOTO_NOTE.sub("", code)
        if cleaned == code:
            break
        code = cleaned
    if not valid_sku(code):
        return None
    if len(name) > len(code) and name[len(code)] not in " _(. -":
        return None
    return code, ("exact" if code == name else "decorated")


def qr_sku(raw):
    """Đọc SKU ở đầu nội dung QR, ưu tiên các SKU chứa dấu chấm."""
    value = raw.strip().lstrip("\ufeff").upper()
    if not value:
        return None
    for pattern in SPECIAL_SKU_PATTERNS:
        match = pattern.match(value)
        if match and (match.end() == len(value) or value[match.end()] in ". |\r\n\t"):
            code = match.group(0).upper()
            if valid_sku(code):
                return code
    candidate = re.split(r"[.|\r\n]", value, maxsplit=1)[0].strip()
    return candidate if valid_sku(candidate) else None


def decode_opencv(image, detector):
    """OpenCV trả về cả tọa độ QR kể cả khi chưa giải mã được nội dung."""
    try:
        value, corners, _ = detector.detectAndDecode(image)
        return (value or ""), corners
    except (cv2.error, ValueError):
        return "", None


def decode_zbar(image):
    """Dùng ZBar offline khi OpenCV không đọc được; chỉ chấp nhận QR."""
    if zbar_decode is None:
        return ""
    try:
        matches = zbar_decode(image, symbols=[ZBarSymbol.QRCODE])
    except (OSError, ValueError, RuntimeError, TypeError):
        return ""
    for match in matches:
        try:
            content = match.data.decode("utf-8-sig")
            if content.strip():
                return content
        except UnicodeDecodeError:
            continue
    return ""


def decode_rectified_qr(image, corners, detector):
    """Sửa phối cảnh từ bốn góc QR, nâng tương phản và tạo viền trắng."""
    try:
        points = np.asarray(corners, dtype=np.float32).reshape(-1, 2)
        if points.shape != (4, 2):
            return ""
        if not np.isfinite(points).all():
            return ""
        # Ảnh tem thông thường có QR nhỏ, nên warp 256 px tránh quá ít điểm ảnh.
        size = 256
        target = np.float32([[0, 0], [size, 0], [size, size], [0, size]])
        transform = cv2.getPerspectiveTransform(points, target)
        square = cv2.warpPerspective(
            image, transform, (size, size),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        )
        gray = cv2.cvtColor(square, cv2.COLOR_BGR2GRAY)
        threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        # Trong ảnh thực tế AMI07927.JPG, phép warp + Otsu + ZBar đọc được QR.
        variants = (gray, threshold)
        for variant in variants:
            padded = cv2.copyMakeBorder(
                variant, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255
            )
            value = decode_zbar(padded)
            if value:
                return value
            value, _ = decode_opencv(padded, detector)
            if value:
                return value

        # Chỉ thử bổ sung khi các cách nhanh ở trên chưa thành công.
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
        )
        for variant in (clahe, adaptive):
            padded = cv2.copyMakeBorder(
                variant, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255
            )
            value = decode_zbar(padded)
            if value:
                return value
            value, _ = decode_opencv(padded, detector)
            if value:
                return value
    except (cv2.error, ValueError, OverflowError, TypeError):
        pass
    return ""


def read_qr(path, detector, advanced=True):
    """Trả về (nội dung, lỗi đọc file, đã phát hiện QR).

    Nhận đường dẫn Unicode Windows; không thay đổi ảnh gốc. Quét nâng cao chỉ
    được kích hoạt khi quét trực tiếp không tìm ra dữ liệu.
    """
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return "", "Ảnh rỗng hoặc bị hỏng", False
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            return "", "Không mở được dữ liệu ảnh", False
        decoded, corners = decode_opencv(image, detector)
        seen = corners is not None
        if decoded:
            return decoded, "", True
        if not advanced:
            return "", "", seen

        # Dùng ZBar toàn ảnh trước, sau đó thử các hướng xoay chỉ khi cần.
        decoded = decode_zbar(image)
        if decoded:
            return decoded, "", True
        turns = (
            cv2.ROTATE_90_CLOCKWISE,
            cv2.ROTATE_180,
            cv2.ROTATE_90_COUNTERCLOCKWISE,
        )
        # Trường hợp gốc thấy QR nhưng đọc không được: sửa phối cảnh ngay.
        if corners is not None:
            decoded = decode_rectified_qr(image, corners, detector)
            if decoded:
                return decoded, "", True
        for turn in turns:
            rotated = cv2.rotate(image, turn)
            decoded, corners = decode_opencv(rotated, detector)
            seen = seen or corners is not None
            if decoded:
                return decoded, "", True
            decoded = decode_zbar(rotated)
            if decoded:
                return decoded, "", True
            if corners is not None:
                decoded = decode_rectified_qr(rotated, corners, detector)
                if decoded:
                    return decoded, "", True
        return "", "", seen
    except (OSError, ValueError, cv2.error, MemoryError) as error:
        return "", "Không đọc được ảnh: " + str(error)[:140], False


def qr_escape(value):
    """Mỗi QR vẫn ở đúng một dòng và không phá dấu | phân tách."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", "\\r").replace("\n", "\\n")


def atomic_write(path, text, encoding="utf-8"):
    """Không để mất file JSON/TXT cũ khi ghi bị lỗi giữa chừng."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding=encoding, newline="\n", delete=False,
            dir=str(path.parent), prefix=".sku_tmp_", suffix=".tmp",
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def load_manifest(folder):
    path = folder / MANIFEST_NAME
    if not path.exists():
        return {"version": 1, "groups": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value.get("version") != 1 or not isinstance(value.get("groups"), dict)):
            raise ValueError("Cấu trúc manifest không đúng")
        for group_path, group in value["groups"].items():
            if (not isinstance(group_path, str) or not isinstance(group, dict)
                    or not isinstance(group.get("sku"), str)
                    or not isinstance(group.get("qr", ""), str)
                    or not isinstance(group.get("files"), dict)):
                raise ValueError("Có một nhóm dữ liệu manifest không hợp lệ")
            for original_name, item in group["files"].items():
                if (not isinstance(original_name, str) or not isinstance(item, dict)
                        or not isinstance(item.get("dest"), str)
                        or Path(item["dest"]).name != item["dest"]
                        or not isinstance(item.get("size"), int)
                        or not isinstance(item.get("mtime_ns"), int)):
                    raise ValueError("Có tên hoặc thông tin file trong manifest không hợp lệ")
        return value
    except (OSError, ValueError, AttributeError) as error:
        raise ValueError(
            "Không đọc được file nhật ký xử lý " + MANIFEST_NAME + ". "
            "Hãy khôi phục file hợp lệ hoặc chọn thư mục đích khác. " + str(error)
        ) from error


def save_manifest(folder, manifest):
    atomic_write(
        folder / MANIFEST_NAME,
        json.dumps(manifest, ensure_ascii=False, indent=2),
    )


def sync_qr_txt(folder, manifest):
    """Đồng bộ TXT theo số nhóm trong manifest; chạy lại không tạo dòng trùng."""
    path = folder / QR_TXT_NAME
    if path.exists():
        old = path.read_text(encoding="utf-8-sig")
        lines = [line for line in old.splitlines() if line]
    else:
        old, lines = "", []

    desired = []
    for entry in manifest["groups"].values():
        if isinstance(entry, dict) and entry.get("sku"):
            desired.append(entry["sku"] + "|" + qr_escape(entry.get("qr", "")))

    # Tránh giữ dòng dữ liệu QR cũ nếu đổi quy tắc quét lại cùng một SKU.
    # Giữ nguyên các dòng của SKU không nằm trong manifest (không xoá dữ liệu ngoài ứng dụng).
    active_skus = {entry["sku"] for entry in manifest["groups"].values() if entry.get("sku")}
    remaining = Counter(desired)
    merged = []
    for line in lines:
        sku = line.split("|", 1)[0]
        if sku not in active_skus:
            merged.append(line)
        elif remaining[line] > 0:
            merged.append(line)
            remaining[line] -= 1
    for line in desired:
        if remaining[line] > 0:
            merged.append(line)
            remaining[line] -= 1

    new_text = "\n".join(merged) + ("\n" if merged else "")
    # Cũng chuẩn hóa sang UTF-8 có BOM nếu file cũ chưa có BOM.
    if not path.exists() or old != new_text or not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        atomic_write(path, new_text, encoding="utf-8-sig")


def exclusive_copy(source, destination):
    """Copy từng byte, giữ metadata và tuyệt đối không ghi đè tệp đã tồn tại."""
    created = False
    try:
        with source.open("rb") as source_handle:
            with destination.open("xb") as dest_handle:
                created = True
                shutil.copyfileobj(source_handle, dest_handle, length=1024 * 1024)
        shutil.copystat(source, destination)
    except Exception:
        if created:
            try:
                destination.unlink()
            except OSError:
                pass
        raise


def leaf_groups(root, traversal_errors):
    """Chỉ duyệt thư mục lá, không phân tích tên thư mục tháng/ngày."""
    def on_error(error):
        traversal_errors.append({
            "folder": str(getattr(error, "filename", root)),
            "reason": "Không truy cập được thư mục: " + str(error),
        })

    for folder, dirs, files in os.walk(root, topdown=True, onerror=on_error, followlinks=False):
        dirs[:] = sorted((name for name in dirs if not (Path(folder) / name).is_symlink()),
                         key=natural_key)
        if dirs:
            continue
        images = sorted(
            (Path(folder) / name for name in files if Path(name).suffix.lower() in SUPPORTED_IMAGES),
            key=lambda path: natural_key(path.name),
        )
        unsupported = sorted(
            (name for name in files if Path(name).suffix.lower() in UNSUPPORTED_IMAGES),
            key=natural_key,
        )
        if images or unsupported:
            yield Path(folder), images, unsupported


def file_metadata(path):
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def exported_file_present(folder, metadata):
    """Kiểm tra bản đã xuất còn tồn tại và có đúng số byte ban đầu."""
    try:
        output_path = folder / metadata["dest"]
        return output_path.is_file() and output_path.stat().st_size == metadata["size"]
    except (OSError, KeyError, TypeError):
        return False


def summary_error(result, folder, reason):
    result["error_groups"] += 1
    result["errors"].append({"folder": str(folder), "reason": reason})


def process_folders(source_string, destination_string, skip_filename_prefixes=None, advanced_qr=True):
    """Xử lý ảnh; tiền tố trong ô cấu hình không được xem là SKU từ tên file."""
    skip_prefixes = ignored_prefixes(skip_filename_prefixes)
    if not isinstance(advanced_qr, bool):
        raise ValueError("Tùy chọn quét QR nâng cao phải là bật hoặc tắt.")
    rule_snapshot = list(skip_prefixes)
    if not isinstance(source_string, str) or not isinstance(destination_string, str):
        raise ValueError("Vui lòng nhập đầy đủ đường dẫn nguồn và đích.")
    original_source = source_string.strip().strip('"')
    original_destination = destination_string.strip().strip('"')
    if not original_source or not original_destination:
        raise ValueError("Vui lòng nhập đầy đủ đường dẫn nguồn và đích.")

    source = Path(os.path.expandvars(original_source)).expanduser().resolve()
    destination = Path(os.path.expandvars(original_destination)).expanduser().resolve()
    if not source.is_dir():
        raise ValueError("Thư mục nguồn không tồn tại hoặc không thể truy cập: " + str(source))
    if destination == source or source in destination.parents:
        raise ValueError("Thư mục đích phải nằm ngoài thư mục nguồn để không quét lặp ảnh.")
    if destination.exists() and not destination.is_dir():
        raise ValueError("Đường dẫn đích đang trỏ đến một file, không phải thư mục.")
    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ValueError("Không thể tạo thư mục đích: " + str(error)) from error

    manifest = load_manifest(destination)
    # Kiểm tra khả năng đọc TXT trước khi bắt đầu copy để hạn chế tình trạng dở dang.
    txt_path = destination / QR_TXT_NAME
    if txt_path.exists():
        try:
            txt_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            raise ValueError("Không đọc được " + QR_TXT_NAME + ": " + str(error)) from error

    result = {
        "total_groups": 0, "successful_groups": 0, "copied_images": 0,
        "filename_groups": 0, "qr_groups": 0, "error_groups": 0,
        "skipped_images": 0, "errors": [], "output": str(destination),
    }
    # Chỉ duyệt danh sách file đầu ra một lần để tốc độ không giảm khi ảnh nhiều.
    existing_names = set()
    counters = {}
    output_name = re.compile(r"^(.*?) \((\d+)\)$")
    try:
        for entry in destination.iterdir():
            if not entry.is_file():
                continue
            existing_names.add(entry.name.casefold())
            match = output_name.fullmatch(entry.stem)
            if match and entry.suffix.lower() in SUPPORTED_IMAGES:
                sku = match.group(1).upper()
                counters[sku] = max(counters.get(sku, 0), int(match.group(2)))
    except OSError as error:
        raise ValueError("Không thể đọc thư mục đích: " + str(error)) from error

    detector = None  # Chỉ khởi tạo OpenCV QR khi thực sự cần.
    traversal_errors = []
    for folder, images, unsupported in leaf_groups(source, traversal_errors):
        result["total_groups"] += 1
        folder_key = str(folder.resolve()).casefold()

        if unsupported:
            summary_error(result, folder, "Định dạng ảnh chưa hỗ trợ: " + ", ".join(unsupported[:12]))
            continue
        if not images:
            continue

        try:
            current = {path.name: file_metadata(path) for path in images}
        except OSError as error:
            summary_error(result, folder, "Không đọc được thông tin file ảnh: " + str(error))
            continue

        previous = manifest["groups"].get(folder_key)
        if previous is not None and not isinstance(previous.get("files"), dict):
            summary_error(result, folder, "Manifest chứa thông tin nhóm ảnh không hợp lệ.")
            continue

        # Lượt chạy lại: nhóm không đổi, không cần giải mã QR hay copy bất kỳ ảnh nào.
        if previous and previous.get("ignored_filename_prefixes") == rule_snapshot and all(
            previous["files"].get(path.name, {}).get("size") == current[path.name]["size"]
            and previous["files"].get(path.name, {}).get("mtime_ns") == current[path.name]["mtime_ns"]
            and exported_file_present(destination, previous["files"].get(path.name, {}))
            for path in images
        ) and len(previous["files"]) == len(images):
            result["successful_groups"] += 1
            result["skipped_images"] += len(images)
            result["filename_groups" if previous.get("source") == "filename" else "qr_groups"] += 1
            continue

        candidates = set()
        for image in images:
            extracted = filename_sku(image.stem, skip_prefixes)
            if extracted:
                candidates.add(extracted[0])
        if len(candidates) > 1:
            summary_error(result, folder, "Phát hiện nhiều SKU xung đột: " + ", ".join(sorted(candidates)))
            continue

        qr_raw, method = "", "filename"
        if candidates:
            sku = next(iter(candidates))
        else:
            method = "qr"
            sku = None
            if detector is None:
                detector = cv2.QRCodeDetector()
            invalid_images, found_qr_but_invalid, seen_undecoded = [], False, False
            for image in images:
                decoded, read_error, saw_qr = read_qr(image, detector, advanced=advanced_qr)
                if read_error:
                    invalid_images.append(image.name)
                if saw_qr and not decoded:
                    seen_undecoded = True
                if decoded:
                    candidate = qr_sku(decoded)
                    if candidate:
                        sku, qr_raw = candidate, decoded
                        break
                    found_qr_but_invalid = True
            if not sku:
                if found_qr_but_invalid:
                    reason = "Đọc được QR nhưng không trích xuất được SKU hợp lệ."
                elif seen_undecoded:
                    reason = "Phát hiện vùng QR nhưng không giải mã được (có thể mờ, quá nhỏ hoặc biến dạng)."
                else:
                    reason = "Không phát hiện QR đọc được hoặc tên ảnh có SKU hợp lệ."
                if advanced_qr and zbar_decode is None:
                    reason += " Chưa có bộ giải mã pyzbar/ZBar; cần cài đủ requirements.txt."
                if invalid_images:
                    reason += " Ảnh không mở được: " + ", ".join(invalid_images[:5])
                summary_error(result, folder, reason)
                continue

        if previous and previous.get("sku") != sku:
            summary_error(result, folder, "SKU của nhóm đã xuất trước đây là " + str(previous.get("sku")) +
                          ", nhưng quy tắc hiện tại xác định " + sku +
                          ". Để không ghi đè ảnh cũ, hãy chọn thư mục đích mới cho lần xuất đúng.")
            continue

        previous_files = previous["files"] if previous else {}
        changed = []
        for image in images:
            old = previous_files.get(image.name)
            if not old:
                continue
            if (old.get("size") != current[image.name]["size"]
                    or old.get("mtime_ns") != current[image.name]["mtime_ns"]):
                changed.append(image.name + " (đã sửa)")
            elif not exported_file_present(destination, old):
                changed.append(image.name + " (thiếu bản xuất cũ)")
        if changed:
            summary_error(result, folder, "Ảnh đã xuất có thay đổi: " + ", ".join(changed[:6]) +
                          ". Không xuất trùng hoặc ghi đè; hãy đổi tên ảnh nguồn nếu muốn lưu phiên bản mới.")
            continue

        new_images = [image for image in images if image.name not in previous_files]
        allocated = []
        new_entries = {}
        next_index = counters.get(sku, 0)
        try:
            for image in new_images:
                while True:
                    next_index += 1
                    filename = f"{sku} ({next_index}){image.suffix}"
                    if filename.casefold() not in existing_names and all(
                        filename.casefold() != name.casefold() for name in allocated
                    ):
                        break
                target = destination / filename
                exclusive_copy(image, target)
                allocated.append(filename)
                new_entries[image.name] = {
                    **current[image.name], "dest": filename,
                }

            old_entry = manifest["groups"].get(folder_key)
            manifest["groups"][folder_key] = {
                "sku": sku,
                "qr": qr_raw,
                "source": method,
                "ignored_filename_prefixes": rule_snapshot,
                "files": {**previous_files, **new_entries},
            }
            try:
                save_manifest(destination, manifest)
            except Exception:
                if old_entry is None:
                    manifest["groups"].pop(folder_key, None)
                else:
                    manifest["groups"][folder_key] = old_entry
                raise
        except (OSError, ValueError, TypeError) as error:
            # Nhóm lỗi: rollback bản copy vừa tạo; không đụng tới ảnh gốc.
            for filename in allocated:
                try:
                    (destination / filename).unlink()
                except OSError:
                    pass
            summary_error(result, folder, "Không thể copy/lưu nhật ký: " + str(error))
            continue

        counters[sku] = next_index
        existing_names.update(name.casefold() for name in allocated)
        result["copied_images"] += len(allocated)
        result["skipped_images"] += len(images) - len(allocated)
        result["successful_groups"] += 1
        result["filename_groups" if method == "filename" else "qr_groups"] += 1

    for traversal_error in traversal_errors:
        result["errors"].append(traversal_error)
        result["error_groups"] += 1
    try:
        sync_qr_txt(destination, manifest)
    except (OSError, ValueError, UnicodeError) as error:
        result["errors"].append({
            "folder": str(destination / QR_TXT_NAME),
            "reason": "Không lưu được file TXT: " + str(error) + ". Có thể chạy lại để thử đồng bộ.",
        })
    return result


PAGE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ANCARAT – IMAGE SKU PROCESSOR</title>
  <style>
    :root { --wine: #7A0019; --ruby: #A00024; --cream: #F9F4EB; --gold: #D3AC64;
            --ink: #292529; --muted: #777178; --line: #E8E3E3; --green: #1F704E; }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
           background: #F7F6F4; color: var(--ink); line-height: 1.5; }
    .topline { height: 5px; background: linear-gradient(90deg, var(--wine), var(--ruby), var(--gold)); }
    .page { max-width: 900px; margin: 0 auto; padding: 44px 20px 70px; }
    .brand { color: var(--wine); font-size: 13px; font-weight: 800; letter-spacing: .23em; margin-bottom: 10px; }
    h1 { font-size: clamp(27px, 5vw, 35px); letter-spacing: -.04em; line-height: 1.2;
         margin: 0 0 9px; font-weight: 750; }
    .subtitle { margin: 0 0 30px; color: var(--muted); font-size: 15px; }
    .panel { background: white; border: 1px solid var(--line); border-radius: 17px;
             box-shadow: 0 12px 36px rgba(44, 26, 31, .035); padding: 31px; }
    .panel-title { font-size: 17px; font-weight: 750; margin: 0 0 23px; }
    .field { margin-bottom: 23px; }
    label { display: block; font-size: 14px; font-weight: 690; margin-bottom: 8px; }
    label .num, .opt-title .num { display: inline-grid; place-items: center; background: var(--cream); color: var(--wine);
                 width: 24px; height: 24px; border-radius: 7px; font-size: 12px; margin-right: 8px; }
    input { width: 100%; height: 49px; border-radius: 10px; border: 1px solid #DCD7D8;
            padding: 0 14px; outline: none; font-family: Consolas, "Segoe UI", monospace; font-size: 14px;
            background: #FEFDFD; color: #393238; transition: border-color .15s, box-shadow .15s; }
    input:focus { border-color: var(--wine); box-shadow: 0 0 0 3px rgba(122, 0, 25, .09); }
    input::placeholder { color: #A19CA0; }
    .hint { color: var(--muted); font-size: 12px; margin: 7px 0 0; }
    .rule-label { display: inline-flex; align-items: center; gap: 7px; }
    .opt-title { display:block; font-size:14px; font-weight:690; margin-bottom:8px; }
    .option { display:flex; gap:12px; align-items:center; border:1px solid var(--line);
              padding:14px; border-radius:10px; background:#FEFDFD; cursor:pointer; }
    .option input[type="checkbox"] { flex:0 0 19px; width:19px; height:19px; margin:0;
                     accent-color: var(--wine); box-shadow:none; }
    .option span { font-size:13px; font-weight:500; }
    .option strong { color:var(--wine); font-weight:750; }
    .rule-tag { display: inline-flex; background: #F4E6E7; color: var(--wine); border-radius: 5px;
                font-size: 10px; padding: 3px 6px; font-weight: 750; letter-spacing: .04em; }
    .action { width: 100%; min-height: 52px; margin-top: 5px; border: none; border-radius: 10px;
              background: var(--wine); color: white; font-size: 14px; letter-spacing: .025em;
              font-weight: 750; cursor: pointer; transition: background .16s, transform .16s; }
    .action:not(:disabled):hover { background: var(--ruby); transform: translateY(-1px); }
    .action:disabled { opacity: .76; cursor: wait; }
    .spin { display: none; vertical-align: -3px; width: 15px; height: 15px;
            margin-right: 10px; border: 2px solid #F4DCE2; border-top-color: white;
            border-radius: 50%; animation: turn .7s linear infinite; }
    .busy .spin { display: inline-block; }
    @keyframes turn { to { transform: rotate(360deg); } }
    .safety { margin-top: 17px; border-radius: 10px; background: var(--cream); padding: 12px 15px;
              color: #625647; font-size: 13px; }
    .result { margin-top: 25px; display: none; }
    .result.visible { display: block; }
    .result-heading { display: flex; gap: 12px; align-items: baseline; justify-content: space-between;
                      margin: 0 0 16px; flex-wrap: wrap; }
    .result-heading h2 { font-size: 19px; margin: 0; }
    .result-heading small { font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
    .stats { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; }
    .stat { border: 1px solid var(--line); border-radius: 12px; background: #fff; padding: 18px 17px; }
    .stat-number { font-size: 29px; font-weight: 770; font-variant-numeric: tabular-nums;
                   line-height: 1.15; color: var(--wine); }
    .stat-title { font-size: 12px; color: var(--muted); margin-top: 7px; }
    .message { margin: 0 0 14px; padding: 12px 15px; border-radius: 10px;
               font-size: 13px; background: #EEF7F1; color: var(--green); }
    .message.problem { background: #FFF1F0; color: #A12222; }
    .errorbox { margin-top: 19px; border-radius: 13px; background: #fff;
                border: 1px solid var(--line); padding: 21px; }
    .errorbox h3 { margin: 0 0 12px; font-size: 15px; }
    .errorbox ul { list-style: none; padding: 0; margin: 0; max-height: 380px; overflow: auto; }
    .errorbox li { padding: 12px 0; border-top: 1px solid #EFECEC; font-size: 12px; }
    .errorbox .path { font-family: Consolas, monospace; color: var(--ink); overflow-wrap: anywhere; }
    .errorbox .why { margin-top: 4px; color: #A12222; overflow-wrap: anywhere; }
    footer { color: #938D90; text-align: center; font-size: 12px; margin-top: 26px; }
    @media (max-width: 600px) { .page { padding-top: 30px; } .panel { padding: 23px 18px; }
             .stats { grid-template-columns: repeat(2, minmax(0,1fr)); }
             .stat { padding: 15px 13px; } .stat-number { font-size: 25px; } }
  </style>
</head>
<body>
  <div class="topline"></div>
  <main class="page">
    <div class="brand">ANCARAT · V3</div>
    <h1>Image SKU Processor</h1>
    <p class="subtitle">Tự động tìm SKU, đổi tên và gom ảnh sản phẩm vào một thư mục.</p>
    <section class="panel" aria-labelledby="inputTitle">
      <h2 id="inputTitle" class="panel-title">Chọn thư mục cần xử lý</h2>
      <form id="workForm">
        <div class="field">
          <label for="source"><span class="num">1</span>Đường dẫn thư mục nguồn</label>
          <input id="source" name="source" spellcheck="false" required
                 placeholder="D:\ANH_SAN_PHAM" autocomplete="off">
          <p class="hint">Tự động đi vào tất cả thư mục con và chỉ xử lý thư mục nhỏ nhất.</p>
        </div>
        <div class="field">
          <label for="destination"><span class="num">2</span>Đường dẫn thư mục đích</label>
          <input id="destination" name="destination" spellcheck="false" required
                 placeholder="D:\ANH_DA_XU_LY" autocomplete="off">
          <p class="hint">Tất cả ảnh được gom vào đây, giữ nguyên định dạng và chất lượng gốc.</p>
        </div>
        <div class="field">
          <label for="skipPrefixes"><span class="num">3</span><span class="rule-label">Tiền tố tên ảnh cần đọc QR <span class="rule-tag">CÓ THỂ CHỈNH</span></span></label>
          <input id="skipPrefixes" name="skipPrefixes" spellcheck="false" value="AMI"
                 placeholder="AMI, ABC, TMP" autocomplete="off" maxlength="500">
          <p class="hint">Ví dụ: <strong>AMI, ABC</strong>. Tên ảnh bắt đầu bằng những chữ này sẽ <strong>không được lấy làm SKU</strong>.
            Nếu không có tên SKU hợp lệ khác trong nhóm, ứng dụng tự đọc QR. Ngăn cách bằng dấu phẩy; xóa hết nếu muốn tắt quy tắc.</p>
        </div>
        <div class="field">
          <div class="opt-title"><span class="num">4</span>Chế độ đọc mã QR</div>
          <label for="advancedQr" class="option">
            <input type="checkbox" id="advancedQr" name="advancedQr" checked>
            <span><strong>Quét QR nâng cao</strong> (khuyên bật)<br>
              <span class="hint">Nếu đọc trực tiếp thất bại: tự xoay 4 hướng, chỉnh phối cảnh,
              tăng tương phản và thử bộ giải mã dự phòng. Không chỉnh sửa ảnh nguồn.</span>
            </span>
          </label>
        </div>
        <button type="submit" class="action" id="startButton">
          <span class="spin" aria-hidden="true"></span><span id="buttonText">BẮT ĐẦU XỬ LÝ</span>
        </button>
      </form>
      <div class="safety">✓ Tên ảnh bắt đầu bằng tiền tố bỏ qua (mặc định <b>AMI</b>) sẽ không được xem là SKU.
        Nội dung QR vẫn được kiểm tra bình thường. Không sửa, xóa hay di chuyển ảnh nguồn.</div>
    </section>

    <section class="result" id="result" aria-live="polite">
      <div class="result-heading"><h2>Kết quả xử lý</h2><small id="output"></small></div>
      <p id="message" class="message"></p>
      <div class="stats">
        <div class="stat"><div class="stat-number" id="total_groups">0</div><div class="stat-title">Thư mục có ảnh</div></div>
        <div class="stat"><div class="stat-number" id="successful_groups">0</div><div class="stat-title">Thư mục thành công</div></div>
        <div class="stat"><div class="stat-number" id="copied_images">0</div><div class="stat-title">Ảnh mới đã copy</div></div>
        <div class="stat"><div class="stat-number" id="filename_groups">0</div><div class="stat-title">SKU từ tên file</div></div>
        <div class="stat"><div class="stat-number" id="qr_groups">0</div><div class="stat-title">SKU từ mã QR</div></div>
        <div class="stat"><div class="stat-number" id="error_groups">0</div><div class="stat-title">Thư mục bị lỗi</div></div>
      </div>
      <div id="errorbox" class="errorbox" hidden>
        <h3>Danh sách lỗi cần kiểm tra</h3>
        <ul id="errorlist"></ul>
      </div>
    </section>
    <footer>Chạy trên máy tính của bạn · Không gửi ảnh lên Internet · Kết quả nằm trong thư mục đích</footer>
  </main>
  <script>
    const form = document.getElementById('workForm');
    const result = document.getElementById('result');
    const button = document.getElementById('startButton');
    const buttonText = document.getElementById('buttonText');
    const message = document.getElementById('message');
    const counts = ['total_groups','successful_groups','copied_images','filename_groups','qr_groups','error_groups'];
    const errorbox = document.getElementById('errorbox');
    const errorlist = document.getElementById('errorlist');
    const skipPrefixes = document.getElementById('skipPrefixes');
    const advancedQr = document.getElementById('advancedQr');
    try {
      const saved = localStorage.getItem('ancarat_skip_filename_prefixes');
      if (saved !== null) skipPrefixes.value = saved;
      const savedQr = localStorage.getItem('ancarat_advanced_qr');
      if (savedQr !== null) advancedQr.checked = savedQr === 'true';
    } catch (_) { /* Vẫn hoạt động nếu trình duyệt tắt lưu trữ. */ }
    skipPrefixes.addEventListener('change', () => {
      try { localStorage.setItem('ancarat_skip_filename_prefixes', skipPrefixes.value); } catch (_) {}
    });
    advancedQr.addEventListener('change', () => {
      try { localStorage.setItem('ancarat_advanced_qr', String(advancedQr.checked)); } catch (_) {}
    });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const source = document.getElementById('source').value.trim();
      const destination = document.getElementById('destination').value.trim();
      const ignored_filename_prefixes = skipPrefixes.value.trim();
      const advanced_qr = advancedQr.checked;
      if (!source || !destination) return;
      try {
        localStorage.setItem('ancarat_skip_filename_prefixes', ignored_filename_prefixes);
        localStorage.setItem('ancarat_advanced_qr', String(advanced_qr));
      } catch (_) {}
      button.disabled = true;
      button.classList.add('busy');
      buttonText.textContent = 'ĐANG XỬ LÝ...';
      result.classList.remove('visible');
      try {
        const response = await fetch('/api/process', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source, destination, ignored_filename_prefixes, advanced_qr})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Không thực hiện được yêu cầu.');
        result.classList.add('visible');
        document.getElementById('output').textContent = data.output;
        counts.forEach(id => document.getElementById(id).textContent =
          (data[id] || 0).toLocaleString('vi-VN'));
        if (data.errors && data.errors.length) {
          message.className = 'message problem';
          message.textContent = 'Đã hoàn tất các nhóm hợp lệ. Vui lòng kiểm tra những lỗi bên dưới.';
        } else {
          message.className = 'message';
          message.textContent = `Hoàn tất. ${data.copied_images} ảnh mới đã được copy; ${data.skipped_images} ảnh đã xuất được bỏ qua khi chạy lại.`;
        }
        errorlist.replaceChildren();
        (data.errors || []).forEach(item => {
          const li = document.createElement('li');
          const path = document.createElement('div');
          const why = document.createElement('div');
          path.className = 'path'; why.className = 'why';
          path.textContent = item.folder; why.textContent = item.reason;
          li.append(path, why); errorlist.append(li);
        });
        errorbox.hidden = !data.errors || data.errors.length === 0;
      } catch (error) {
        result.classList.add('visible');
        counts.forEach(id => document.getElementById(id).textContent = '—');
        document.getElementById('output').textContent = '';
        message.className = 'message problem';
        message.textContent = error.message || 'Đã xảy ra lỗi.';
        errorbox.hidden = true;
      } finally {
        button.disabled = false;
        button.classList.remove('busy');
        buttonText.textContent = 'BẮT ĐẦU XỬ LÝ';
      }
    });
  </script>
</body>
</html>
"""


class RequestHandler(BaseHTTPRequestHandler):
    def _send(self, status, payload, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status, data):
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _is_local_request(self):
        """Protect the localhost file-processing service against DNS rebinding."""
        port = self.server.server_port
        accepted_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        return self.headers.get("Host", "").lower() in accepted_hosts

    def _is_allowed_origin(self):
        """Reject browser cross-site POSTs (including text/plain CSRF attempts)."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # Local CLI clients such as curl do not send Origin.
        port = self.server.server_port
        return origin.lower() in {
            f"http://127.0.0.1:{port}", f"http://localhost:{port}"
        }

    def do_GET(self):
        if not self._is_local_request():
            self._json(403, {"error": "Chỉ cho phép truy cập qua localhost."})
            return
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "Không tìm thấy trang."})

    def do_POST(self):
        if not self._is_local_request() or not self._is_allowed_origin():
            self._json(403, {"error": "Chỉ cho phép yêu cầu từ trang localhost."})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._json(415, {"error": "Yêu cầu phải sử dụng Content-Type: application/json."})
            return
        if self.path != "/api/process":
            self._json(404, {"error": "Không tìm thấy địa chỉ xử lý."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                self._json(400, {"error": "Yêu cầu không hợp lệ hoặc quá dài."})
                return
            params = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(params, dict):
                raise ValueError("Dữ liệu gửi lên không hợp lệ.")
        except (ValueError, UnicodeError, json.JSONDecodeError) as error:
            self._json(400, {"error": "Dữ liệu đường dẫn không hợp lệ: " + str(error)})
            return

        if not PROCESS_LOCK.acquire(blocking=False):
            self._json(409, {"error": "Ứng dụng đang xử lý một yêu cầu khác."})
            return
        try:
            result = process_folders(
                params.get("source"), params.get("destination"),
                params.get("ignored_filename_prefixes"),
                params.get("advanced_qr", True),
            )
            self._json(200, result)
        except (ValueError, OSError) as error:
            self._json(400, {"error": str(error)})
        except Exception as error:
            self._json(500, {"error": "Đã xảy ra lỗi không mong muốn: " + str(error)})
        finally:
            PROCESS_LOCK.release()

    def log_message(self, format_string, *args):
        # Không in liên tục log localhost; lỗi đã được hiển thị trên giao diện.
        pass


def main():
    url = f"http://{HOST}:{PORT}"
    try:
        server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    except OSError as error:
        print("Không thể mở ứng dụng trên cổng", PORT, ":", error)
        print("Có thể ứng dụng đang chạy ở cửa sổ khác.")
        return
    print(f"ANCARAT - IMAGE SKU PROCESSOR V{APP_VERSION}")
    print("Mở trình duyệt:", url)
    print("Đóng cửa sổ dòng lệnh hoặc nhấn Ctrl+C để tắt ứng dụng.")
    if os.environ.get("SKU_APP_NO_BROWSER") != "1":
        threading.Timer(1, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
