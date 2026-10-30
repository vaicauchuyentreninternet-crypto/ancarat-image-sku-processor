"""End-to-end file-processing tests with synthetic, non-production sample data."""

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import cv2
import pytest
import qrcode

import app


def write_img(path, color=(240, 240, 240)):
    path.parent.mkdir(parents=True, exist_ok=True)
    image = __import__("numpy").full((48, 48, 3), color, dtype="uint8")
    ok, output = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(output.tobytes())
    return path


def write_qr(path, text):
    """Generate offline QR data for testing; not a real ANCARAT product QR."""
    code = qrcode.QRCode(box_size=12, border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(text)
    code.make(fit=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    code.make_image(fill_color="black", back_color="white").convert("RGB").save(path)
    return path


@pytest.mark.parametrize("stem,expected", [
    ("G3SMD00M0660038", ("G3SMD00M0660038", "exact")),
    ("G3SMD00M0660038_final", ("G3SMD00M0660038", "decorated")),
    ("G3SMD00M0660038 (copy)", ("G3SMD00M0660038", "decorated")),
    ("TMV.C001C_hinhchinh", ("TMV.C001C", "decorated")),
    ("MDTP.13", ("MDTP.13", "exact")),
    ("VDD-01", ("VDD-01", "exact")),
    ("IMG_001", None),
    ("DSC_0001", None),
])
def test_filename_sku(stem, expected):
    assert app.filename_sku(stem) == expected


def test_ignored_prefixes_and_invalid_value():
    assert app.ignored_prefixes(" AMI, DSC; AMI ") == ("AMI", "DSC")
    assert app.filename_sku("AMI07927", app.ignored_prefixes("AMI")) is None
    with pytest.raises(ValueError):
        app.ignored_prefixes("*INVALID*")


@pytest.mark.parametrize("raw,sku", [
    ("TMV.C001C.Data123", "TMV.C001C"),
    ("MDTP.13.MoreData", "MDTP.13"),
    ("G75D1ZTD1680009.PWH0000_PWH00004X224X24470", "G75D1ZTD1680009"),
    ("VDD-01", "VDD-01"),
    ("IMG_001", None),
])
def test_qr_sku(raw, sku):
    assert app.qr_sku(raw) == sku


def test_qr_escape():
    assert app.qr_escape("a|b\\c\nd") == "a\\|b\\\\c\\nd"


def test_filename_group_rerun_and_preserve_originals(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    p1 = write_img(source / "san_pham" / "VDD-01.jpg")
    p2 = write_img(source / "san_pham" / "IMG_001.png")
    bytes_before = {p.name: p.read_bytes() for p in (p1, p2)}

    first = app.process_folders(str(source), str(output), "AMI")
    assert first["total_groups"] == 1
    assert first["successful_groups"] == 1
    assert first["copied_images"] == 2
    assert first["filename_groups"] == 1
    assert first["qr_groups"] == 0
    assert (output / "VDD-01 (1).png").exists()  # natural order: IMG_001 then VDD-01
    assert (output / "VDD-01 (2).jpg").exists()
    assert {p.name: p.read_bytes() for p in (p1, p2)} == bytes_before
    assert (output / app.QR_TXT_NAME).read_text(encoding="utf-8-sig") == "VDD-01|\n"

    second = app.process_folders(str(source), str(output), "AMI")
    assert second["copied_images"] == 0
    assert second["skipped_images"] == 2
    assert second["successful_groups"] == 1
    assert (output / app.QR_TXT_NAME).read_text(encoding="utf-8-sig") == "VDD-01|\n"


def test_same_sku_across_groups_and_conflict(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    write_img(source / "a" / "VDD-01.png")
    write_img(source / "b" / "VDD-01.jpg")
    write_img(source / "conflict" / "VDD-01.jpg")
    write_img(source / "conflict" / "TMV.C001C.png")
    result = app.process_folders(str(source), str(output))
    assert result["successful_groups"] == 2
    assert result["error_groups"] == 1
    assert result["copied_images"] == 2
    assert (output / "VDD-01 (1).png").exists()
    assert (output / "VDD-01 (2).jpg").exists()
    assert any("xung đột" in item["reason"] for item in result["errors"])


def test_qr_filename_ami_and_advanced_decoder(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    value = "G75D1ZTD1680009.PWH0000_PWH00004X224X24470"
    write_qr(source / "batch" / "AMI07927.png", value)
    result = app.process_folders(str(source), str(output), "AMI", advanced_qr=True)
    assert result["qr_groups"] == 1, result["errors"]
    assert result["copied_images"] == 1, result["errors"]
    assert (output / "G75D1ZTD1680009 (1).png").exists()
    assert (output / app.QR_TXT_NAME).read_text(encoding="utf-8-sig") == f"G75D1ZTD1680009|{value}\n"


def test_changed_source_group_does_not_overwrite(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    sample = write_img(source / "batch" / "VDD-01.png")
    first = app.process_folders(str(source), str(output))
    assert first["copied_images"] == 1
    exported = output / "VDD-01 (1).png"
    bytes_before = exported.read_bytes()
    sample.write_bytes(sample.read_bytes() + b"modified")
    second = app.process_folders(str(source), str(output))
    assert second["error_groups"] == 1
    assert second["copied_images"] == 0
    assert exported.read_bytes() == bytes_before


def test_refuse_output_inside_input(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="ngoài thư mục nguồn"):
        app.process_folders(str(source), str(source / "output"))


@pytest.fixture
def web_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    status, payload = response.status, response.read()
    connection.close()
    return status, payload


def test_http_root_and_block_non_json_post(web_server):
    code, body = request(web_server, "GET", "/")
    assert code == 200 and b"ANCARAT" in body
    code, body = request(web_server, "POST", "/api/process", "{}", {"Content-Type": "text/plain"})
    assert code == 415
    assert "application/json" in json.loads(body)["error"]


def test_http_reject_external_origin_and_host(web_server):
    port = web_server.server_port
    code, _ = request(web_server, "POST", "/api/process", "{}", {
        "Host": f"127.0.0.1:{port}", "Content-Type": "application/json", "Origin": "https://attacker.example"
    })
    assert code == 403
    code, _ = request(web_server, "GET", "/", headers={"Host": "external.example"})
    assert code == 403


def test_rotated_qr_is_decodable(tmp_path):
    path = write_qr(tmp_path / "qr.png", "VDD-01.Data123")
    data = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert data is not None
    rotated = cv2.rotate(data, cv2.ROTATE_90_CLOCKWISE)
    target = tmp_path / "rotated.png"
    assert cv2.imwrite(str(target), rotated)
    decoded, error, seen = app.read_qr(target, cv2.QRCodeDetector(), advanced=True)
    assert error == ""
    assert app.qr_sku(decoded) == "VDD-01"
    assert seen is True


def test_existing_output_not_overwritten(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    write_img(source / "batch" / "VDD-01.png")
    output.mkdir()
    existing = output / "VDD-01 (1).png"
    existing.write_bytes(b"existing customer file must never be overwritten")
    result = app.process_folders(str(source), str(output))
    assert result["copied_images"] == 1
    assert existing.read_bytes() == b"existing customer file must never be overwritten"
    assert (output / "VDD-01 (2).png").exists()


def test_http_process_valid_request(web_server, tmp_path):
    source, output = tmp_path / "in", tmp_path / "out"
    write_img(source / "group" / "VDD-01.png")
    payload = json.dumps({"source": str(source), "destination": str(output),
                          "ignored_filename_prefixes": "AMI", "advanced_qr": True})
    port = web_server.server_port
    code, body = request(web_server, "POST", "/api/process", payload, {
        "Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"
    })
    response = json.loads(body)
    assert code == 200, response
    assert response["copied_images"] == 1
    assert (output / "VDD-01 (1).png").exists()
