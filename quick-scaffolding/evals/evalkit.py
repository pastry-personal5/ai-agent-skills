#!/usr/bin/env python3
"""Eval kit for the quick-scaffolding skill.

  python3 evalkit.py setup <iteration-dir>     create run folders, fixtures, metadata, agent prompts, evals.json
  python3 evalkit.py grade <iteration-dir>     grade every run-N folder into grading.json
  python3 evalkit.py flatten <iteration-dir>   build the viewer-friendly outputs/ folder of every run
  python3 evalkit.py smoke <scratch-dir>       no agent: scaffold each eval with canned values via scaffold.py, then grade it
  python3 evalkit.py export                    rewrite evals.json from EVALS and the checks

Run layout:  <iteration>/eval-<id>-<name>/<config>/run-1/{repo/, outputs/, notes.md, final_message.md,
             timing.json, grading.json, agent_prompt.md, eval_metadata.json}
"""
import datetime, filecmp, json, re, shutil, subprocess, sys
from pathlib import Path

WS = HERE = Path(__file__).resolve().parent
SKILL = WS.parent
CONFIGS = ("with_skill", "without_skill")
UX = ("ux-terms.md", "ux-gui.md", "ux-information-architecture.md")

MIT_TEXT = """MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# `smoke` is what a correct agent would put in the values file for that eval (used by the no-agent `smoke` command).
EVALS = [
    dict(id=1, name="gui-rust-empty", project="pixel-notes",
         desc="A tiny macOS note-taking app with a Qt Widgets window.",
         stack="Rust", gui=True, license="Apache-2.0", holder=None, fixture=None, git_init=False,
         tooling="rustfmt, clippy and cargo test", gate_tools=["cargo fmt", "clippy", "cargo test"],
         smoke=dict(gate=["cargo fmt --check", "cargo clippy --all-targets -- -D warnings", "cargo test"],
                    commands=[["cargo build", "build"], ["cargo test", "run the tests"]],
                    environment=["Rust via rustup."], conventions=["Use default rustfmt."],
                    build_output=["target/"], gitignore="target/\n.DS_Store\n")),
    dict(id=2, name="python-cli-mit-git-only", project="logslice",
         desc="A command-line tool that slices large log files by time range.",
         stack="Python", gui=False, license="MIT", holder="Ada Example", fixture=None, git_init=True,
         tooling="ruff and pytest", gate_tools=["ruff", "pytest"],
         smoke=dict(gate=["ruff format --check .", "ruff check .", "pytest -q"],
                    commands=[["pytest -q", "run the tests"], ["ruff check .", "lint"]],
                    environment=["Python 3.12 or newer."], conventions=["Format with ruff."],
                    build_output=["__pycache__/", ".venv/"], gitignore="__pycache__/\n.venv/\n.DS_Store\n")),
    dict(id=3, name="existing-repo-conflicts", project="site-notes",
         desc="A static site generator for personal notes.",
         stack="TypeScript", gui=False, license="Apache-2.0", holder=None, fixture="existing-repo", git_init=False,
         tooling="Biome for formatting and linting, and Vitest", gate_tools=["biome", "vitest"],
         smoke=dict(gate=["npx biome format .", "npx biome lint .", "npx vitest run"],
                    commands=[["npx vitest run", "run the tests"], ["npx biome lint .", "lint"]],
                    environment=["Node.js 22 or newer."], conventions=["Format with Biome."],
                    build_output=["node_modules/", "dist/"], gitignore="node_modules/\ndist/\n.DS_Store\n")),
]

IGNORE_PATTERN = {"Rust": "target", "Python": "__pycache__", "TypeScript": "node_modules"}


def read(p):
    p = Path(p)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None


def strip_fences(t):
    return re.sub(r"```.*?```", "", t, flags=re.S)


def files_of(repo):
    return sorted(p for p in Path(repo).rglob("*") if p.is_file() and ".git" not in p.relative_to(repo).parts)


# ---------------------------------------------------------------- prompts

def license_line(ev):
    return ev["license"] + (f" (copyright holder: {ev['holder']})" if ev["holder"] else "")


def invocation(ev, target):
    return (f"/quick-scaffolding {target}\n\nProject name: {ev['project']}\nDescription: {ev['desc']}\n"
            f"Stack: {ev['stack']}\nHas a GUI: {'yes' if ev['gui'] else 'no'}\nTooling: {ev['tooling']}\n"
            f"License: {license_line(ev)}")


def baseline_request(ev, target):
    existing = ("\nThe directory already has a README.md, docs/glossary.md and src/index.ts. Do not overwrite or "
                "change any existing file." if ev["fixture"] else "")
    return (f"Set up the starting files for a new repo at {target}.\n\nProject: {ev['project']}. {ev['desc']}\n"
            f"Stack: {ev['stack']}. {'It has a GUI.' if ev['gui'] else 'It has no GUI.'} Tooling: {ev['tooling']}. "
            f"License: {license_line(ev)}.\n\n"
            "I want README.md, LICENSE, .gitignore, an AGENTS.md for AI coding agents, a CLAUDE.md that pulls in "
            "AGENTS.md, and a docs/ folder for design, process and contribution docs." + existing)


def agent_prompt(ev, config, run):
    target = run / "repo"
    log = (f"Nobody can answer questions in this run. If you would stop to ask the user something, do not stop. "
           f"Append two lines to `{run}/notes.md`: `PROMPT[<kind>]: <what you would show the user>` then "
           f"`ASSUMED: <the answer you assume>`. Use kind `interview` for a question about the project, "
           f"`plan-approval` for asking permission to write a planned tree, and `conflict:<relative path>` for a "
           f"file that already exists. Assume: plan approval = yes; every file conflict = skip (keep the existing file). "
           f"Do not log a prompt for anything the user's message already answers.")
    if config == "with_skill":
        return (f"You are running one test of a Claude Code skill by following its instructions by hand.\n\n"
                f"The skill is user-invocation-only, so do not use the Skill tool. Read `{SKILL}/SKILL.md` and follow it "
                f"step by step. The skill's base directory is `{SKILL}` (its assets/ folder is there). Do not modify "
                f"anything inside that directory.\n\nThe user typed this, so treat everything after the command name as "
                f"`$ARGUMENTS`:\n\n```\n{invocation(ev, target)}\n```\n\n{log}\n\n"
                f"Write the scaffold only into `{target}`. Save the skill's values file at `{run}/values.json` (outside the "
                f"target). Your final reply must be exactly what the skill tells you to print at the end. Also save "
                f"that same text to `{run}/final_message.md`.\n")
    return (f"A user asks you for this:\n\n{baseline_request(ev, target)}\n\nWork only inside `{target}`; do not look at "
            f"other directories on this machine, and do not run git init, commit, install or build. {log} "
            f"When you finish, reply with a short summary and save that same summary to `{run}/final_message.md`.\n")


# ---------------------------------------------------------------- checks

def checks(ev, run):
    """Return [(text, passed, evidence)]. Tolerates a missing run, so it can also list assertion texts."""
    repo, run = Path(run) / "repo", Path(run)
    out = []

    def add(text, passed, evidence=""):
        out.append((text, bool(passed), evidence))

    agents, docs = read(repo / "AGENTS.md"), repo / "docs"
    # "nothing bad happened" checks only count once something was actually scaffolded
    built = any((repo / n).is_file() for n in ("AGENTS.md", "CLAUDE.md", "LICENSE", ".gitignore"))

    need = ["## Decided", "## Undecided", "## Documentation", "Ask before building on an undecided item"]
    miss = [n for n in need if not agents or n not in agents]
    add("AGENTS.md has Decided, Undecided and Documentation sections and the 'Ask before building on an undecided item' rule",
        agents is not None and not miss, f"missing: {miss}" if agents else "AGENTS.md not found")

    cl = read(repo / "CLAUDE.md")
    add("CLAUDE.md contains exactly the one line @AGENTS.md", cl is not None and cl.strip() == "@AGENTS.md",
        repr(cl) if cl is not None else "CLAUDE.md not found")

    lic = read(repo / "LICENSE")
    if ev["license"] == "Apache-2.0":
        same = (repo / "LICENSE").is_file() and filecmp.cmp(repo / "LICENSE", SKILL / "assets/licenses/Apache-2.0.txt", shallow=False)
        add("LICENSE is the bundled Apache-2.0 text, byte for byte", same, "identical" if same else "missing or different")
    else:
        year, h = str(datetime.date.today().year), ev["holder"]
        good = lic is not None and lic.lstrip().startswith("MIT License") and year in lic and h in lic
        add("LICENSE is the MIT license with the current year and the copyright holder named in the user's message", good,
            f"expected year {year} and holder {h!r}; head: {(lic or '')[:80]!r}")

    rd = read(repo / "README.md")
    if not ev["fixture"]:  # in the conflict eval the existing README is kept on purpose, so its content is not checked here
        add("README.md names the project and points to AGENTS.md and docs/contribution-guide.md",
            rd is not None and ev["project"] in rd and "AGENTS.md" in rd and "contribution-guide.md" in rd,
            "README.md not found" if rd is None else "checked name, AGENTS.md, contribution-guide.md")

    gi = read(repo / ".gitignore")
    pat = IGNORE_PATTERN[ev["stack"]]
    add(f".gitignore exists and ignores the {ev['stack']} build output ({pat})", gi is not None and pat in gi,
        ".gitignore not found" if gi is None else f"pattern {pat!r} {'found' if pat in gi else 'absent'}")

    dp = read(docs / "development-process.md")
    gate = None
    if dp:
        m = re.search(r"The gate passes: (.+?)\.?\s*$", dp, flags=re.M)
        gate = m.group(1).strip() if m else None
    add("docs/development-process.md gate line is filled in and identical to the gate in AGENTS.md",
        bool(gate) and gate != "TBD" and agents is not None and gate in agents, f"gate line: {gate!r}")
    add("docs/development-process.md says to put milestone IDs in commit bodies, not PR titles",
        bool(dp) and "not in PR titles" in dp, "line present" if dp and "not in PR titles" in dp else "line absent")

    cg = read(docs / "contribution-guide.md")
    cmds, why = [], ""
    if cg:
        m = re.search(r"## Required validation.*?```[a-z]*\n(.*?)```", cg, flags=re.S)
        cmds = [l.strip() for l in (m.group(1).splitlines() if m else []) if l.strip()]
        why = f"validation commands: {cmds}"
    add("docs/contribution-guide.md has a Status line, the stack's gate commands under Required validation, and no leftover TV-project example",
        bool(cg) and "Status: Active" in cg and len(cmds) >= 2 and agents is not None and all(c in agents for c in cmds)
        and "mDNS" not in cg, why or "contribution-guide.md not found")

    pm = read(docs / "product-behavior.md")
    if ev["gui"]:
        good = bool(pm) and pm.lstrip().startswith("# ") and "Status:" in pm and len(pm.strip()) > 30 \
            and agents is not None and "docs/product-behavior.md" in agents
    else:
        good = built and pm is None and agents is not None and "product-behavior" not in agents
    add("docs/product-behavior.md exists, with a title, a Status line, summary text and a link from AGENTS.md, exactly when the app has a GUI",
        good, "not found" if pm is None else f"{len(pm)} chars")

    present = [u for u in UX if (docs / u).is_file()]
    add("The three ux-*.md docs are present exactly when the app has a GUI", built and ((set(present) == set(UX)) if ev["gui"] else not present),
        f"present: {present}; gui={ev['gui']}")

    fl = files_of(repo) if repo.is_dir() else []
    left = [str(p.relative_to(repo)) for p in fl if "{{" in (read(p) or "")]
    add("No unfilled {{placeholder}} remains in any scaffolded file", built and not left, f"files with placeholders: {left}")

    dangling = []
    for p in fl:
        if p.suffix == ".md":
            for t in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", strip_fences(read(p) or "")):
                if t.startswith(("http://", "https://", "mailto:")):
                    continue
                if not (p.parent / t).resolve().exists():
                    dangling.append(f"{p.relative_to(repo)} -> {t}")
    add("No relative markdown link points at a file that does not exist", built and not dangling, f"dangling: {dangling}")

    idx = read(docs / "README.md")
    if idx is None:
        add("docs/README.md indexes every doc in docs/ exactly once, and nothing else", False, "docs/README.md not found")
    else:
        listed = re.findall(r"\|\s*\[[^\]]*\]\(([^)]+)\)", idx)
        have = sorted(str(p.relative_to(docs)) for p in docs.rglob("*.md") if p.name != "README.md")
        add("docs/README.md indexes every doc in docs/ exactly once, and nothing else",
            sorted(listed) == have, f"listed={sorted(listed)} have={have}")

    low = (agents or "").lower()
    absent = [t for t in ev["gate_tools"] if t.lower() not in low]
    add("AGENTS.md uses the tools the user named for the gate", agents is not None and not absent, f"absent: {absent}")

    forbid = ["CXX-Qt", "file manager", "Folder Item"] + ([] if ev["stack"] == "Rust" else ["cargo", "clippy", "rustfmt", "Qt"])
    hit = [w for w in forbid if agents and w.lower() in agents.lower()]
    add(f"AGENTS.md carries no dual-pane-specific or wrong-stack content for a {ev['stack']} project", agents is not None and not hit,
        f"found: {hit}")

    junk = [n for n in ("target", "node_modules", "__pycache__", "Cargo.lock", "dist", "build") if (repo / n).exists()]
    git_ok = True
    if (repo / ".git").exists():
        r = subprocess.run(["git", "-C", str(repo), "rev-list", "--all", "--count"], capture_output=True, text=True)
        git_ok = ev["git_init"] and r.stdout.strip() in ("0", "")
    add("No commit was made and no build or dependency output was created", built and not junk and git_ok,
        f"artifacts: {junk}; git ok: {git_ok}")

    fm, notes = read(run / "final_message.md"), read(run / "notes.md") or ""
    add("The final message shows the file tree, names docs/roadmap.md as still to write, and lists files that still contain TBD",
        bool(fm) and "roadmap.md" in fm and "TBD" in fm and "AGENTS.md" in fm and "Tooling chosen" not in fm,
        "final_message.md not found" if fm is None else "checked roadmap.md, TBD, AGENTS.md, no tooling-choice note")

    add("No interview question was asked, because the user's message already answered all of them",
        built and "PROMPT[interview]" not in notes, f"interview prompts: {notes.count('PROMPT[interview]')}")

    plan = notes.count("PROMPT[plan-approval]")
    conf = re.findall(r"PROMPT\[conflict:([^\]]*)\]", notes)
    if ev["fixture"]:
        add("Exactly one plan-approval prompt and one conflict prompt, for README.md only", plan == 1 and conf == ["README.md"],
            f"plan-approval={plan}; conflicts={conf}")
        fx = WS / "fixtures" / ev["fixture"]
        same = lambda rel: (repo / rel).is_file() and (fx / rel).read_bytes() == (repo / rel).read_bytes()
        add("The existing README.md is unchanged", same("README.md"), "byte-identical" if same("README.md") else "changed or missing")
        add("The existing docs/glossary.md and src/index.ts are unchanged", same("docs/glossary.md") and same("src/index.ts"),
            f"glossary={same('docs/glossary.md')} index.ts={same('src/index.ts')}")
        row = [l for l in (idx or "").splitlines() if "glossary.md" in l]
        add("The docs index has a row for glossary.md using the doc's own summary line",
            bool(row) and "Terms used across the site-notes project" in row[0], f"row: {row[:1]}")
    else:
        add("A fresh directory needed no plan-approval or conflict prompt", built and plan == 0 and not conf,
            f"plan-approval={plan}; conflicts={conf}")
    return out


# ---------------------------------------------------------------- commands

def eval_dirs(it):
    return sorted(d for d in Path(it).glob("eval-*") if d.is_dir())


def ev_of(edir):
    return next(e for e in EVALS if edir.name.startswith(f"eval-{e['id']}-"))


def export_evals():
    (SKILL / "evals").mkdir(exist_ok=True)
    (SKILL / "evals" / "evals.json").write_text(json.dumps({
        "skill_name": "quick-scaffolding",
        "evals": [{"id": e["id"], "prompt": invocation(e, "<target-dir>"),
                   "expected_output": "Repo meta files, docs and AGENTS.md scaffolded per the manifest, with every check in evals/evalkit.py passing.",
                   "files": ([f"evals/fixtures/{e['fixture']}"] if e["fixture"] else []),
                   "expectations": [t for t, _, _ in checks(e, WS / "nonexistent")]} for e in EVALS]}, indent=2) + "\n")


def cmd_setup(it):
    it = Path(it).resolve()
    for ev in EVALS:
        edir = it / f"eval-{ev['id']}-{ev['name']}"
        texts = [t for t, _, _ in checks(ev, edir / "nonexistent")]
        for cfg in CONFIGS:
            run = edir / cfg / "run-1"
            if run.exists():
                shutil.rmtree(run)
            (run / "outputs").mkdir(parents=True)
            repo = run / "repo"
            if ev["fixture"]:
                shutil.copytree(WS / "fixtures" / ev["fixture"], repo)
            else:
                repo.mkdir()
            if ev["git_init"]:
                subprocess.run(["git", "init", "-q", str(repo)], check=True)
            prompt = invocation(ev, repo) if cfg == "with_skill" else baseline_request(ev, repo)
            meta = {"eval_id": ev["id"], "eval_name": ev["name"], "prompt": prompt, "assertions": texts}
            (run / "eval_metadata.json").write_text(json.dumps(meta, indent=2))
            (run / "agent_prompt.md").write_text(agent_prompt(ev, cfg, run))
        (edir / "eval_metadata.json").write_text(json.dumps(
            {"eval_id": ev["id"], "eval_name": ev["name"], "prompt": invocation(ev, "<target-dir>"), "assertions": texts}, indent=2))
    export_evals()
    print("setup done:", it)


def runs(it):
    for edir in eval_dirs(it):
        for cfg in CONFIGS:
            run = edir / cfg / "run-1"
            if run.is_dir():
                yield ev_of(edir), cfg, run


def cmd_grade(it):
    failed = 0
    for ev, cfg, run in runs(it):
        res = checks(ev, run)
        passed = sum(1 for _, p, _ in res if p)
        total = len(res)
        (run / "grading.json").write_text(json.dumps({
            "expectations": [{"text": t, "passed": p, "evidence": e} for t, p, e in res],
            "summary": {"passed": passed, "failed": total - passed, "total": total,
                        "pass_rate": round(passed / total, 4) if total else 0.0},
            "execution_metrics": {}, "user_notes_summary": {"uncertainties": [], "needs_review": [], "workarounds": []}}, indent=2))
        failed += total - passed
        print(f"{run.parent.parent.name:36} {cfg:13} {passed}/{total}")
        for t, p, e in res:
            if not p:
                print(f"    FAIL: {t}\n          {e}")
    return failed


def scaffold(*args):
    r = subprocess.run([sys.executable, "-I", str(SKILL / "scripts" / "scaffold.py"), *args], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout or "{}")


def cmd_smoke(it):
    """Run the skill's script the way a correct agent would, then grade the result with the same checks as a real run."""
    it = Path(it).resolve()
    if it.exists() and any(it.iterdir()):  # never delete a directory that may hold agent runs
        sys.exit(f"smoke: {it} is not empty; pass a new or empty directory")
    for ev in EVALS:
        run = it / f"eval-{ev['id']}-{ev['name']}" / "with_skill" / "run-1"
        repo = run / "repo"
        (run / "outputs").mkdir(parents=True)
        if ev["fixture"]:
            shutil.copytree(HERE / "fixtures" / ev["fixture"], repo)
        else:
            repo.mkdir()
        if ev["git_init"]:
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
        sm = ev["smoke"]
        gen = {".gitignore": sm["gitignore"]}
        if ev["license"] == "MIT":
            gen["LICENSE"] = MIT_TEXT.format(year=datetime.date.today().year, holder=ev["holder"])
        values = {"name": ev["project"], "description": ev["desc"], "stack": ev["stack"], "license": ev["license"],
                  "gui": ev["gui"], "gate": sm["gate"], "commands": sm["commands"], "environment": sm["environment"],
                  "conventions": sm["conventions"], "build_output": sm["build_output"], "generated": gen}
        (run / "values.json").write_text(json.dumps(values, indent=2))
        rc, plan = scaffold("plan", "--values", str(run / "values.json"), "--target", str(repo))
        if rc or plan.get("warnings") or plan.get("unregistered_assets") or plan["fresh"] == bool(ev["fixture"]):
            sys.exit(f"smoke: unexpected plan for eval {ev['id']}: {plan}")
        notes = []
        if not plan["fresh"]:  # what the user is asked, and what the answers are assumed to be
            notes.append("PROMPT[plan-approval]: show the plan tree\nASSUMED: yes")
            notes += [f"PROMPT[conflict:{f['dest']}]: overwrite, skip or append?\nASSUMED: skip"
                      for f in plan["files"] if f["status"] == "differs"]
        (run / "notes.md").write_text("\n".join(notes) + "\n")
        rc, res = scaffold("write", "--values", str(run / "values.json"), "--target", str(repo))
        if rc:
            sys.exit(f"smoke: write failed for eval {ev['id']}: {res}")
        (run / "final_message.md").write_text(res["summary"] + "\n")
    failed = cmd_grade(it)
    print("smoke:", "all checks passed" if not failed else f"{failed} check(s) failed")
    return failed


def cmd_flatten(it):
    for ev, cfg, run in runs(it):
        out, repo = run / "outputs", run / "repo"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        fl = files_of(repo) if repo.is_dir() else []
        (out / "tree.txt").write_text("\n".join(str(p.relative_to(repo)) for p in fl) + "\n")
        for p in fl:
            name = "__".join(p.relative_to(repo).parts)
            name = name if name.endswith((".md", ".txt", ".json")) else name.lstrip(".") + ".txt"
            shutil.copyfile(p, out / name)
        for extra in ("notes.md", "final_message.md"):
            if (run / extra).is_file():
                shutil.copyfile(run / extra, out / extra)
    print("flatten done:", it)


if __name__ == "__main__":
    cmds = {"setup": cmd_setup, "grade": cmd_grade, "flatten": cmd_flatten, "smoke": cmd_smoke}
    if sys.argv[1:] == ["export"]:
        export_evals()
        sys.exit(0)
    if len(sys.argv) != 3 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    sys.exit(1 if cmds[sys.argv[1]](sys.argv[2]) else 0)
