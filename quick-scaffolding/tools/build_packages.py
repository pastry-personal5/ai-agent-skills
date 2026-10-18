#!/usr/bin/env python3
"""Build self-contained Codex and Claude Code packages from shared sources."""
import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
ADAPTERS = ROOT / "adapters"
COMMON_DIRS = ("assets", "references", "scripts")
COPY_IGNORE = shutil.ignore_patterns("__pycache__", "*.py[co]", ".DS_Store")


def copy_common(destination):
    for name in COMMON_DIRS:
        shutil.copytree(CORE / name, destination / name, ignore=COPY_IGNORE)
    shutil.copy2(CORE / "workflow.md", destination / "references" / "workflow.md")


def build(output):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    codex = output / "codex" / "quick-scaffolding"
    codex.mkdir(parents=True)
    shutil.copy2(ADAPTERS / "codex" / "SKILL.md", codex / "SKILL.md")
    shutil.copytree(ADAPTERS / "codex" / "agents", codex / "agents")
    copy_common(codex)

    claude = output / "claude" / "quick-scaffolding"
    claude.mkdir(parents=True)
    shutil.copytree(ADAPTERS / "claude" / ".claude-plugin", claude / ".claude-plugin")
    shutil.copytree(ADAPTERS / "claude" / "commands", claude / "commands")
    copy_common(claude)
    manifest_path = claude / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return codex, claude


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="an absent or empty output directory")
    args = parser.parse_args(argv)
    try:
        codex, claude = build(args.output)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Codex: {codex}")
    print(f"Claude Code: {claude}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
