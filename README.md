# ai-agent-skills

Agent skills for Codex CLI and Claude Code. See the [changelog](CHANGELOG.md).

## quick-scaffolding

Gives a new repo the same starting files every time, so people and agents find the same things in the same places.

```text
Codex:      $quick-scaffolding [target-dir]
Claude Code: /quick-scaffolding [target-dir]
```

It asks for the project name, stack, whether the app has a GUI, license and tooling, then writes:

- `README.md`, `LICENSE`, `.gitignore`
- `AGENTS.md`, plus a one-line `CLAUDE.md` that imports it
- `docs/`: development process, contribution guide and a docs index
- For GUI apps: product-behavior and `ux-*` docs

On a repo that already has these files, it shows a plan first. For each file that differs, you choose to overwrite or skip it, or to append to `README.md`. It never creates source code, runs `git init`, commits or builds.

The skill only runs when you invoke it. It needs Python 3 (standard library only).

The repository has one shared workflow, script, template set, and reference set under `quick-scaffolding/core/`. Thin adapters under `quick-scaffolding/adapters/` add only the native metadata and invocation behavior for each CLI. The package builder copies the shared core into two self-contained distributions.

### Build the packages

Build into a new or empty directory:

```sh
package_dir="$(mktemp -d)"
python3 -I quick-scaffolding/tools/build_packages.py "$package_dir"
```

### Install for Codex CLI

Copy the generated Codex package into Codex's user skills directory, then start a new Codex session:

```sh
mkdir -p ~/.agents/skills
cp -R "$package_dir/codex/quick-scaffolding" ~/.agents/skills/quick-scaffolding
```

### Install for Claude Code

Load the generated Claude Code plugin and invoke `/quick-scaffolding`:

```sh
claude --plugin-dir "$package_dir/claude/quick-scaffolding"
```

### Test

From the repo root:

```sh
python3 -I quick-scaffolding/evals/test_scaffold.py
python3 -I quick-scaffolding/evals/evalkit.py smoke "$(mktemp -d)/smoke"
```

Agent evals are described in [quick-scaffolding/evals/README.md](quick-scaffolding/evals/README.md).
