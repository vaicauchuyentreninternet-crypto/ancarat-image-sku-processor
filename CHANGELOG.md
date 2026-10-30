# Changelog

## 3.0.1 — GitHub-ready packaging (2026-10-30)

- Preserved V3's SKU filename detection, configurable `AMI` exclusions, enhanced OpenCV QR decoding, ZBar fallback, safe copy, manifest, and TXT export behavior.
- Included a project-local virtual environment launcher for Windows (`CHAY_TREN_WINDOWS.bat`).
- Added bilingual README files, GitHub-friendly ignore rules, contributing and security documentation, test dependencies, and automated CI.
- Restricted web requests to local Host/Origin and `application/json` POST requests, to reduce local server misuse by hostile web pages.
- Counted filesystem traversal errors in `error_groups` as well as the error listing.
- Declared NumPy explicitly among the runtime dependencies; OpenCV already uses NumPy arrays.

## 3.0.0 — Advanced QR V3 (2026-10-23)

- Added advanced QR scanning (image rotation, perspective rectification, contrast processing).
- Added optional offline `pyzbar` fallback for difficult QR images.
- Kept exclusion rules for misleading filename prefixes, particularly `AMI`.
- Added reports that distinguish no QR found, undecodable QR, and QR decoded without a valid SKU.
- Original archive: `ANCARAT_IMAGE_SKU_PROCESSOR_V3_QR_NANG_CAO.zip`.

## Earlier versions (2026-10-22)

- V1: Extract SKU from filenames or QR codes; copy and rename images; produce a consolidated TXT file.
- V2: Exclude `AMI` and custom filename prefixes from SKU candidates.
