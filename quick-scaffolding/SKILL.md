---
name: quick-scaffolding
description: Scaffold a new repo's meta files (README.md, LICENSE, .gitignore, AGENTS.md, a one-line CLAUDE.md, and a docs/ folder with the development process, contribution guide and, for GUI apps, the product-behavior and UX docs). Runs only when the user invokes /quick-scaffolding [target-dir].
disable-model-invocation: true
---

# Quick scaffolding

Give a repo the same starting files every time, so people and agents find the same things in the same places. This skill writes repo meta files only. It does not create source code, run builds, run `git init`, or commit.

Your job is the judgement: the interview, turning the answers into a values file, and the conflict questions. `scripts/scaffold.py` (in this skill's base directory) does the mechanical work from `assets/manifest.json`: it copies and fills the templates, builds the docs index, copies the licence, handles existing files, and writes the final summary. Use it instead of copying files by hand, so every run produces the same result. Run it as described here; you do not need to read its source.

Arguments: $ARGUMENTS

The first token of the arguments is the target directory if it looks like a path (it contains `/`, starts with `.` or `~`, or names an existing directory). Everything else in them is answers to the interview. With no such token, the target is the current directory.

## 1. Interview

Ask once, in a single message, and only what the arguments, the directory name, or the conversation have not already answered:

1. Project name (default: the target directory's name) and a one-line description.
2. Stack or language, for example Rust, Python, TypeScript.
3. Does the app have a GUI? This decides whether the product-behavior and `ux-*` docs are included.
4. License. Offer Apache-2.0 as the default and let the user pick another.
5. Tooling: formatter, linter and test tool. Propose the conventional tools for the stack that run with no extra config file (for example `rustfmt, clippy and cargo test`) and ask the user to reply "ok" or name replacements. Skip this when the arguments already name the tools. If the stack is not known yet, you cannot propose tools: ask the other questions first, then put the tooling proposal in one short follow-up. That is the only case for a second message.

For a license that needs a copyright holder (MIT, BSD), use `git config user.name` and the current year, and ask only if the name is empty. Apache-2.0 needs neither.

## 2. Write the values file

Turn the answers into this JSON, using exactly the tools the user confirmed. [references/values.example.json](references/values.example.json) is a complete example. Save it **outside** the target directory (a temp folder or the session scratchpad):

| Key | Content |
|---|---|
| `name`, `description`, `stack` | From the interview. `stack` is a few words, e.g. `Python with ruff and pytest`. |
| `license` | SPDX id, e.g. `Apache-2.0`. |
| `gui` | `true` or `false`. |
| `gate` | The commands that must pass before a change is done: format check, linter with warnings denied, tests. A list of strings. The script writes them identically into AGENTS.md, the process doc and the contribution guide, so they cannot drift apart. |
| `commands` | `["command", "short comment"]` pairs for build, run, test, format, lint (omit what the stack lacks). |
| `environment` | What must be installed to build and run, one string per bullet. |
| `conventions` | Two to four stack-appropriate code conventions (default formatter, no lint warnings, how errors are handled). |
| `build_output` | Build and dependency directories an agent should never read, e.g. `target/`, `node_modules/`. |
| `generated` | `".gitignore"`: the full file for the stack, plus `.DS_Store`. `"LICENSE"`: only when `license` has no bundled text (see below). |
| `extra_assets` | Optional `{"src": ..., "dest": ...}` objects, filled in step 3. `src` is a path inside `assets/`, `dest` a path inside the target. |

The bundled licence is Apache-2.0. For MIT or BSD, write the short standard text with the year and holder into `generated.LICENSE`. For a long licence such as GPL or MPL, do not write it from memory: ask the user for the text file and put its contents there.

## 3. Plan

Run `python3 <skill>/scripts/scaffold.py plan --values <values.json> --target <dir>`. It writes nothing. Read its JSON:

- **`errors`** (exit status 2): the values or the request were rejected and nothing was written. Fix the values file and run again. Exit status 1 is an I/O error: show it to the user and stop.
- **`warnings`**: if there are any, tell the user before going on. A warning means a template in `assets/` no longer matches `manifest.json`, so the scaffold would ship a file with a missing or unfilled section.
- **`unregistered_assets`**: files in `assets/` that the manifest does not mention. The user adds assets over time, so an unlisted file is a decision. For each, tell the user and ask whether to include it and at what path. If yes, add it to `extra_assets` and plan again.
- **`fresh`**: true when the target is missing, empty, or holds only `.git`. If it is **true**, go straight to step 4. If it is **false**, show `plan_tree`, get a yes before writing anything, then ask about each file whose `status` is `differs`, one file at a time:
  - overwrite or skip, and for `README.md` also **append** (keep the existing text and add the License and Contributing sections it lacks).

  Files that are `new` or `same` need no question. Say what differs so the choice is informed.

## 4. Write

Run `python3 <skill>/scripts/scaffold.py write --values <values.json> --target <dir>`, adding `--overwrite <path>` for each file the user chose to replace and `--append README.md` if they chose that. Any existing file that differs and is not named is left alone. The script rejects an `--overwrite` path that is not one of the scaffold's files, so spell it as `plan` listed it.

## 5. Finish

Print the `summary` field of the result exactly as it is: the file tree, any warnings, skipped and appended files, what is still to write, and which files still contain `TBD`. Stop there. Do not run `git init`, commit, install dependencies, or build.
