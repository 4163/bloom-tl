"""Editable raster bundles and imported PSD previews. No desktop application calls."""
import json
import re
import shutil
import subprocess
import uuid
import tempfile
from pathlib import Path

from .files import ROOT, copy_snapshot, fingerprint, png_size, project, read, require, retry_file_operation, revision_path, sha, stamp, write

MAX_IMPORT_BYTES = read(ROOT / "profiles/editing.json")["import_limit_mib"] * 1024 * 1024


def node_command(*arguments):
    node = shutil.which("node")
    require(node is not None, "Install Node.js 20 or newer to use PSD export/import.")
    require((ROOT / "node_modules/ag-psd").is_dir(), "Run npm ci in this repository to install the PSD tools.")
    try:
        result = subprocess.run([node, str(ROOT / "tools/psd.mjs"), *map(str, arguments)],
                                capture_output=True, text=True, encoding="utf-8", timeout=120,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as error:
        raise ValueError("PSD conversion exceeded two minutes. The original import is retained.") from error
    require(result.returncode == 0, result.stderr.strip() or "PSD conversion failed.")
    return result.stdout.strip()


def export_editable(name, revision, page_id, plan):
    folder, data = project(name)
    page = next((page for page in data["pages"] if page["id"] == page_id), None)
    require(page is not None, "Unknown page.")
    plan = Path(plan).resolve()
    manifest = read(plan)
    expected = data.get("canvas_size") or page["size"]
    require([manifest["width"], manifest["height"]] == expected, "Editable canvas differs from the page.")
    require([layer["name"] for layer in manifest["layers"]] == read(ROOT / "profiles/editing.json")["order_top_first"], "Use the three named raster layers, top first.")
    composite = (plan.parent / manifest["composite"]).resolve()
    require(sha(composite) == sha(revision_path(folder, revision) / "pages" / f"{page_id}.png"), "Use the exact reviewed flat page as the PSD compatibility image.")
    capture = plan.parent / "capture.json"
    if capture.exists():
        receipt = read(capture)
        require(receipt["original_source_sha256"] == page["sha256"], "Captured original does not match the source page.")
        require(all(receipt["sha256"][filename] == sha((plan.parent / layer["file"]).resolve())
                    for filename, layer in zip(("text.png", "paint.png", "original.png"), manifest["layers"])),
                "A captured layer changed after rendering.")
    final = revision_path(folder, revision) / "editable" / page_id
    require(not final.exists(), "Editable bundle already exists. Use a new revision.")
    output = final.with_name(f".pending-{page_id}-{uuid.uuid4().hex}")
    output.mkdir(parents=True)
    for layer, filename in zip(manifest["layers"], ("text.png", "paint.png", "original.png")):
        source = (plan.parent / layer["file"]).resolve()
        require(source.suffix.lower() == ".png", "Editable bundles use native-exported PNG rasters.")
        shutil.copy2(source, output / filename)
        layer["file"] = filename
    shutil.copy2(composite, output / "preview.png")
    manifest["composite"] = "preview.png"
    write(output / "layers.json", manifest)
    exported = json.loads(node_command("export", output / "layers.json", output / f"{page_id}.psd"))
    require(exported.get("layer_order_verified") is True, "PSD layer order was not verified.")
    if capture.exists():
        shutil.copy2(capture, output / "capture.json")
    write(output / "provenance.json", {"at": stamp(), "revision": revision,
          "composition_verified": True,
          "layer_order_verified": True,
          "psd_sha256": sha(output / f"{page_id}.psd"), "preview_sha256": sha(composite),
          "note": "Raster text, cleanup and original layers. Pixel drawing remains native; JavaScript writes the PSD container."})
    output.rename(final)
    return final


def edit_contents(folder, revision, page_id):
    base = folder / "manual" / revision
    return {kind: sha(path) if path.exists() else None for kind, path in {
        "rendered": revision_path(folder, revision) / "pages" / f"{page_id}.png",
        "preview": base / "pages" / f"{page_id}.png",
        "psd": base / "editable" / f"{page_id}.psd",
        "receipt": base / "receipts" / f"{page_id}.json",
    }.items()}


def edit_state(folder, revision, page_id):
    return fingerprint({"current_revision": read(folder / "project.json").get("current_revision"),
                        **edit_contents(folder, revision, page_id)})


def import_edit(name, revision, page_id, source, original_name=None, expected=None):
    folder, _ = project(name)
    work_root = folder / "work"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="import-", dir=work_root, ignore_cleanup_errors=True) as temporary:
        return _import_edit(name, revision, page_id, source, original_name, expected, Path(temporary))


def _import_edit(name, revision, page_id, source, original_name, expected, work):
    from .workflow import page_set

    folder, data = project(name)
    page = next((page for page in data["pages"] if page["id"] == page_id), None)
    require(page is not None, "Unknown page.")
    original = revision_path(folder, revision)
    require((original / "pages" / f"{page_id}.png").exists(), "Render this revision before importing manual work.")
    before = edit_state(folder, revision, page_id)
    require(expected is None or expected == before, "This chapter changed. Review it before importing again.")
    source = Path(source).resolve()
    require(source.suffix.lower() in {".psd", ".png"}, "Import a saved PSD or flattened PNG.")
    require(source.stat().st_size <= MAX_IMPORT_BYTES, "Manual import exceeds 512 MiB.")
    import_id = uuid.uuid4().hex
    saved = work / (page_id + source.suffix.lower())
    shutil.copy2(source, saved)
    preview = work / f"{page_id}.preview.png"
    expected_size = data.get("canvas_size") or page["size"]
    if source.suffix.lower() == ".psd":
        node_command("preview", saved, preview, *expected_size)
    else:
        require(png_size(saved) == expected_size, "PNG canvas differs from the selected page.")
        node_command("validate-png", saved, preview, *expected_size)
    require(before == edit_state(folder, revision, page_id), "This chapter changed during import. Review it before importing again.")

    previous_manual = folder / "manual" / revision
    active = previous_manual / "pages" / f"{page_id}.png"
    active_psd = previous_manual / "editable" / f"{page_id}.psd"
    if not active.exists():
        active = original / "pages" / f"{page_id}.png"
        active_psd = original / "editable" / page_id / f"{page_id}.psd"
    unchanged = sha(preview) == sha(active)
    if source.suffix.lower() == ".psd":
        unchanged = unchanged and active_psd.exists() and sha(saved) == sha(active_psd)
    else:
        unchanged = unchanged and not active_psd.exists()
    if unchanged:
        return {"page": page_id, "revision": revision, "created": False}

    numbers = [int(match.group(1)) for directory in ("revisions", "manual")
               for path in (folder / directory).glob("*")
               if (match := re.match(r"r(\d+)(?:-|$)", path.name))]
    next_revision = f"r{max(numbers, default=0) + 1:03d}"
    destination = revision_path(folder, next_revision)
    manual = folder / "manual" / next_revision
    staged_revision = work / "revision"
    staged_manual = work / "manual"
    shutil.copytree(original, staged_revision, copy_function=copy_snapshot,
                    ignore=shutil.ignore_patterns("approval.json", "manual-approval.json"))
    for directory in ("pages", "editable", "receipts"):
        old = previous_manual / directory
        if old.is_dir():
            shutil.copytree(old, staged_manual / directory, copy_function=copy_snapshot)
    history = staged_manual / "imports" / import_id
    history.mkdir(parents=True)
    copy_snapshot(saved, history / saved.name)
    copy_snapshot(preview, history / preview.name)
    active = staged_manual / "pages" / f"{page_id}.png"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.unlink(missing_ok=True)
    copy_snapshot(preview, active)
    editable = staged_manual / "editable" / f"{page_id}.psd"
    receipt = {"at": stamp(), "history": f"manual/{next_revision}/imports/{import_id}",
               "page_sha256": sha(preview), "import_sha256": sha(saved),
               "source_name": original_name or source.name}
    if source.suffix.lower() == ".psd":
        editable.parent.mkdir(parents=True, exist_ok=True)
        editable.unlink(missing_ok=True)
        copy_snapshot(saved, editable)
        receipt["psd_sha256"] = sha(saved)
    else:
        editable.unlink(missing_ok=True)
    write(history / "record.json", receipt)
    write(staged_manual / "receipts" / f"{page_id}.json", receipt)
    write(staged_revision / "import.json", {"at": receipt["at"], "parent": revision, "complete": False,
          "page": page_id, "source_name": receipt["source_name"], "import_sha256": receipt["import_sha256"]})
    # Change the current revision only after its pages and receipts are valid.
    manual.parent.mkdir(parents=True, exist_ok=True)
    previous_output = read(folder / "output.json") if (folder / "output.json").exists() else None
    try:
        retry_file_operation(lambda: staged_manual.rename(manual))
        retry_file_operation(lambda: staged_revision.rename(destination))
        page_set(folder, data, next_revision, True)
        require(before == edit_state(folder, revision, page_id), "This chapter changed while saving the import. Import it again from the current revision.")
        _, data = project(name)
        imported = read(destination / "import.json")
        imported["complete"] = True
        write(destination / "import.json", imported)
        from .output import record_completed
        record_completed(folder, data, next_revision, [page_id])
        data["current_revision"] = next_revision
        write(folder / "project.json", data)
    except Exception:
        if previous_output is None:
            (folder / "output.json").unlink(missing_ok=True)
        else:
            write(folder / "output.json", previous_output)
        if destination.exists():
            retry_file_operation(lambda: destination.rename(staged_revision))
        if manual.exists():
            retry_file_operation(lambda: manual.rename(staged_manual))
        raise
    return {"page": page_id, "revision": next_revision, "created": True}


def discard_revision(name, revision=None, page_id=None):
    from .output import protected_revision, without_revision
    folder, data = project(name)
    current = data.get("current_revision")
    revision = revision or current
    require(bool(revision), "No revision specified or active.")
    target = revision_path(folder, revision)
    require(target.is_dir(), f"Revision does not exist: {revision}")
    require(not protected_revision(folder, data, revision), "This revision is selected for output or retained by a finished chapter. Use latest or choose another page version first.")
    import_meta = target / "import.json"
    require(import_meta.is_file(), "Only imported revisions can be discarded.")
    receipt = read(import_meta)
    require(page_id is None or page_id == receipt.get("page"), "This import belongs to a different page.")
    require(not (target / "approval.json").exists() and not (target / "manual-approval.json").exists(),
            "Approved revisions cannot be discarded.")
    for rev_dir in (folder / "revisions").iterdir():
        if rev_dir.is_dir() and rev_dir.name != revision:
            for filename, key in (("import.json", "parent"), ("parent.json", "revision")):
                child_meta = rev_dir / filename
                if child_meta.is_file():
                    require(read(child_meta).get(key) != revision,
                            f"Cannot discard revision: {rev_dir.name} was created from it.")
    parent = receipt.get("parent")
    require(bool(parent) and (folder / "revisions" / parent).is_dir(),
            f"Parent revision is missing or invalid: {parent}")
    output_state = without_revision(folder, data, revision, parent)
    retry_file_operation(lambda: shutil.rmtree(target))
    manual_dir = folder / "manual" / revision
    if manual_dir.is_dir():
        retry_file_operation(lambda: shutil.rmtree(manual_dir))
    if current == revision:
        _, data = project(name)
        data["current_revision"] = parent
        write(folder / "project.json", data)
        current = parent
    write(folder / "output.json", output_state)
    return {"project": name, "discarded": revision, "revision": current}
