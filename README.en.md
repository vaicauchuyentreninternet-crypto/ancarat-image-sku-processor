# ANCARAT Image SKU Processor V3

**Offline local-web application to extract product SKUs from filenames or QR codes, batch-rename photos, and export QR metadata.**

[Tiếng Việt](README.md) · **GitHub package version:** `3.0.1` · **Python:** 3.10+ · **Primary platform:** Windows 10/11

## Highlights

- Prefer a validated SKU found in filenames. No QR decoding is needed for those folders.
- Fall back to OpenCV QR decoding; optional enhanced mode rotates the image, rectifies the QR perspective, adjusts contrast, and tries `pyzbar`/ZBar.
- Ignore configurable filename prefixes such as `AMI` while still allowing their images to be QR-scanned.
- Support special SKU patterns containing periods (e.g. `TMV.C001C` and `MDTP.13`).
- Copy files without modifying pixels, format, or source files; automatically assign `SKU (1).jpg`, `SKU (2).png`, etc.
- Track outputs with `.sku_processor_manifest.json` so reruns do not duplicate unchanged groups.
- Produce `du_lieu_qr.txt` as UTF-8 with BOM: one `SKU|RAW_QR` line per processed product group.
- Run entirely on your own computer via `http://127.0.0.1:5050` using Python's standard-library web server.

This project **does not** perform object recognition, visual similarity matching, AI inference, or OCR.

## Windows quick start

1. Install **Python 3.10+** from [python.org](https://www.python.org/downloads/) and select **Add Python to PATH**.
2. Download and extract this repository ZIP.
3. Double-click `CHAY_TREN_WINDOWS.bat`. It creates a project-local `.venv` and installs dependencies on first launch; Internet is required for initial installation only.
4. Open `http://127.0.0.1:5050` if a browser window does not open automatically.
5. Enter your source and destination directory paths, then click **BẮT ĐẦU XỬ LÝ** (Start Processing).

### Manual install

```bash
python -m pip install -r requirements.txt
python app.py
```

On Ubuntu/Debian, `pyzbar` needs the system `libzbar0` package. On macOS, install ZBar separately (for example `brew install zbar`).

### Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions runs the tests on Linux and Windows with Python 3.11 and 3.12.

## Input/output conventions

Each **leaf directory** under the selected source folder is treated as one product. Filenames are examined before attempting QR decoding. Multiple conflicting SKU candidates in a group produce an error instead of an arbitrary choice. Outputs are placed directly into the destination directory without product subfolders.

The app never deletes or renames source images. It will refuse to overwrite existing exported files or silently update a previously processed file with changed size/mtime. Do not delete the manifest file if you plan to reuse the destination directory. If V1/V2 previously assigned incorrect SKUs to `AMI...` files, choose a new destination directory for V3.

**Limitations:** Filename-derived SKUs are not cross-checked against the printed QR; the app does not verify that each copied image is decodable when a filename already supplies a SKU. This is a QR/SKU workflow tool, not a general image-integrity validator.

## Security & distribution

The HTTP server binds to `127.0.0.1`, requires a local Host and Origin for browser calls, and rejects non-JSON API posts. Do not expose the server to a public network. Do not upload production photos, customer information, real QR payloads, or your output manifest to GitHub.

This package **does not contain a LICENSE file**. Public hosting on GitHub alone does not grant others a right to reuse or redistribute the code. Obtain the rights holder's approval and select a license before publicly releasing the repository.

See [README.md](README.md) for examples, [CHANGELOG.md](CHANGELOG.md) for release details, [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, and [SECURITY.md](SECURITY.md) for security notes.
