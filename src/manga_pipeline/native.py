"""Adapt OCR and native Qt lettering. Pixel work stays in upstream tools and FFmpeg."""
import copy
import os
import shutil
import subprocess
from pathlib import Path

from .files import ROOT, SLUG, jsonl, project, read, require, revision_path, sha, write, write_jsonl
from .workflow import check_english, unresolved

ENGINE = ROOT / "manga-translator-ui"


def content(path):
    data = read(path)
    if "regions" in data:
        return data
    values = [value for value in data.values() if isinstance(value, dict) and "regions" in value]
    require(len(values) == 1, f"Expected one native page: {path}")
    return values[0]


def extract_transcript(name, native_directory):
    folder, data = project(name)
    destination = folder / "transcript/raw.jsonl"
    require(not destination.exists(), "Raw transcript already exists. Preserve it; edit checked.jsonl after review.")
    rows, mapping, coverage = [], {}, {}
    native_directory = Path(native_directory).resolve()
    for page in data["pages"]:
        native = native_directory / f"{page['id']}_translations.json"
        require(native.is_file(), f"Missing OCR result, including textless pages: {native}")
        payload = content(native)
        count = 0
        for index, region in enumerate(payload["regions"]):
            text = region.get("text", "").strip()
            if not text:
                continue
            record = f"{name}.p{page['id']}.r{index + 1:03d}"
            rows.append({"id": record, "ja": text})
            mapping[record] = {"page": page["id"], "region": index}
            count += 1
        coverage[page["id"]] = {"records": count, "native_sha256": sha(native)}
    target = folder / "native/ocr"
    require(not target.exists(), "Native OCR snapshot already exists.")
    target.mkdir(parents=True)
    for page in data["pages"]:
        shutil.copy2(native_directory / f"{page['id']}_translations.json", target / f"{page['id']}_translations.json")
    write_jsonl(destination, rows)
    write_jsonl(folder / "transcript/checked.jsonl", rows)
    write(folder / "transcript/coverage.json", coverage)
    write(folder / "native/region-map.json", mapping)
    data["raw_transcript_sha256"] = sha(destination)
    write(folder / "project.json", data)


def run_engine(name, stage, python, run, revision=None, execute=False, pages=None):
    folder, data = project(name)
    if pages:
        require(stage != "extract", "Initial extraction must cover the complete chapter.")
        require(set(pages) <= {page["id"] for page in data["pages"]}, "Unknown page selection.")
        data = dict(data, pages=[page for page in data["pages"] if page["id"] in pages])
    require(bool(SLUG.fullmatch(run)), "Use a lowercase run name.")
    require((ENGINE / "manga_translator/__init__.py").is_file(), "Initialize the manga-translator-ui submodule first.")
    require(Path(python).is_file(), "Provide the Python executable of an installed upstream runtime.")
    destination = folder / "work" / run
    require(not destination.exists(), "Use a new run name to avoid stale native caches.")
    profile = read(ROOT / "profiles" / ("render.json" if stage == "clean" else f"{stage}.json"))
    translations, mapping, english_sha256 = {}, {}, None
    if stage in {"clean", "render"}:
        require(revision is not None, "Cleanup and rendering need --revision.")
        require(not unresolved(folder, {"transcript", "translation"}), "Resolve user decisions before lettering.")
        _, complete_data = project(name)
        translations = {row["id"]: row["en"] for row in check_english(folder, complete_data, revision_path(folder, revision) / "en.jsonl")}
        english_sha256 = sha(revision_path(folder, revision) / "en.jsonl")
        mapping = read(folder / "native/region-map.json")
        require(set(mapping) == set(translations), "Update native mappings for added or removed records before rendering.")
    if stage == "render":
        preflight = read(folder / "native/layouts" / revision / "preflight.json")
        require(preflight.get("english_sha256") == sha(revision_path(folder, revision) / "en.jsonl"), "Native layout review is stale.")
        require(preflight.get("profile_sha256") == sha(ROOT / "profiles/render.json"), "Native render profile changed after review.")
        require(all(preflight.get(key) is True for key in ("masks_checked", "fonts_checked", "layout_checked", "protected_art_checked")),
                "Review native masks, fonts, text fit and protected art before rendering.")
    if not execute:
        return {"engine": str(ENGINE), "python": str(python), "stage": stage,
                "output": str(destination), "revision": revision,
                "note": "Preview only. Add --execute after checking runtime, native layouts and masks."}
    inputs = destination / "input"
    inputs.mkdir(parents=True)
    for page in data["pages"]:
        base = folder / "source/pages" / page["source"]
        if stage == "clean":
            layout = content(folder / "native/layouts" / revision / f"{page['id']}_translations.json")
            source = layout.get("cleanup", {}).get("source")
            if source:
                base = (folder / source).resolve()
                require(base.is_relative_to(folder.resolve()), "Cleanup input must stay inside the project.")
            require("inpainter" in layout.get("cleanup", {}), f"Choose cleanup settings for page {page['id']}.")
        if stage == "render":
            receipt = preflight["bases"][page["id"]]
            base = (folder / receipt["path"]).resolve()
            require(base.is_relative_to(folder.resolve()), "Native base must stay inside the project.")
            require(base.suffix.lower() == ".png" and sha(base) == receipt["sha256"], "Native base changed after review, or is not lossless PNG.")
        image = inputs / (page["id"] + (".png" if stage == "render" else base.suffix.lower()))
        shutil.copy2(base, image)
        if stage == "extract":
            continue
        override = folder / "native/layouts" / revision / f"{page['id']}_translations.json"
        require(override.exists(), f"Prepare a reviewed native layout for page {page['id']}, including textless pages.")
        if stage == "render":
            require(preflight["layout_sha256"][page["id"]] == sha(override), "Native layout changed after review.")
        payload = copy.deepcopy(content(override))
        for record, location in mapping.items():
            if location["page"] != page["id"]:
                continue
            region = payload["regions"][location["region"]]
            text = translations[record]
            require(region.get("translation_raw") == text, f"Update native layout text and wrapping for {record} before rendering.")
            region["target_lang"] = "ENG"
        write(inputs / "manga_translator_work/json" / f"{page['id']}_translations.json", {str(image): payload})
    write(destination / "config.json", profile)
    command = [str(Path(python).resolve()), "-m", "manga_translator", "local", "-i", str(inputs),
               "--config", str(destination / "config.json"), "-o", str(destination / "output")]
    environment = dict(os.environ, PYTHONUTF8="1", QT_QPA_PLATFORM="offscreen", MT_DISABLE_ONNX_GPU="1",
                       OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    write(destination / "run.json", {"command": command, "engine_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ENGINE, text=True).strip(), "revision": revision})
    if stage == "clean":
        commands = []
        for page in data["pages"]:
            source = next(path for path in inputs.glob(page["id"] + ".*") if path.is_file())
            clean_command = [str(Path(python).resolve()), "-I", "-B", str(ROOT / "tools/native_cleanup.py"),
                str(inputs / "manga_translator_work/json" / f"{page['id']}_translations.json"), str(source),
                str(destination / "output" / f"{page['id']}.png"), *map(str, data.get("canvas_size") or page["size"])]
            subprocess.run(clean_command, cwd=ENGINE, env=environment, check=True)
            commands.append(clean_command)
        write(destination / "run.json", {"commands": commands, "engine_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ENGINE, text=True).strip(), "revision": revision,
            "mode": "upstream inpainting on reviewed masks"})
        return {"output": str(destination / "output"), "note": "Inspect cleanup, then bind these bases in the render preflight."}
    if stage == "render":
        ffmpeg = shutil.which("ffmpeg")
        require(ffmpeg is not None, "FFmpeg is required for native raster-layer assembly.")
        output = destination / "output"
        output.mkdir()
        commands = []
        layer_names = read(ROOT / "profiles/editing.json")["order_top_first"]
        for page in data["pages"]:
            layers = destination / "layers" / page["id"]
            layers.parent.mkdir(exist_ok=True)
            width, height = data.get("canvas_size") or page["size"]
            text_command = [str(Path(python).resolve()), "-I", "-B", str(ROOT / "tools/native_text_layers.py"),
                str(inputs / "manga_translator_work/json" / f"{page['id']}_translations.json"), str(layers),
                str(width), str(height), "--ffmpeg", ffmpeg, "--cleaned", str(inputs / f"{page['id']}.png"),
                "--original", str(folder / "source/pages" / page["source"]), "--composite", str(output / f"{page['id']}.png")]
            subprocess.run(text_command, cwd=ENGINE, env=environment, check=True)
            write(layers / "layers.json", {"width": width, "height": height,
                "english_sha256": english_sha256,
                "composite": f"../../output/{page['id']}.png", "layers": [
                    {"name": layer_names[0], "file": "text.png"},
                    {"name": layer_names[1], "file": "paint.png"},
                    {"name": layer_names[2], "file": "original.png", "locked": True}]})
            commands.append(text_command)
        require(sha(revision_path(folder, revision) / "en.jsonl") == english_sha256,
                "English changed during rendering. Keep this run and render the updated text in a fresh run.")
        write(destination / "run.json", {"commands": commands, "engine_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ENGINE, text=True).strip(), "revision": revision,
            "mode": "upstream Qt text rasters and FFmpeg assembly"})
        return {"output": str(output), "layers": str(destination / "layers"),
                "note": "Import the page set to retain its raster bundles and generate layered PSDs."}
    subprocess.run(command, cwd=ENGINE, env=environment, check=True)
    return {"output": str(destination), "note": "Inspect native results before importing pages."}
