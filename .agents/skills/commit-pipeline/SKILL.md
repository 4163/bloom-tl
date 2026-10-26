---
name: commit-pipeline
description: Commit or push repository changes through the submodule update and exclusion pipeline, or write commit and pull request messages.
---

# Commit pipeline

Use this skill when asked to commit, push, update the commit pipeline, or prepare commit and pull request messages. Message-only requests do not run Git mutations. A commit request does not authorize a push unless the user also requested it.

## Entry points

The runner is [scripts/commit-pipeline.py](scripts/commit-pipeline.py). Run it from the repository root with Python. The root `Makefile` provides `make push`, `make push-x` and `make push-a` shortcuts. Direct Python invocation does not require Make.

For an agent following this skill directly, first run `python -I -B .agents/skills/commit-pipeline/scripts/commit-pipeline.py prepare --update`, then perform the commit workflow below with raw Git commands. This updates initialized submodules from their configured upstream, reapplies `.exclusion-config` and handles configured remote file downloads. Review the changed engine gitlink and its effect on dependency setup before committing it. Do not treat an upstream update as proof that the new engine still works with the parent adapters.

The full `push` runner performs that preparation, stages changes and invokes the configured AI committer. `push -x` uses terminal prompts for manual commit messages; `push -a` collects additional user context for the AI committer. Inspect the runner's configured CLI and model before using the full runner. These dependencies are needed only for that path, not for direct agent commits or chapter translation.

When invoked with the `[COMMIT_PIPELINE]` handoff marker, preparation has already run. Do not invoke the runner or Make shortcuts again. Continue with raw Git commands to avoid recursion.

`prepare` without `--update` initializes the parent's recorded submodule versions and reapplies exclusions without staging, committing or pushing. Environment setup uses this form. Both forms preserve generated and untracked submodule files; pruning stops when tracked submodule files have local changes.

## Commit workflow

After preparation, do not edit, create or delete working files while committing. Staging, unstaging, commits and an authorized push are permitted. If a fix is needed, report it and return to the implementation task before preparing commits again. This restriction does not prevent editing the pipeline when the user asks to change it.

1. Review `git status`, the working diff and the staged diff. Account for any changes that were already staged before the request.
2. Check the actual change scope and relevant project documentation. Do not assume all pending work belongs in this commit.
3. Check `.gitignore` coverage and staged contents. Keep credentials, personal paths and private chapter inputs, transcripts, handoffs, edits and archives out of commits unless the user specifically chose to publish those files. Unstage inappropriate files; do not silently edit them during the commit pass. Stop before publishing if sensitive contents remain unresolved.
4. Group independent changes into logical commits. Keep related implementation and documentation together. Prioritize the user's description of their intent when deciding the groups.
5. Stage only the current group and inspect `git diff --cached`. Include the updated gitlink only after checking the engine change and the parent operations it affects.
6. Commit each group using the message rules below. Do not rewrite history or create unnecessary micro-commits.
7. Push only when requested. If no remote is configured, report that fact instead of inventing a destination.

## Commit messages

Write from the staged diff and verified context. Use a concise past-tense header, preferably under 50 characters. The body explains what changed and why, including non-obvious implementation choices. Use a paragraph or simple bullets when they help. Keep the whole message in past tense.

## Pull requests

Write from the branch's full change against its base. Follow an established repository title convention when one exists; otherwise use a concise title describing the outcome. Lead the body with the user-visible problem and resulting behavior, explain relevant changes and tradeoffs, then report checks actually performed. Do not invent validation or include abandoned approaches unless they explain a current decision.

When asked to provide message text, put the header or title and the body in separate copyable `text` code blocks. Follow [unslop](../unslop/SKILL.md) for plain prose. Keep Markdown paragraphs on one source line and avoid em dashes, puffery and arbitrary indentation.
