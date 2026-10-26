---
name: familiarize
description: Use at the very start of a session to familiarize yourself with this repository before proceeding with actual work.
argument-hint: "<low|docs|skim|surface|normal> [task to prepare for]"
---

# Familiarize

Three tiers control how deep you go. The user specifies the tier, or you infer it from the request. Default is docs level.

## Tiers

### Low / docs

Read agent guidelines and project documentation only. No codebase exploration.

- `.agents/setup.md`
- `.agents/workflow.md`
- `.agents/architecture.md`
- `.agents/skills/manga-translation/SKILL.md`
- `.agents/skills/lettering/SKILL.md`
- `.agents/skills/unslop/SKILL.md`
- `README.md` (if present)
- `PROMPT.md`

Do not read source files, config files, or directory trees.

### Skim / surface

Read guidelines (everything in Low) plus a surface-level pass over the codebase. No deep dives.

- Walk the root directory tree and note the layout.
- Read package manifests, dependency manifests, or config files (if present).
- Skim entry points and main scripts, but do not open individual helper modules or trace execution flow.

Do not use subagents.

### Normal

Everyday orientation. Rules plus layout plus who owns what.

- Build on the lower tiers. Docs holds the guidelines, skim holds the layout, configs, and entry points.
- Read top-level scripts and configuration files only as far as skim has not covered.
- Note the conventions in place: naming, folder layout, error handling, style. New work fits the codebase, not the other way around.
- Stop at module doors. Do not open individual helper modules, utility scripts, or internal handlers to learn them. Do not trace call chains or data flow. Depth beyond this is task-scoped.

## Subagents

If the harness supports subagents, delegate parts of the Normal tier to run in parallel (directory mapping, manifest reading, subsystem exploration). Have each subagent report a short summary, not raw output.

If the harness does not support subagents, do the work yourself. Never use any pseudo subagents skill as a substitute.
