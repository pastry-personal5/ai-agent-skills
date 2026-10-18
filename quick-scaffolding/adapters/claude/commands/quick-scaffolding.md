---
description: Scaffold repository metadata and process documentation
argument-hint: [target-dir] [project details]
disable-model-invocation: true
---

# Quick scaffolding for Claude Code

Arguments: $ARGUMENTS

Treat the first argument as the target only when it looks like a path: it contains `/`, starts with `.` or `~`, or names an existing directory. Otherwise use the current working directory. Treat all other arguments and the conversation as interview answers.

Before acting, read `${CLAUDE_PLUGIN_ROOT}/references/workflow.md` completely and follow it. In that workflow, `<skill-dir>` is `${CLAUDE_PLUGIN_ROOT}`.
