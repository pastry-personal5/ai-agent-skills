# Changelog

## Unreleased

- Condense the shared workflow and generated guidance without changing scaffold behavior, conflict safeguards, or phase/milestone conventions.
- Remove legacy project-specific template rules and eval assertions, centralize the development package version, make Claude target parsing path-aware, and exclude caches and filesystem metadata from built packages.
- Split quick-scaffolding into one shared engine/workflow and thin native adapters: a Codex skill with explicit `$quick-scaffolding` policy, and a Claude Code plugin command with `/quick-scaffolding`, `$ARGUMENTS`, `argument-hint`, and manual-only invocation. Add a deterministic builder for self-contained packages and cross-package parity tests.
- The development process doc now lets phase and milestone numbers change as plans evolve (update IDs, filenames and links together), and names milestone plan docs `milestone-NN-<theme>-overview.md` and `milestone-NN-<theme>-architecture.md`.
- MIT, BSD-2-Clause, BSD-3-Clause and ISC are bundled with their canonical text, so the agent no longer writes licence text from memory. Put the copyright holder in `license_holder` in the values file; the year defaults to the current one (`license_year` overrides it).
- On a repo that already has files, the plan and the final summary show a directory such as `node_modules/` as one line with its file count, instead of listing every file in it.
- The docs index no longer lists files under `docs/archive/`.

## 1.0.0 - 2026-10-07

First release of `quick-scaffolding`.

- `/quick-scaffolding [target-dir]` gives a new repo the same starting files every time: `README.md`, `LICENSE`, `.gitignore`, `AGENTS.md`, a one-line `CLAUDE.md`, and a `docs/` folder with the development process, contribution guide and docs index.
- GUI apps also get the product-behavior and `ux-*` docs. Non-GUI repos never link to them.
- The skill asks one batch of questions (name, stack, GUI, license, tooling), skipping what you already answered. The tooling you confirm is written identically into every gate.
- `scripts/scaffold.py` does the file work: a `plan` dry run, then `write`. Existing files that differ are never touched unless you choose to overwrite them, or append to `README.md`. It checks every conflict before writing anything.
- Apache-2.0 is bundled. MIT and BSD are generated with your name and the year. Other licenses use text you supply.
- It writes meta files only: no source code, `git init`, commits or builds.
- Unit tests, a no-agent smoke check and agent evals ship in `quick-scaffolding/evals/`.
