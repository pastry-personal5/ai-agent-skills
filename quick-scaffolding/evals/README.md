# Evals and tests

Everything needed to test the skill lives here, so a fresh clone can reproduce the results. Run all commands from the repo root. Use `python3 -I` so the interpreter does not import stray modules from the working directory.

| File | What it is |
|---|---|
| `test_scaffold.py` | Unit and regression tests for `scripts/scaffold.py` and the templates. Fast, no agent. |
| `evalkit.py` | Builds eval runs for agents, grades their output, and runs the no-agent smoke check. |
| `evals.json` | The eval prompts and expectations. Generated from `evalkit.py`; do not edit by hand. |
| `fixtures/existing-repo/` | A repo with a hand-written README, a glossary doc and a source file, for the conflict eval. |

## Everyday checks (no agent)

```sh
python3 -I quick-scaffolding/evals/test_scaffold.py
python3 -I quick-scaffolding/evals/evalkit.py smoke "$(mktemp -d)/smoke"
```

`smoke` scaffolds each eval with the values a correct agent would write, then grades the result with the same checks as a real run. It proves the script, templates and checks agree. It does not test the agent following `SKILL.md`. `smoke` refuses a directory that is not empty, so it can never overwrite agent runs. Both commands exit non-zero on any failure.

## Testing the skill with an agent

```sh
python3 -I quick-scaffolding/evals/evalkit.py setup quick-scaffolding-workspace/iteration-N
```

`setup` creates one folder per eval and configuration (`with_skill`, `without_skill`) with the agent prompt, metadata and a seeded repo. Run an agent in each folder, then:

```sh
python3 -I quick-scaffolding/evals/evalkit.py grade   quick-scaffolding-workspace/iteration-N
python3 -I quick-scaffolding/evals/evalkit.py flatten quick-scaffolding-workspace/iteration-N
```

`quick-scaffolding-workspace/` holds run output only and is git-ignored.

## Changing the evals

Edit `EVALS` or `checks()` in `evalkit.py`, then run `python3 -I quick-scaffolding/evals/evalkit.py export` to rewrite `evals.json`.

## What the evals do not cover

- The interview itself (what the agent asks when the arguments are incomplete). All three prompts answer every question.
- The `git config user.name` fallback for MIT and BSD. Eval 2 names the copyright holder in the prompt so it passes on any machine.
- Choosing `--append` or `--overwrite` for a conflict. The unit tests cover the script's handling; no eval has an agent make that choice.
