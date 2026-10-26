---
name: code-guidelines
description: Explicitly invoked guidelines for repository code changes, refactors, shared configuration and architectural work.
---

# Code guidelines

Use when the user invokes `$code-guidelines` for development work on this repository. Routine chapter transcription, translation, lettering and review follow their own workflow; editing chapter records or page layouts alone does not activate this skill.

## Establish the scope

Tell the user what you are changing and keep them informed during the work. Read the affected ownership boundaries in [architecture](../../architecture.md), then inspect the relevant implementation and its consumers. Read [setup](../../setup.md) when changing dependencies or execution environments, and [workflow](../../workflow.md) when changing commands, persisted records or chapter transitions. Load only the resources relevant to the change.

Identify the requested behavior and the contracts that must remain stable. Preserve unrelated work, including changes already staged or being made by another agent. Follow the existing style and formatting of each affected directory.

## Implement deliberately

- Write descriptive names and flat control flow. Prefer early returns over deep nesting. Comments explain why, non-obvious constraints or maintained invariants; they do not narrate the code. A short local heading can explain an ownership, lifecycle or persistence rule when needed.
- Search for an existing helper before adding logic. Reuse a helper when its contract fits. Extract repeated operations with the same meaning into an intuitive shared owner, without generalizing unrelated cases.
- Work in small, coherent changes. Avoid broad refactors, speculative features and abstractions without a current need. Address the cause of the issue rather than accumulating special cases at callers.
- Keep allocations and dynamic evaluation out of hot paths. Cache repeated work when its lifetime and invalidation are clear. Check the actual cost before introducing a more complex optimization.
- Preserve established file, folder and asset paths. Move or rename them only when the requested change needs it, and update their consumers together. An architecture request permits the restructuring needed for that request; it does not justify unrelated cleanup.
- Preserve behavior, return types and output schemas outside the requested change. When a contract must change, update its callers, stored-data handling and owning documentation together. Do not treat an incidental improvement as permission to break compatibility.

## Verify the affected behavior

Trace downstream consumers of changed helpers, configuration, CLI commands and core abstractions. Check concrete callsites and data use rather than assuming compatibility. For a shared change, include the affected entry points and persistence paths in the verification scope.

Use existing checks and focused runtime verification. Do not create new test suites or harnesses during implementation. Keep disposable probes and scratch artifacts outside the project, and use copies or isolated fixtures when checking chapter mutations. Preserve existing originals, revisions and user edits.

Choose checks that establish the changed behavior. A syntax or import check does not establish that a browser interaction, native render or persisted revision works. Avoid using browser automation/browser subagent and computer use skill. Exercise the relevant operation when available, inspect its result, and report any verification that could not run. Broaden checks when failures or affected consumers justify it.

Update the document that owns a changed contract. Keep engineering guidance here, chapter operation instructions in the workflow, and environment instructions in setup. Use [unslop](../unslop/SKILL.md) for changed documentation, prompts, comments and interface copy. Keep Markdown prose paragraphs on one source line, preserving real lists, tables, code blocks and intentional text breaks.

## Report and hand off

Report what changed, why, what was verified and any remaining limitation. Distinguish implemented behavior from checks actually performed and from user acceptance. Completing a code change does not mark a chapter finished or accept its pages.

Do not commit or push unless the user requested it. When requested, use [commit-pipeline](../commit-pipeline/SKILL.md), which owns submodule updates, local exclusions and the commit process. Do not run that pipeline as part of ordinary implementation or translation work.
