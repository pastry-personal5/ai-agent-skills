# Shared scaffolding workflow

Create consistent repository metadata and docs. Do not create source code, build, run `git init`, or commit.

The platform adapter supplies `<skill-dir>`, its self-contained package directory. `<target>` is the requested directory or, if omitted, the current directory. Resolve relative paths from the current directory and expand `~`. Treat the request and conversation as interview answers.

Handle judgement here: interview, values, and conflicts. Use `<skill-dir>/scripts/scaffold.py` for all file work; it applies `assets/manifest.json`, templates, licences, conflicts, the docs index, and the final summary. Do not copy files manually or read the script unless troubleshooting.

## 1. Interview

In one message, ask only for missing information:

1. Project name (default: target directory name) and one-line description.
2. Stack or language.
3. Whether it has a GUI (controls product and UX docs).
4. License, offering Apache-2.0 as the default.
5. Formatter, linter, and test tool. Propose conventional tools requiring no extra config and ask for "ok" or replacements. Skip known answers. If the stack is unknown, ask questions 1–4 first, then make the tooling proposal in the only permitted follow-up.

For MIT, BSD-2-Clause, BSD-3-Clause, or ISC, run `git config user.name` in the target and ask for the copyright holder only if it is empty. The script supplies the current year. Apache-2.0 needs neither.

## 2. Create the values file

Write JSON outside the target, preferably in a temporary directory. See `references/values.example.json`.

| Key | Value |
|---|---|
| `name`, `description`, `stack` | Interview answers; keep `stack` short. |
| `license` | SPDX ID. |
| `license_holder` | One-line holder; required for MIT, BSD-2-Clause, BSD-3-Clause, and ISC. |
| `license_year` | Optional; defaults to the current year. |
| `gui` | Boolean. |
| `gate` | Exact format-check, lint-with-warnings-denied, and test commands. |
| `commands` | `["command", "short comment"]` pairs for available build/run/test/format/lint commands. |
| `environment` | Required software, one string per bullet. |
| `conventions` | Two to four stack-specific conventions. |
| `build_output` | Build and dependency directories agents should skip. |
| `generated` | Full `.gitignore` text, including `.DS_Store`; `LICENSE` only for unbundled licenses. |
| `extra_assets` | Optional `{ "src": ..., "dest": ... }` entries added in step 3. |

Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, and ISC are bundled; use their SPDX ID and do not supply text. For another license, do not recreate it: ask the user for its text and set `generated.LICENSE`.

## 3. Plan

Run:

```sh
python3 <skill-dir>/scripts/scaffold.py plan --values <values.json> --target <target>
```

Interpret its JSON:

- `errors` with exit 2: fix the rejected values/request and retry. Exit 1 is an I/O error; report it and stop.
- `warnings`: show them before writing; they indicate template/manifest drift.
- `unregistered_assets`: ask whether to include each and where. Add accepted files to `extra_assets`, then re-plan.
- `fresh: true`: continue to step 4.
- Otherwise, show `plan_tree` and get approval to write. Then ask about each `differs` file, one at a time: overwrite or skip; for `README.md`, also offer append, which preserves existing text and adds missing License/Contributing sections. Explain the difference. Do not ask about `new` or `same` files.

## 4. Write

Run:

```sh
python3 <skill-dir>/scripts/scaffold.py write --values <values.json> --target <target>
```

Add `--overwrite <path>` for each approved replacement and `--append README.md` when chosen. Unnamed differing files remain untouched; paths must exactly match the plan.

## 5. Finish

Print the result's `summary` exactly. It includes the tree, warnings, skipped/appended files, remaining work, and files containing `TBD`. Stop; do not initialize Git, commit, install dependencies, or build.
