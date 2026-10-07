# Changelog

## 1.0.0 - 2026-10-07

First release of `quick-scaffolding`.

- `/quick-scaffolding [target-dir]` gives a new repo the same starting files every time: `README.md`, `LICENSE`, `.gitignore`, `AGENTS.md`, a one-line `CLAUDE.md`, and a `docs/` folder with the development process, contribution guide and docs index.
- GUI apps also get the product-behavior and `ux-*` docs. Non-GUI repos never link to them.
- The skill asks one batch of questions (name, stack, GUI, license, tooling), skipping what you already answered. The tooling you confirm is written identically into every gate.
- `scripts/scaffold.py` does the file work: a `plan` dry run, then `write`. Existing files that differ are never touched unless you choose to overwrite them, or append to `README.md`. It checks every conflict before writing anything.
- Apache-2.0 is bundled. MIT and BSD are generated with your name and the year. Other licenses use text you supply.
- It writes meta files only: no source code, `git init`, commits or builds.
- Unit tests, a no-agent smoke check and agent evals ship in `quick-scaffolding/evals/`.
