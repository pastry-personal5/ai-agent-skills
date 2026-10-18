#!/usr/bin/env python3
"""Regression tests for the shared scaffold engine and platform packages. Run: python3 -I evals/test_scaffold.py"""
import datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

WS = Path(__file__).resolve().parent
SKILL = WS.parent
CORE = SKILL / "core"
S = CORE / "scripts" / "scaffold.py"
FIX = WS / "fixtures" / "existing-repo"
TMP = Path(tempfile.mkdtemp(prefix="scaffold-test-"))
ok = True


def run(*args, script=S):
    r = subprocess.run([sys.executable, "-I", str(script), *args], capture_output=True, text=True, cwd=TMP)
    try:
        out = json.loads(r.stdout)
    except Exception:
        out = {"raw": r.stdout, "err": r.stderr}
    return r.returncode, out


base = dict(name="pixel-notes", description="A tiny note app.", stack="Rust", license="Apache-2.0", gui=True,
            gate=["cargo fmt --check", "cargo clippy --all-targets -- -D warnings", "cargo test"],
            commands=[["cargo build", "build"], ["cargo test", "run the tests"]], environment=["Rust via rustup."],
            conventions=["Use default rustfmt."], build_output=["target/"], generated={".gitignore": "target/\n.DS_Store\n"})


def vf(fname, **over):
    d = dict(base)
    d.update(over)
    (TMP / fname).write_text(json.dumps(d))
    return fname


def check(label, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + label + (f"  [{extra}]" if (extra and not cond) else ""))


def rows(p):
    return Path(p).read_text().count("\n| [")


def dangling(root):
    out = []
    for p in Path(root).rglob("*.md"):
        text = re.sub(r"```.*?```", "", p.read_text(), flags=re.S)
        for link in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if not link.startswith(("http://", "https://", "mailto:")) and not (p.parent / link).exists():
                out.append(f"{p.relative_to(root)} -> {link}")
    return out


def skill_copy(name):
    """A private copy of the skill (scripts + assets), so tests can break an asset without touching the real one."""
    dst = TMP / name
    shutil.copytree(SKILL, dst, ignore=shutil.ignore_patterns("evals", ".DS_Store"))
    return dst


# ---------------------------------------------------------------- GUI project

vf("v.json")
rc, plan = run("plan", "--values", "v.json", "--target", "t1")
check("plan on missing dir: fresh, 12 files all new", rc == 0 and plan["fresh"] and len(plan["files"]) == 12 and {f["status"] for f in plan["files"]} == {"new"})
check("plan writes nothing", not (TMP / "t1").exists())
rc, w = run("write", "--values", "v.json", "--target", "t1")
t1 = TMP / "t1"
agents1 = (t1 / "AGENTS.md").read_text()
check("write: 12 written", rc == 0 and len(w["written"]) == 12, w)
check("CLAUDE.md is exactly @AGENTS.md", (t1 / "CLAUDE.md").read_text() == "@AGENTS.md\n")
check("LICENSE is the bundled Apache text", (t1 / "LICENSE").read_bytes() == (CORE / "assets/licenses/Apache-2.0.txt").read_bytes())
check("no {{ left", not any("{{" in p.read_text(errors="ignore") for p in t1.rglob("*") if p.is_file() and p.name != "LICENSE"))
g = "`cargo fmt --check`, `cargo clippy --all-targets -- -D warnings`, and `cargo test`"
check("gate identical in AGENTS.md and process doc", g in agents1 and f"The gate passes: {g}." in (t1 / "docs/development-process.md").read_text())
cg = (t1 / "docs/contribution-guide.md").read_text()
check("contribution guide: gate block, Status, neutral example, PR section still TBD",
      "```sh\ncargo fmt --check\ncargo clippy" in cg and "Status: Active" in cg and "## Pull requests\n\nTBD" in cg)
process_doc = (t1 / "docs/development-process.md").read_text()
check("process doc: phase and milestone numbers may change", "Phase and milestone numbers may change" in process_doc)
check("process doc: no commit body ID rule", "commit message bodies" not in process_doc)
stale_plan_names = re.findall(r"milestone-(?:NN|\d{2})-(?:overview|architecture)\.md", process_doc)
themed_plan_names = re.findall(r"milestone-(?:NN|\d{2})-<theme>-(overview|architecture)\.md", process_doc)
check("process doc: milestone plan docs are named with <theme> in the table, template, and instructions",
      not stale_plan_names and themed_plan_names.count("overview") >= 3 and themed_plan_names.count("architecture") >= 3,
      (stale_plan_names, themed_plan_names))
check("GUI: Product scope and Interaction model lines in Decided",
      "- **Product scope:** [product-behavior.md](docs/product-behavior.md).\n- **Interaction model:**" in agents1)
check("GUI: Project paragraph links the product scope doc", "overview and [docs/product-behavior.md](docs/product-behavior.md) for product scope." in agents1)
check("empty product-behavior asset becomes a stub", "docs/product-behavior.md" in w["stubbed"], w["stubbed"])
check("index lists 6 docs", rows(t1 / "docs/README.md") == 6)
check("GUI scaffold has no dangling relative links", not dangling(t1), dangling(t1))
check("TBD files include stub and guide", {"docs/product-behavior.md", "docs/contribution-guide.md"} <= set(w["tbd_files"]), w["tbd_files"])
check("summary: roadmap and TBD heading, no tooling note", "docs/roadmap.md" in w["summary"] and "contain `TBD`" in w["summary"] and "Tooling chosen" not in w["summary"], w["summary"])
rc, w2 = run("write", "--values", "v.json", "--target", "t1")
check("second write is a no-op, TBD files still reported", rc == 0 and not w2["written"] and not w2["skipped"] and len(w2["unchanged"]) == 12 and w2["tbd_files"])

# template content
rule = "Ask before building on an undecided item"
check("AGENTS.md states the undecided-item rule once, in Agent workflow",
      agents1.count(rule) == 1 and agents1.index(rule) < agents1.index("## Decided"), agents1.count(rule))
check("AGENTS.md does not assume ripgrep", "rg -n" not in agents1 and "| rg" not in agents1)

# ---------------------------------------------------------------- non-GUI project

vf("v2.json", name="logslice", stack="Python", gui=False, gate=["ruff format --check .", "ruff check .", "pytest"], build_output=["__pycache__/"])
rc, w = run("write", "--values", "v2.json", "--target", "t2")
t2 = TMP / "t2"
agents2 = (t2 / "AGENTS.md").read_text()
check("non-GUI: no ux docs, no GUI line", rc == 0 and not list(t2.glob("docs/ux-*")) and "Interaction model" not in agents2 and "{{GUI" not in agents2)
check("non-GUI: no product-behavior doc", not (t2 / "docs/product-behavior.md").exists())
check("non-GUI: AGENTS.md has no product scope line or link", "product-behavior" not in agents2 and "Product scope" not in agents2 and "product scope" not in agents2)
check("non-GUI scaffold has no dangling relative links", not dangling(t2), dangling(t2))
check("non-GUI index has 2 docs", rows(t2 / "docs/README.md") == 2)
check("no blank line left where the GUI lines were", "- **Technical stack:** Python.\n- **License:**" in agents2)

# ---------------------------------------------------------------- existing repo: skip, append, overwrite

shutil.copytree(FIX, TMP / "t3")
vf("v3.json", name="site-notes", description="A static site generator for personal notes.", stack="TypeScript", gui=False)
rc, plan = run("plan", "--values", "v3.json", "--target", "t3")
st = {f["dest"]: f["status"] for f in plan["files"]}
check("existing repo: not fresh, README differs, AGENTS new", rc == 0 and not plan["fresh"] and st["README.md"] == "differs" and st["AGENTS.md"] == "new", st)
check("plan_tree marks existing vs new", "(exists, differs)" in plan["plan_tree"] and "(existing, not part of the scaffold)" in plan["plan_tree"])
rc, w = run("write", "--values", "v3.json", "--target", "t3")
check("default skips README and leaves it untouched", w["skipped"] == ["README.md"] and (TMP / "t3/README.md").read_text() == (FIX / "README.md").read_text())
idx = (TMP / "t3/docs/README.md").read_text()
check("glossary indexed with its own summary line", "[glossary.md](glossary.md) | Terms used across the site-notes project" in idx, idx)
check("glossary and src/index.ts untouched", (TMP / "t3/src/index.ts").read_text() == "export const answer = 42;\n" and (TMP / "t3/docs/glossary.md").read_bytes() == (FIX / "docs/glossary.md").read_bytes())
check("summary lists the skipped README", "Skipped because they already existed" in w["summary"] and "`README.md`" in w["summary"])
rc, w = run("write", "--values", "v3.json", "--target", "t3", "--append", "README.md")
rd = (TMP / "t3/README.md").read_text()
check("append keeps the original and adds License + Contributing", rc == 0 and w["appended"] == ["README.md"] and "My hand-written readme" in rd and "## License" in rd and "## Contributing" in rd, rd)
check("append summary names both sections", "added the License and Contributing sections" in w["summary"], w["summary"])
rc, w = run("write", "--values", "v3.json", "--target", "t3", "--append", "README.md")
check("append twice does nothing more", not w["appended"] and rd == (TMP / "t3/README.md").read_text())
shutil.copytree(FIX, TMP / "t4")
rc, w = run("write", "--values", "v3.json", "--target", "t4", "--overwrite", "README.md")
check("overwrite replaces README", w["overwritten"] == ["README.md"] and (TMP / "t4/README.md").read_text().startswith("# site-notes\n\nA static site generator"))

(TMP / "t9").mkdir()
(TMP / "t9/README.md").write_text("# x\n\n### License\n\nMIT-ish\n")
rc, w = run("write", "--values", "v3.json", "--target", "t9", "--append", "README.md")
rd9 = (TMP / "t9/README.md").read_text()
check("append: a '### License' heading counts as a License section", rc == 0 and w["appended"] == ["README.md"] and "\n## License" not in rd9 and "## Contributing" in rd9, rd9)
check("append summary names only the section it added", "added the Contributing section." in w["summary"] and "License and" not in w["summary"], w["summary"])
(TMP / "t10").mkdir()
(TMP / "t10/README.md").write_text("# x\n\n## License\n\nMine.\n\n## Contributing\n\nMine too.\n")
rc, w = run("write", "--values", "v3.json", "--target", "t10", "--append", "README.md")
check("append: README with both sections is left alone", rc == 0 and not w["appended"] and (TMP / "t10/README.md").read_text().endswith("Mine too.\n"), w)

rc, o = run("write", "--values", "v3.json", "--target", "t11", "--overwrite", "readme.md")
check("--overwrite naming a file the scaffold does not produce: rc 2, nothing written",
      rc == 2 and "readme.md" in o["errors"][0] and not (TMP / "t11").exists(), o)

# ---------------------------------------------------------------- big existing repos: the plan and the summary stay short

(TMP / "big/node_modules/pkg").mkdir(parents=True)
for i in range(300):
    (TMP / f"big/node_modules/pkg/f{i}.js").write_text("x\n")
(TMP / "big/src").mkdir()
(TMP / "big/src/index.ts").write_text("export {};\n")
(TMP / "big/docs").mkdir()
(TMP / "big/docs/glossary.md").write_text("# Glossary\n\nStatus: Active\n\nTerms.\n")
rc, p = run("plan", "--values", "v3.json", "--target", "big")
tree = p["plan_tree"].splitlines()
check("plan_tree collapses a many-file directory to one line that shows its file count",
      rc == 0 and len(tree) < 30 and any(l.endswith("node_modules/  (300 files, existing, not part of the scaffold)") for l in tree), (len(tree), tree[:6]))
check("plan_tree collapses a one-file directory and says '1 file'", any("src/" in l and "(1 file," in l for l in tree) and not any("index.ts" in l for l in tree), tree)
check("plan_tree still lists the existing files in docs/, where the scaffold writes", any("glossary.md" in l and "(existing, not part of the scaffold)" in l for l in tree), tree)
rc, w = run("write", "--values", "v3.json", "--target", "big")
check("the write summary is short too, with the collapsed directory's file count",
      rc == 0 and len(w["summary"].splitlines()) < 40 and "node_modules/  (300 files)" in w["summary"], (len(w["summary"].splitlines()), w["summary"][:300]))

(TMP / "arch/docs/archive").mkdir(parents=True)
(TMP / "arch/docs/archive/old-plan.md").write_text("# Old plan\n\nStatus: Archived\n\nSuperseded.\n")
(TMP / "arch/docs/notes.md").write_text("# Notes\n\nStatus: Active\n\nLive notes.\n")
rc, w = run("write", "--values", "v3.json", "--target", "arch")
idx = (TMP / "arch/docs/README.md").read_text()
check("the docs index lists live docs but leaves out docs/archive/", rc == 0 and "[notes.md](notes.md)" in idx and "old-plan.md" not in idx, idx)

# ---------------------------------------------------------------- rejected input: rc 2, JSON errors, nothing written

rc, o = run("write", "--values", vf("v5.json", license="GPL-3.0"), "--target", "t5")
check("licence with no bundled text: rc 2, nothing written", rc == 2 and "GPL-3.0" in o["errors"][0] and not (TMP / "t5").exists(), o)
bad = dict(base)
bad.pop("gate")
(TMP / "v6.json").write_text(json.dumps(bad))
rc, o = run("plan", "--values", "v6.json", "--target", "t6")
check("missing gate: rc 2", rc == 2 and "gate" in o["errors"][0], o)
rc, o = run("write", "--values", "v.json", "--target", "t1", "--append", "AGENTS.md")
check("--append AGENTS.md rejected", rc == 2)
rc, o = run("write", "--values", vf("v7.json", license="MPL-2.0", generated={".gitignore": "x\n", "LICENSE": "Mozilla Public License Version 2.0\n"}), "--target", "t7")
check("a licence with no bundled text uses values.generated.LICENSE", rc == 0 and (TMP / "t7/LICENSE").read_text() == "Mozilla Public License Version 2.0\n", o)
(TMP / "t8/.git").mkdir(parents=True)
rc, p = run("plan", "--values", "v.json", "--target", "t8")
check("a dir holding only .git counts as fresh", p["fresh"])

for label, over in {
    "extra_assets src that does not exist": dict(extra_assets=[{"src": "nope.md", "dest": "docs/x.md"}]),
    "extra_assets entry without dest": dict(extra_assets=[{"src": "contribution-guide.md"}]),
    "extra_assets that is not a list": dict(extra_assets={"src": "a", "dest": "b"}),
    "commands entry that is not two strings": dict(commands=[["cargo build", 3]]),
    "gate that is not a list of strings": dict(gate=["cargo test", 5]),
    "generated that is not an object": dict(generated=[".gitignore"]),
}.items():
    rc, o = run("plan", "--values", vf("vbad.json", **over), "--target", "tbad")
    check(f"{label}: rc 2 with JSON errors", rc == 2 and isinstance(o.get("errors"), list) and o["errors"], o)

for label, extra, why in [
    ("dest with ..", {"src": "contribution-guide.md", "dest": "../escaped.md"}, "escaped.md"),
    ("absolute dest", {"src": "contribution-guide.md", "dest": str(TMP / "abs-escaped.md")}, "abs-escaped.md"),
    ("src with ..", {"src": "../SKILL.md", "dest": "docs/skill.md"}, None),
    ("dest that collides with a scaffold file", {"src": "contribution-guide.md", "dest": "AGENTS.md"}, None),
]:
    rc, o = run("write", "--values", vf("vx.json", extra_assets=[extra]), "--target", "tx")
    check(f"extra_assets {label}: rc 2, nothing written", rc == 2 and o.get("errors") and not (TMP / "tx").exists() and (why is None or not (TMP / why).exists()), o)
rc, o = run("write", "--values", vf("vx.json", extra_assets=[{"src": "contribution-guide.md", "dest": "docs/extra-guide.md"}]), "--target", "tx")
check("extra_assets inside the target still works", rc == 0 and (TMP / "tx/docs/extra-guide.md").is_file() and "[extra-guide.md]" in (TMP / "tx/docs/README.md").read_text(), o)

(TMP / "tz/LICENSE").mkdir(parents=True)
rc, o = run("write", "--values", "v.json", "--target", "tz")
check("a blocked file means rc 2 before any file is written", rc == 2 and sorted(p.name for p in (TMP / "tz").iterdir()) == ["LICENSE"], sorted(p.name for p in (TMP / "tz").iterdir()))

if os.geteuid() != 0:
    (TMP / "tro").mkdir()
    (TMP / "tro").chmod(0o555)
    rc, o = run("write", "--values", "v.json", "--target", "tro")
    (TMP / "tro").chmod(0o755)
    check("I/O error while writing: rc 1 with JSON errors, not a traceback", rc == 1 and o.get("errors"), (rc, o))

rc, p = run("plan", "--values", str(CORE / "references/values.example.json"), "--target", "texample")
check("references/values.example.json is a valid values file", rc == 0 and p["warnings"] == [] and not (TMP / "texample").exists(), p)

# ---------------------------------------------------------------- bundled licences: canonical text, holder and year filled in

year = str(datetime.date.today().year)
BUNDLED = {  # id: (what the file starts with, what it ends with), written by hand from the SPDX text
    "MIT": (f"MIT License\n\nCopyright (c) {year} Ada Example\n\nPermission is hereby granted", "USE OR OTHER DEALINGS IN THE SOFTWARE.\n"),
    "BSD-2-Clause": (f"Copyright (c) {year} Ada Example\n\nRedistribution and use", "OF THE POSSIBILITY OF SUCH DAMAGE.\n"),
    "BSD-3-Clause": (f"Copyright (c) {year} Ada Example.\n\nRedistribution and use", "OF THE POSSIBILITY OF SUCH DAMAGE.\n"),
    "ISC": (f"ISC License\n\nCopyright {year} Ada Example\n\nPermission to use, copy, modify", "USE OR PERFORMANCE OF THIS SOFTWARE.\n"),
}
for lid, (head, tail) in BUNDLED.items():
    rc, o = run("write", "--values", vf(f"vl-{lid}.json", license=lid, license_holder="Ada Example"), "--target", f"tl-{lid}")
    lic = (TMP / f"tl-{lid}/LICENSE").read_text() if rc == 0 else ""
    check(f"bundled {lid}: LICENSE is the canonical text with the holder and year filled in",
          lic.startswith(head) and lic.endswith(tail) and "{{" not in lic and not re.search(r"<(year|owner|copyright holders)>", lic), (rc, lic[:120], o))
PINNED = {  # sha256 of each bundled template: the legal wording must not change by accident. Update with assets/licenses/README.md
    "MIT": "aeaae84c5db6dd072b23d98e1cb448268c2905a2601c0b16f471ae7409998f1f",
    "BSD-2-Clause": "48cf5c3b88780027c3142ea8ad74938027be1a37027cc46c00b3a52e1ea822d6",
    "BSD-3-Clause": "fbbae4ed873993b7115262bc4d233a50b26cefe57161d21c96283c260f3431f5",
    "ISC": "3b47c4aaec0bf5a46d33437eaf247e9cacf6c83017e336bc4c3bf41f4038c679",
}
drift = [i for i, h in PINNED.items() if hashlib.sha256((CORE / f"assets/licenses/{i}.txt.tmpl").read_bytes()).hexdigest() != h]
check("bundled licence templates are word for word the pinned SPDX texts", not drift, drift)
bsd2, bsd3 = [(TMP / f"tl-{i}/LICENSE").read_text() if (TMP / f"tl-{i}/LICENSE").is_file() else "" for i in ("BSD-2-Clause", "BSD-3-Clause")]
check("BSD-3-Clause has the non-endorsement clause and BSD-2-Clause does not",
      "3. Neither the name of the copyright holder" in bsd3 and bsd2 and "Neither the name" not in bsd2)
rc, o = run("write", "--values", vf("vl-year.json", license="MIT", license_holder="Ada Example", license_year=2020), "--target", "tl-year")
check("license_year replaces the current year", rc == 0 and (TMP / "tl-year/LICENSE").read_text().startswith("MIT License\n\nCopyright (c) 2020 Ada Example\n"), o)
rc, o = run("plan", "--values", vf("vl-nohold.json", license="BSD-3-Clause"), "--target", "tl-nohold")
check("a bundled licence that needs a holder, with none given: rc 2 naming license_holder, nothing written",
      rc == 2 and "license_holder" in o["errors"][0] and not (TMP / "tl-nohold").exists(), o)
rc, o = run("plan", "--values", vf("vl-badhold.json", license="MIT", license_holder="Ada\nExample"), "--target", "tl-badhold")
check("license_holder with a line break: rc 2", rc == 2 and "license_holder" in o["errors"][0], o)

# ---------------------------------------------------------------- thin adapters, self-contained packages, and released version metadata

root = SKILL.parent
if (root / "README.md").is_file() and (root / "CHANGELOG.md").is_file():
    package_root = TMP / "packages"
    package_run = subprocess.run(
        [sys.executable, "-I", str(SKILL / "tools/build_packages.py"), str(package_root)],
        capture_output=True, text=True)
    codex = package_root / "codex/quick-scaffolding"
    claude = package_root / "claude/quick-scaffolding"
    check("package builder creates self-contained Codex and Claude distributions",
          package_run.returncode == 0 and (codex / "SKILL.md").is_file() and
          (claude / ".claude-plugin/plugin.json").is_file() and
          (claude / "commands/quick-scaffolding.md").is_file(), package_run.stderr)
    package_version = (SKILL / "VERSION").read_text().strip()
    plugin_manifest = json.loads((claude / ".claude-plugin/plugin.json").read_text())
    check("Claude plugin manifest carries the canonical package version",
          plugin_manifest.get("name") == "quick-scaffolding" and plugin_manifest.get("version") == package_version,
          plugin_manifest)
    shared = ["assets/manifest.json", "references/values.example.json", "references/workflow.md", "scripts/scaffold.py"]
    check("both packages contain byte-identical shared workflow, assets, references, and engine",
          all((codex / p).read_bytes() == (claude / p).read_bytes() for p in shared), shared)
    packaged_junk = [p for package in (codex, claude) for p in package.rglob("*")
                     if p.name == "__pycache__" or p.suffix in (".pyc", ".pyo") or p.name == ".DS_Store"]
    check("packages exclude caches and local filesystem metadata", not packaged_junk, packaged_junk)
    codex_rc, codex_plan = run("plan", "--values", "v.json", "--target", "package-codex-target",
                               script=codex / "scripts/scaffold.py")
    claude_rc, claude_plan = run("plan", "--values", "v.json", "--target", "package-claude-target",
                                 script=claude / "scripts/scaffold.py")
    check("both packaged engines resolve their bundled assets and references",
          codex_rc == claude_rc == 0 and not codex_plan["warnings"] and not claude_plan["warnings"],
          (codex_plan, claude_plan))
    skill_text = (codex / "SKILL.md").read_text()
    frontmatter = skill_text.split("---", 2)[1]
    check("Codex SKILL.md frontmatter uses only name and description",
          set(re.findall(r"^([a-z_-]+):", frontmatter, flags=re.M)) == {"name", "description"}, frontmatter)
    openai_yaml = (codex / "agents/openai.yaml").read_text()
    check("Codex metadata names the skill and keeps explicit-only invocation",
          'display_name: "Quick Scaffolding"' in openai_yaml and
          'default_prompt: "Use $quick-scaffolding ' in openai_yaml and
          "allow_implicit_invocation: false" in openai_yaml, openai_yaml)
    check("Codex adapter contains no Claude-only argument or invocation metadata",
          "$ARGUMENTS" not in skill_text and "disable-model-invocation" not in skill_text)
    claude_command = (claude / "commands/quick-scaffolding.md").read_text()
    check("Claude adapter uses native arguments and manual-only invocation",
          "$ARGUMENTS" in claude_command and "argument-hint:" in claude_command and
          "disable-model-invocation: true" in claude_command and "${CLAUDE_PLUGIN_ROOT}" in claude_command,
          claude_command)
    second_run = subprocess.run(
        [sys.executable, "-I", str(SKILL / "tools/build_packages.py"), str(package_root)],
        capture_output=True, text=True)
    check("package builder refuses a non-empty output directory", second_run.returncode == 1 and "must be empty" in second_run.stderr)
    readme_text = (root / "README.md").read_text()
    check("README builds both adapters and installs Codex through the current user skill root",
          "tools/build_packages.py" in readme_text and "~/.agents/skills/quick-scaffolding" in readme_text and
          "--plugin-dir" in readme_text)
    check("README does not duplicate the package version", package_version not in readme_text)

# ---------------------------------------------------------------- asset drift is reported (on a private copy of the skill)

cp = skill_copy("skill-copy")
cs = cp / "core" / "scripts" / "scaffold.py"
rc, p = run("plan", "--values", "v.json", "--target", "tc1", script=cs)
check("unmodified skill copy: no warnings, nothing unregistered", rc == 0 and p["warnings"] == [] and p["unregistered_assets"] == [], p)
(cp / "core" / "assets" / "zz-probe.md").write_text("# probe\n")
rc, p = run("plan", "--values", "v.json", "--target", "tc1", script=cs)
check("unregistered asset is reported", p["unregistered_assets"] == ["zz-probe.md"], p["unregistered_assets"])
(cp / "core" / "assets" / "zz-probe.md").unlink()
manifest = cp / "core" / "assets" / "manifest.json"
manifest.write_text(manifest.read_text().replace("The gate passes: TBD", "The gate passes: NOPE"))
rc, p = run("plan", "--values", "v.json", "--target", "tc1", script=cs)
check("a broken replace anchor shows up in plan warnings", rc == 0 and any("NOPE" in x for x in p["warnings"]), p["warnings"])
rc, w = run("write", "--values", "v.json", "--target", "tc2", script=cs)
check("a broken replace anchor shows up in the write summary", rc == 0 and "Warnings" in w["summary"] and "NOPE" in w["summary"], w["summary"])

shutil.rmtree(TMP, ignore_errors=True)
print("\nALL PASSED" if ok else "\nSOME FAILED")
sys.exit(0 if ok else 1)
