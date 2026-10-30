# Security / Bảo mật

This is a local file-processing application, not an Internet-facing service.

- The server binds only to `127.0.0.1:5050`; do not modify it to bind to `0.0.0.0` on a shared or public network.
- HTTP requests are restricted to loopback Host headers. Browser POSTs must have a local Origin and use `Content-Type: application/json`.
- The web UI receives the local input and output folder paths. Anyone with local access to the application may initiate file-copy operations accessible to that user's OS account.
- The application does not upload source photos to a remote server. Do not commit real photos, QR payloads, output manifests, or local logs to GitHub.
- Use distinct source and destination directories; never use production folders for automated testing.
- Keep Python and OpenCV/NumPy/pyzbar dependencies up to date after testing compatibility.

**Vulnerability reports:** Avoid posting sensitive paths, QR payloads, or production files in a public issue. Report them privately to the repository maintainer through GitHub's private vulnerability reporting feature if it is enabled. The owner can configure this under repository security settings.

**Scope:** The project is intended for a trusted local user. It does not provide authentication or protect against malicious programs already running with the same operating-system privileges.
