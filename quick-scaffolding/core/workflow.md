# Shared scaffolding workflow

Give a repository the same starting files every time, so people and agents find the same things in the same places. Write repository metadata and documentation only. Do not create source code, run builds, run `git init`, or commit.

The platform adapter supplies `<skill-dir>`, the self-contained package directory; `<target>` is the requested target directory, or the current working directory when none was given. Resolve relative target paths from the current working directory and expand `~`. Treat the rest of the request and conversation as interview answers.

Your job is the judgement: the interview, turning the answers into a values file, and the conflict questions. `<skill-dir>/scripts/scaffold.py` does the mechanical work from `<skill-dir>/assets/manifest.json`: it copies and fills the templates, builds the docs index, copies the licence, handles existing files, and writes the final summary. Use it instead of copying files by hand. You do not need to read its source.

## 1. Interview

Ask once, in a single message, and only what the request, target directory name, or conversation have not already answered:

1. Project name (default: the target directory's name) and a one-line description.
2. Stack or language, for example Rust, Python, TypeScript.
3. Does the app have a GUI? This decides whether the product-behavior and `ux-*` docs are included.
4. License. Offer Apache-2.0 as the default and let the user pick another.
5. Tooling: formatter, linter and test tool. Propose the conventional tools for the stack that run with no extra config file (for example `rustfmt, clippy and cargo test`) and ask the user to reply "ok" or name replacements. Skip this when the request already names the tools. If the stack is not known yet, ask the other questions first, then put the tooling proposal in one short follow-up. That is the only case for a second message.

For a license that needs a copyright holder (MIT, BSD-2-Clause, BSD-3-Clause, ISC), run `git config user.name` in the target repository and ask only if the name is empty. The script fills in the current year. Apache-2.0 needs neither.

## 2. Write the values file

Turn the answers into this JSON, using exactly the tools the user confirmed. `references/values.example.json` is a complete example. Save it **outside** the target directory, preferably in a temporary directory:

| Key | Content |
|---|---|
| `name`, `description`, `stack` | From the interview. `stack` is a few words, e.g. `Python with ruff and pytest`. |
| `license` | SPDX id, e.g. `Apache-2.0`. |
| `license_holder` | The copyright holder's name on one line. Required for MIT, BSD-2-Clause, BSD-3-Clause and ISC; ignored for other licenses. |
| `license_year` | Optional year such as `2026`. Defaults to the current year. |
| `gui` | `true` or `false`. |
| `gate` | The commands that must pass before a change is done: format check, linter with warnings denied, tests. A list of strings. The script writes them identically into AGENTS.md, the process doc and the contribution guide, so they cannot drift apart. |
| `commands` | `["command", "short comment"]` pairs for build, run, test, format, lint (omit what the stack lacks). |
| `environment` | What must be installed to build and run, one string per bullet. |
| `conventions` | Two to four stack-appropriate code conventions (default formatter, no lint warnings, how errors are handled). |
| `build_output` | Build and dependency directories an agent should never read, e.g. `target/`, `node_modules/`. |
| `generated` | `".gitignore"`: the full file for the stack, plus `.DS_Store`. `"LICENSE"`: only when `license` has no bundled text (see below). |
| `extra_assets` | Optional `{"src": ..., "dest": ...}` objects, filled in step 3. `src` is a path inside `assets/`, `dest` a path inside the target. |

Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause and ISC are bundled: set `license` to the SPDX id (and `license_holder` where needed) and never write their text yourself. For any other licence, such as GPL or MPL, do not write it from memory: ask the user for the text file and put its contents in `generated.LICENSE`.

## 3. Plan

Run `python3 <skill-dir>/scripts/scaffold.py plan --values <values.json> --target <target>`. It writes nothing. Read its JSON:

- **`errors`** (exit status 2): the values or request were rejected and nothing was written. Fix the values file and run again. Exit status 1 is an I/O error: show it to the user and stop.
- **`warnings`**: if there are any, tell the user before going on. A warning means a template in `assets/` no longer matches `manifest.json`, so the scaffold would ship a file with a missing or unfilled section.
- **`unregistered_assets`**: files in `assets/` that the manifest does not mention. For each, tell the user and ask whether to include it and at what path. If yes, add it to `extra_assets` and plan again.
- **`fresh`**: true when the target is missing, empty, or holds only `.git`. If true, go straight to step 4. If false, show `plan_tree`, get a yes before writing anything, then ask about each file whose `status` is `differs`, one file at a time:
  - overwrite or skip, and for `README.md` also **append** (keep the existing text and add the License and Contributing sections it lacks).

  Files that are `new` or `same` need no question. Say what differs so the choice is informed.

## 4. Write

Run `python3 <skill-dir>/scripts/scaffold.py write --values <values.json> --target <target>`, adding `--overwrite <path>` for each file the user chose to replace and `--append README.md` if they chose that. Any existing file that differs and is not named is left alone. The script rejects an `--overwrite` path that is not one of the scaffold's files, so spell it as `plan` listed it.

## 5. Finish

Print the `summary` field of the result exactly as it is: the file tree, any warnings, skipped and appended files, what is still to write, and which files still contain `TBD`. Stop there. Do not run `git init`, commit, install dependencies, or build.
