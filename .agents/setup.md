# Environment setup

The parent workflow uses Python 3.11 or newer and the standard library. The pinned engine's `pyproject.toml` requires Python 3.12 and owns its dependency versions. Node.js 20 or newer runs the PSD tools. Git initializes the submodule; FFmpeg assembles and checks the native rasters. No desktop image editor is required to render, export or import PSDs.

## Parent tools

Check `python --version`, `git --version`, `node --version`, `npm --version` and `ffmpeg -version`. Install missing tools from their official distribution or a trusted package manager for the user's OS. Verify executables afterward. Do not replace working system installations just to create a chapter.

Run from the repository root:

```powershell
python -I -B .agents/skills/commit-pipeline/scripts/commit-pipeline.py prepare
npm ci
node --input-type=module -e "import './tools/psd.mjs'; console.log('PSD tools ready')"
python -I -B manga.py --help
```

The populated `node_modules` directory alone is not an install check; the module import above must succeed. The commit-pipeline's `prepare` command initializes the parent's recorded gitlink and applies `.exclusion-config` without staging, committing or pushing. It uses Git sparse checkout to omit upstream tests, CI, website sources, development reports and binary release builders locally. The engine's `pyproject.toml`, `uv.lock`, license, runtime modules, fonts, dictionaries, usage guides and backend installer remain available. Pruning stops if tracked submodule files have local changes; preserve those changes before retrying.

To adjust the local checkout, edit `.exclusion-config` and rerun the same `prepare` command. Entries are submodule-relative paths or Git ignore patterns, one per line under the submodule's path section. Omitted files remain in the pinned Git history. `git -C manga-translator-ui sparse-checkout disable` restores the complete checkout when needed; preparation reapplies the exclusions. Generated files, installed dependencies and chapter work are not pruned.

When the user later requests a commit or push, [commit-pipeline](skills/commit-pipeline/SKILL.md) uses `prepare --update` to advance submodules from their configured upstream and prune before the commit workflow. Its `push` runner does this automatically. Review and verify any engine update before recording its new gitlink. Ordinary chapter setup uses `prepare` without `--update` and keeps the recorded engine version.

## Complete engine environment

Install uv if absent. Its project sync installs the engine's own locked dependencies, including Qt, OCR, inpainting and the selected compute backend. Use one backend group from the pinned `pyproject.toml`. CPU is the portable default. Choose a GPU group only after checking the machine and its compatible driver. Do not combine the mutually exclusive CPU, CUDA, ROCm and Metal groups.

On PowerShell, this creates an isolated full engine environment in `.runtime/engine`:

```powershell
$taskPreviousUvEnvironment = $env:UV_PROJECT_ENVIRONMENT
try {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.runtime/engine'
    uv sync --project manga-translator-ui --python 3.12 --no-default-groups --group cpu --locked
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $taskPreviousUvEnvironment
}
$taskEnginePython = Join-Path (Get-Location) '.runtime/engine/Scripts/python.exe'
```

On Unix, use `.runtime/engine/bin/python` and set `UV_PROJECT_ENVIRONMENT` for the sync command. These options follow uv's [environment configuration](https://docs.astral.sh/uv/concepts/projects/config/) and [locked sync](https://docs.astral.sh/uv/concepts/projects/sync/). A failed locked sync needs investigation of the reported platform or package error; do not silently change upstream versions or substitute a partial environment.

An older `.runtime/lettering` environment may support retained-page lettering. It is not evidence that fresh extraction and model-based cleanup are installed. A virtual environment moved with the repository may need recreation at its new path. Do not delete the old environment while another operation is using it.

Verify the interpreter and native entry point:

```powershell
& $taskEnginePython -c "import sys, torch, cv2, onnxruntime, PyQt6, transformers, ultralytics; print(sys.version); print('CUDA available:', torch.cuda.is_available())"
Push-Location manga-translator-ui
try { & $taskEnginePython -B -m manga_translator --help } finally { Pop-Location }
```

Use this exact interpreter for all `manga.py engine` commands. The profiles default to CPU processing. Per-page cleanup settings can select a compatible device. Model weights are downloaded by the native engine on first use. Tell the user when a model download starts and report progress. A help command verifies imports, not model execution; inspect the first real extraction and cleanup results.

## Fonts, archives and review

Check the actual dialogue, prose and credit fonts before rendering, following the lettering skill. Segoe Print and Arial are not guaranteed on every OS. Do not silently replace a missing font.

ZIP extraction can use Python's archive tools. For RAR or other formats, use the engine's archive support or an available archive utility, checking its backend before extraction. Preserve the supplied archive and extract copies without re-encoding scans. Inspect page ordering and chapter boundaries before init.

The agent launches or reuses the review app and presents it to the user. Launch from the repository with:

```powershell
python -I -B manga.py serve --port 8765
```

Use the printed `http://127.0.0.1:8765/` address. Reuse a running server for this workspace. If another workspace owns that port, choose another port and give the user its URL. The app updates after imports and revisions; a local file URL is not the review interface.
