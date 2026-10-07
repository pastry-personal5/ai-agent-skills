# ai-agent-skills

Agent skills for Claude Code. Current version: 1.0.0. See the [changelog](CHANGELOG.md).

## quick-scaffolding

Gives a new repo the same starting files every time, so people and agents find the same things in the same places.

```
/quick-scaffolding [target-dir]
```

It asks for the project name, stack, whether the app has a GUI, license and tooling, then writes:

- `README.md`, `LICENSE`, `.gitignore`
- `AGENTS.md`, plus a one-line `CLAUDE.md` that imports it
- `docs/`: development process, contribution guide and a docs index
- For GUI apps: product-behavior and `ux-*` docs

On a repo that already has these files, it shows a plan first. For each file that differs, you choose to overwrite or skip it, or to append to `README.md`. It never creates source code, runs `git init`, commits or builds.

The skill only runs when you invoke it. It needs Python 3 (standard library only).

### Install

Link or copy the skill folder into your skills directory:

```sh
ln -s "$PWD/quick-scaffolding" ~/.claude/skills/quick-scaffolding
```

### Test

From the repo root:

```sh
python3 -I quick-scaffolding/evals/test_scaffold.py
python3 -I quick-scaffolding/evals/evalkit.py smoke "$(mktemp -d)/smoke"
```

Agent evals are described in [quick-scaffolding/evals/README.md](quick-scaffolding/evals/README.md).
