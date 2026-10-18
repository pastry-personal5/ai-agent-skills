# Bundled licence texts

`Apache-2.0.txt` is copied into a scaffolded repo byte for byte.

The `*.txt.tmpl` files are the plain texts from the SPDX license-list-data repository (<https://github.com/spdx/license-list-data>, `text/` folder, fetched 2026-10-15 from `main`; latest release v3.29.0). Three edits were made to each, and the licence wording is unchanged:

- `<year>` became `{{YEAR}}`.
- `<copyright holders>` or `<owner>` became `{{HOLDER}}`.
- Trailing whitespace was removed.

`scripts/scaffold.py` fills `{{YEAR}}` from `values.license_year` (default: the current year) and `{{HOLDER}}` from `values.license_holder`. To bundle another licence, add its SPDX text here the same way and list it under `licenses` in `manifest.json`. This folder is not scanned for unregistered assets. `evals/test_scaffold.py` pins the SHA-256 of each `.tmpl` file; update the pin in the same change as any edit to the wording.
