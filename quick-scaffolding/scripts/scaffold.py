#!/usr/bin/env python3
"""Apply the quick-scaffolding manifest to a target directory.

  scaffold.py plan  --values values.json --target DIR
  scaffold.py write --values values.json --target DIR [--overwrite PATH ...] [--append README.md]

`plan` writes nothing. It reports, as JSON, whether the target is fresh, what each file would be
(new / same / differs), assets that the manifest does not mention, and any errors.

`write` writes new files and leaves every existing file that differs alone, unless that path is
named with --overwrite (replace it) or --append (README.md only: add the missing License and
Contributing sections). It prints a JSON result whose "summary" is the text to show the user.

Standard library only. Exit status 2 means nothing was written; "errors" says why.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ASSETS = SKILL / "assets"
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
IGNORED = {".git", ".DS_Store"}
GUI_DECIDED = ("- **Interaction model:** [ux-gui.md](docs/ux-gui.md). Component vocabulary is in "
               "[ux-terms.md](docs/ux-terms.md) and the layout containment model in "
               "[ux-information-architecture.md](docs/ux-information-architecture.md).")


class Fail(Exception):
    pass


# ---------------------------------------------------------------- values

def load_values(path):
    try:
        v = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise Fail(f"cannot read values file {path}: {e}")
    need = {"name": str, "description": str, "stack": str, "license": str, "gui": bool,
            "gate": list, "commands": list, "environment": list, "conventions": list, "build_output": list}
    for key, typ in need.items():
        if not isinstance(v.get(key), typ):
            raise Fail(f"values.{key} is missing or not a {typ.__name__}")
    if not v["gate"] or not all(isinstance(c, str) and c.strip() for c in v["gate"]):
        raise Fail("values.gate must be a non-empty list of command strings")
    if not v["commands"] or not all(isinstance(c, list) and len(c) == 2 for c in v["commands"]):
        raise Fail('values.commands must be a non-empty list of ["command", "comment"] pairs')
    v.setdefault("generated", {})
    v.setdefault("extra_assets", [])
    if not v["generated"].get(".gitignore"):
        raise Fail("values.generated['.gitignore'] is required")
    return v


def prose_list(items):
    t = [f"`{i}`" for i in items]
    if len(t) <= 2:
        return " and ".join(t)
    return ", ".join(t[:-1]) + f", and {t[-1]}"


def commands_block(cmds):
    width = max(len(c) for c, _ in cmds)
    lines = [f"{c.ljust(width)}  # {note}" if note else c for c, note in cmds]
    return "```sh\n" + "\n".join(lines) + "\n```"


def placeholders(v):
    return {
        "NAME": v["name"], "DESCRIPTION": v["description"], "STACK": v["stack"], "LICENSE": v["license"],
        "GATE": prose_list(v["gate"]),
        "GATE_BLOCK": "```sh\n" + "\n".join(v["gate"]) + "\n```",
        "COMMANDS_BLOCK": commands_block(v["commands"]),
        "ENVIRONMENT": "\n".join(f"- {e}" for e in v["environment"]),
        "CONVENTIONS": "\n".join(f"- {c}" for c in v["conventions"]),
        "BUILD_OUTPUT": ", ".join(f"`{b}`" for b in v["build_output"]),
    }


def fill(text, ph):
    return PLACEHOLDER.sub(lambda m: ph.get(m.group(1), m.group(0)), text)


# ---------------------------------------------------------------- README

def readme_sections(v):
    return {
        "## License": f"## License\n\nLicensed under the {v['license']} license. See [LICENSE](LICENSE).\n",
        "## Contributing": "## Contributing\n\nContributors and AI agents: see [AGENTS.md](AGENTS.md) and "
                           "[docs/contribution-guide.md](docs/contribution-guide.md).\n",
    }


def readme(v):
    return f"# {v['name']}\n\n{v['description']}\n\n" + "\n".join(readme_sections(v).values())


# ---------------------------------------------------------------- docs index

def summary_line(text):
    """The first line after the title and the Status line, used as an index description."""
    for line in text.splitlines()[1:]:
        s = line.strip()
        if s and not s.startswith(("#", "Status:")):
            return s
    return ""


def doc_rows(files, index_text, target):
    """One table row per doc that will exist in docs/ after the run, manifest docs first."""
    docs = [d for d in files if d.startswith("docs/") and d.endswith(".md") and d != "docs/README.md"]
    kept = sorted(str(p.relative_to(target)) for p in (target / "docs").rglob("*.md")
                  if p.name != "README.md" and str(p.relative_to(target)) not in files) if (target / "docs").is_dir() else []
    rows = []
    for d in docs + kept:
        text = index_text.get(d)
        if text is None:
            text = summary_line(files[d]["data"].decode("utf-8") if d in files else (target / d).read_text(encoding="utf-8", errors="replace"))
        rel = d[len("docs/"):]
        rows.append(f"| [{rel}]({rel}) | {text.replace('|', chr(92) + '|')} |")
    return "\n".join(rows)


# ---------------------------------------------------------------- render

def render(v, target):
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    ph = placeholders(v)
    files, index_text, warnings = {}, {}, []

    def put(dest, text=None, data=None, kind="manifest"):
        files[dest] = {"data": data if data is not None else text.encode("utf-8"), "kind": kind}

    for e in manifest["entries"]:
        if e["when"] == "gui" and not v["gui"]:
            continue
        kind = "manifest"
        if "content" in e:
            text = e["content"]
        else:
            text = (ASSETS / e["src"]).read_text(encoding="utf-8")
            if not text.strip():
                title = Path(e["dest"]).stem.replace("-", " ").capitalize()
                text = f"# {title}\n\nStatus: Active\n\n{e.get('index', 'TBD')}\n\nTBD\n"
                kind = "stub"
        for r in e.get("replace", []):
            n = text.count(r["find"])
            if n == 1:
                text = text.replace(r["find"], r["with"])
            else:
                warnings.append(f"{e['dest']}: replace anchor {r['find']!r} matched {n} times, so it was left unchanged")
        if e["dest"] == "AGENTS.md":
            text = text.replace("{{GUI_DECIDED}}\n", (GUI_DECIDED + "\n") if v["gui"] else "")
        put(e["dest"], text, kind=kind)
        if "index" in e:
            index_text[e["dest"]] = e["index"]

    for x in v["extra_assets"]:
        put(x["dest"], (ASSETS / x["src"]).read_text(encoding="utf-8"), kind="extra")

    put("README.md", readme(v), kind="generated")
    put(".gitignore", v["generated"][".gitignore"], kind="generated")
    lic = manifest.get("licenses", {}).get(v["license"])
    if lic:
        put("LICENSE", data=(ASSETS / lic).read_bytes(), kind="license")
    elif v["generated"].get("LICENSE"):
        put("LICENSE", v["generated"]["LICENSE"], kind="generated")
    else:
        raise Fail(f"no bundled text for license {v['license']!r}: put the full text in values.generated['LICENSE']")

    ph["DOC_ROWS"] = doc_rows(files, index_text, target)
    left = []
    for dest, f in files.items():
        if f["kind"] == "license":
            continue
        text = fill(f["data"].decode("utf-8"), ph)
        f["data"] = text.encode("utf-8")
        left += [f"{dest}: {{{{{m}}}}}" for m in sorted(set(PLACEHOLDER.findall(text)))]
    if left:
        raise Fail("unfilled placeholders: " + "; ".join(left))
    return manifest, files, warnings


# ---------------------------------------------------------------- state

def is_fresh(target):
    return not target.exists() or all(c.name in IGNORED for c in target.iterdir())


def status_of(target, dest, data):
    p = target / dest
    if p.is_dir():
        raise Fail(f"{dest} exists and is a directory")
    if not p.exists():
        return "new"
    return "same" if p.read_bytes() == data else "differs"


def unregistered(manifest, v):
    known = {e["src"] for e in manifest["entries"] if "src" in e} | {x["src"] for x in v["extra_assets"]}
    out = []
    for p in sorted(ASSETS.rglob("*")):
        rel = p.relative_to(ASSETS).as_posix()
        if p.is_file() and p.name not in IGNORED and rel != "manifest.json" and not rel.startswith("licenses/") and rel not in known:
            out.append(rel)
    return out


def tree_text(root_name, notes):
    """ASCII tree of {relative path: note}."""
    tree = {}
    for path in notes:
        node = tree
        for part in Path(path).parts:
            node = node.setdefault(part, {})
    lines = [f"{root_name}/"]

    def walk(node, prefix, parent):
        names = sorted(node, key=lambda n: (not node[n], n.lower()))
        for i, name in enumerate(names):
            last = i == len(names) - 1
            rel = f"{parent}/{name}" if parent else name
            note = notes.get(rel, "")
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}{'/' if node[name] else ''}{('  ' + note) if note else ''}")
            if node[name]:
                walk(node[name], prefix + ("    " if last else "│   "), rel)

    walk(tree, "", "")
    return "\n".join(lines)


def existing_files(target):
    if not target.is_dir():
        return []
    return sorted(p.relative_to(target).as_posix() for p in target.rglob("*")
                  if p.is_file() and not (set(p.relative_to(target).parts) & IGNORED))


# ---------------------------------------------------------------- commands

def cmd_plan(a):
    v = load_values(a.values)
    target = Path(a.target).expanduser().resolve()
    manifest, files, warnings = render(v, target)
    listing = [{"dest": d, "status": status_of(target, d, f["data"]), "kind": f["kind"]} for d, f in files.items()]
    notes = {p: "(existing, not part of the scaffold)" for p in existing_files(target)}
    notes.update({i["dest"]: {"new": "(new)", "same": "(exists, identical)", "differs": "(exists, differs)"}[i["status"]] for i in listing})
    return {"fresh": is_fresh(target), "files": listing, "unregistered_assets": unregistered(manifest, v),
            "warnings": warnings, "plan_tree": tree_text(target.name, notes)}


def cmd_write(a):
    v = load_values(a.values)
    target = Path(a.target).expanduser().resolve()
    overwrite, append = set(a.overwrite or []), set(a.append or [])
    if append - {"README.md"}:
        raise Fail("--append only supports README.md")
    manifest, files, warnings = render(v, target)
    res = {k: [] for k in ("written", "overwritten", "appended", "skipped", "unchanged", "stubbed")}
    for dest, f in files.items():
        st = status_of(target, dest, f["data"])
        path = target / dest
        if st == "same":
            res["unchanged"].append(dest)
        elif st == "differs" and dest in append:
            existing = path.read_text(encoding="utf-8")
            missing = [body for head, body in readme_sections(v).items() if head not in existing]
            if missing:
                path.write_text(existing.rstrip("\n") + "\n\n" + "\n".join(missing), encoding="utf-8")
                res["appended"].append(dest)
            else:
                res["unchanged"].append(dest)
        elif st == "differs" and dest not in overwrite:
            res["skipped"].append(dest)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f["data"])
            res["overwritten" if st == "differs" else "written"].append(dest)
            if f["kind"] == "stub":
                res["stubbed"].append(dest)

    # every scaffold file the repo now holds, not only those written this run, so a repeat run still reports them
    tbd = sorted(d for d in files if d not in res["skipped"] and (target / d).is_file() and b"TBD" in (target / d).read_bytes())
    todo = [s for s in manifest.get("still_to_write", [])
            if (s["when"] == "always" or v["gui"]) and not (target / s["path"]).exists()]
    notes = {p: "" for p in existing_files(target)}
    notes.update({d: "(existing, kept)" for d in res["skipped"]})
    notes.update({d: "(existing, README sections appended)" for d in res["appended"]})
    notes.update({d: "(stub: the asset was empty)" for d in res["stubbed"]})

    out = [tree_text(target.name, notes), ""]
    if res["skipped"]:
        out += ["Skipped because they already existed:", *[f"- `{d}`: kept as it was; the scaffold's version differs." for d in res["skipped"]], ""]
    if res["appended"]:
        out += ["Appended to:", *[f"- `{d}`: added the License and Contributing sections." for d in res["appended"]], ""]
    out += ["Still to write:", *([f"- `{s['path']}`: {s['reason']}" for s in todo] or ["- Nothing."]), ""]
    out += ["Scaffold files that still contain `TBD`:", *([f"- `{d}`" for d in tbd] or ["- None."]), ""]
    if not v.get("tooling_from_user"):
        out += [f"Tooling chosen by this skill, not by you: {v['stack']}; gate: {prose_list(v['gate'])}. "
                "Change it in AGENTS.md, docs/development-process.md and docs/contribution-guide.md if you prefer other tools."]
    res.update(warnings=warnings, still_to_write=[s["path"] for s in todo], tbd_files=tbd, summary="\n".join(out))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "write"):
        p = sub.add_parser(name)
        p.add_argument("--values", required=True)
        p.add_argument("--target", required=True)
        if name == "write":
            p.add_argument("--overwrite", action="append", metavar="PATH")
            p.add_argument("--append", action="append", metavar="PATH")
    a = ap.parse_args()
    try:
        out = (cmd_plan if a.cmd == "plan" else cmd_write)(a)
    except Fail as e:
        print(json.dumps({"errors": [str(e)]}, indent=2))
        sys.exit(2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
