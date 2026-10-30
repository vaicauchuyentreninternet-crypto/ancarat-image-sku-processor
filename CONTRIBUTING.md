# Contributing / Đóng góp

Thank you for helping improve this offline SKU/QR workflow tool.

## First steps

1. Read [README.md](README.md) (Vietnamese) or [README.en.md](README.en.md) (English).
2. Create an isolated virtual environment and install `requirements-dev.txt`.
3. Run `python -m pytest -q` before and after making a change.
4. Submit a focused pull request that explains the problem, your changes, and test results.

## Code guidelines

- Keep the core tool offline and local-only. Do not add remote APIs, telemetry, or cloud image uploads without explicit review.
- Never change or overwrite source photos. Preserve Unicode paths and existing output-file extensions.
- Prefer filename-only checks when the filename already contains a valid SKU; QR decode should remain the fallback.
- Do not guess a SKU from an uncertain QR or silently resolve conflicting SKUs.
- Add unit tests whenever a new SKU naming convention is supported.
- Avoid introducing heavy frameworks; existing UI uses HTML/CSS/JS embedded in `app.py`.

## Test assets

Tests use synthetic QR codes and temporary files. **Do not commit real product photos, customer data, production QR content, or output manifests.**

## Ownership and licensing

This repository has no license attached. Confirm the applicable copyright holder's permission before distributing forks, publishing a public mirror, or accepting external contributions under a chosen license.
