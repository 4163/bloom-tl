"""Per-page output choices, completion history and the final flattened selection."""
import hashlib
import re
import shutil
import uuid
import zipfile

from .files import ROOT, fingerprint, issues, png_size, project, read, require, revision_path, sha, stamp, write


def complete(folder, data, revision):
    if not revision:
        return False
    target = revision_path(folder, revision)
    for filename in ("render.json", "import.json"):
        receipt = target / filename
        if receipt.exists() and read(receipt).get("complete") is False:
            return False
    return {path.name for path in (target / "pages").glob("*.png")} == {page["id"] + ".png" for page in data["pages"]}


def state(folder, data):
    path = folder / "output.json"
    if path.exists():
        value = read(path)
        require(value.get("version") == 1, "Unsupported output selection format.")
        return value
    # Existing chapters begin at their current completed selection without rewriting it.
    current, visited = data.get("current_revision"), set()
    while current and current not in visited and not complete(folder, data, current):
        visited.add(current)
        target = revision_path(folder, current)
        current = (read(target / "parent.json").get("revision") if (target / "parent.json").exists()
                   else read(target / "import.json").get("parent") if (target / "import.json").exists() else None)
    if not current or not complete(folder, data, current):
        candidates = [path.name for path in (folder / "revisions").glob("*") if complete(folder, data, path.name)]
        def order(name):
            number = re.search(r"\d+", name)
            return (int(number.group()) if number else -1, name)
        current = max(candidates, key=order, default=None)
    return {"version": 1, "history": {page["id"]: [current] if current else [] for page in data["pages"]}, "pins": {}}


def record_completed(folder, data, revision, changed_pages):
    require(complete(folder, data, revision), "Finish the revision before selecting its pages for output.")
    value = state(folder, data)
    for page_id in changed_pages:
        require(page_id in {page["id"] for page in data["pages"]}, "Unknown completed page.")
        history = value["history"].setdefault(page_id, [])
        if not history or history[-1] != revision:
            history.append(revision)
    write(folder / "output.json", value)


def page_info(folder, data, revision, page_id):
    page = next((page for page in data["pages"] if page["id"] == page_id), None)
    require(page is not None and complete(folder, data, revision), "Select a page from a completed revision.")
    path = revision_path(folder, revision) / "pages" / f"{page_id}.png"
    manual = folder / "manual" / revision / "pages" / path.name
    is_manual = manual.is_file()
    path = manual if is_manual else path
    require(png_size(path) == (data.get("canvas_size") or page["size"]), "Selected page has unexpected dimensions.")
    row = {"id": page_id, "revision": revision, "path": path, "sha256": sha(path), "manual": is_manual}
    psd = folder / "manual" / revision / "editable" / f"{page_id}.psd"
    if is_manual and psd.exists():
        receipt = read(folder / "manual" / revision / "receipts" / f"{page_id}.json")
        require(receipt["page_sha256"] == row["sha256"] and receipt["psd_sha256"] == sha(psd),
                "Saved PSD changed. Import it again to refresh its preview.")
        row.update(psd=psd, psd_sha256=receipt["psd_sha256"])
    return row


def resolved(folder, data):
    value = state(folder, data)
    rows = []
    for page in data["pages"]:
        page_id = page["id"]
        pin = value["pins"].get(page_id)
        history = value["history"].get(page_id, [])
        revision = pin["revision"] if pin else history[-1] if history else None
        require(revision is not None, f"Page {page_id} has no completed output yet.")
        row = page_info(folder, data, revision, page_id)
        if pin:
            require(all(row.get(key) == pin.get(key) for key in ("sha256", "manual", "psd_sha256")),
                    f"Pinned page {page_id} changed. Review and select its version again.")
        row.update(pinned=bool(pin), latest_revision=history[-1] if history else None)
        rows.append(row)
    return rows


def selection_key(rows):
    return fingerprint([{key: row.get(key) for key in ("id", "revision", "sha256", "manual", "psd_sha256", "pinned", "latest_revision")} for row in rows])


def choose(name, page_id, revision=None, expected=None, expected_image=None):
    folder, data = project(name)
    if expected is not None:
        require(expected == selection_key(resolved(folder, data)), "Output choices changed. Reload before selecting again.")
    require(page_id in {page["id"] for page in data["pages"]}, "Unknown output page.")
    value = state(folder, data)
    if revision is None:
        value["pins"].pop(page_id, None)
    else:
        row = page_info(folder, data, revision, page_id)
        require(expected_image is None or row["sha256"] == expected_image, "The viewed page changed. Reload before selecting it.")
        value["pins"][page_id] = {key: row[key] for key in ("revision", "sha256", "manual", "psd_sha256") if key in row}
    write(folder / "output.json", value)
    return describe(name)


def describe(name):
    folder, data = project(name)
    rows = resolved(folder, data)
    return {"selection": selection_key(rows), "pages": [dict(row, path=row["path"].relative_to(folder).as_posix(),
            **({"psd": row["psd"].relative_to(folder).as_posix()} if "psd" in row else {})) for row in rows]}


def snapshot(folder, data, rows):
    from .workflow import check_audit, check_english
    check_audit(folder)
    revisions = {row["id"]: row["revision"] for row in rows}
    relevant = []
    for item in issues(folder):
        record = item.get("record", "")
        parts = record.split(".")
        page_id = record if record in revisions else parts[1][1:] if len(parts) > 1 and parts[1].startswith("p") else None
        revision = item.get("revision")
        if (item["stage"] == "transcript" or not revision
                or (page_id in revisions and revisions[page_id] in {revision, item.get("addressed_revision")} if page_id else revision in revisions.values())):
            relevant.append(item)
    require(not any(item["status"] == "open" for item in relevant), "Resolve open notes affecting the selected output before finishing the chapter.")
    records = {}
    for revision in {row["revision"] for row in rows}:
        target = revision_path(folder, revision)
        records[revision] = {"english": check_english(folder, data, target / "en.jsonl"), "glossary": sha(target / "glossary.json")}
    selected = [{key: row.get(key) for key in ("id", "revision", "sha256", "manual", "psd_sha256", "pinned")} for row in rows]
    return fingerprint({"selection": selected, "transcript": sha(folder / "transcript/checked.jsonl"),
        "coverage": sha(folder / "transcript/coverage.json"), "profile": sha(ROOT / "profiles/lettering.json"), "issues": relevant,
        "pages": [{"id": row["id"], "glossary": records[row["revision"]]["glossary"],
                   "english": [line for line in records[row["revision"]]["english"] if line["id"].split(".")[1] == "p" + row["id"]]} for row in rows]})


def confirm_finished(name, note):
    folder, data = project(name)
    require(isinstance(note, str) and note.strip(), "Record the user's statement that the chapter is finished.")
    rows = resolved(folder, data)
    value = snapshot(folder, data, rows)
    write(folder / "output-finished.json", {"sha256": value, "at": stamp(), "by": "user", "note": note,
          "pages": [{key: row[key] for key in ("id", "revision", "sha256", "manual")} for row in rows]})
    return {"selection": value, "pages": len(rows)}


def protected_revision(folder, data, revision):
    if any(pin["revision"] == revision for pin in state(folder, data)["pins"].values()):
        return True
    finished = folder / "output-finished.json"
    if finished.exists() and any(row["revision"] == revision for row in read(finished)["pages"]):
        return True
    return any(any(row.get("revision") == revision for row in read(path).get("pages", []))
               for path in (folder / "final").glob("*/manifest.json"))


def without_revision(folder, data, revision, parent):
    value = state(folder, data)
    for page_id, history in value["history"].items():
        value["history"][page_id] = [entry for entry in history if entry != revision] or [parent]
    return value


def finalize(name, package="full"):
    require(package in {"full", "zip"}, "Choose the full output or flattened ZIP.")
    folder, data = project(name)
    finished = read(folder / "output-finished.json")
    rows = resolved(folder, data)
    value = snapshot(folder, data, rows)
    require(finished["sha256"] == value, "The output changed after the user finished reviewing it. Present the changed selection again.")
    final = folder / "final" / (value[:16] + ("-zip" if package == "zip" else ""))
    require(not final.exists(), "This selection is already finalized.")
    pending = folder / "final" / f".pending-{uuid.uuid4().hex}"
    pending.mkdir(parents=True)
    if package == "full":
        (pending / "pages").mkdir()
    for row in rows if package == "full" else []:
        target = pending / "pages" / f"{row['id']}.png"
        shutil.copy2(row["path"], target)
        require(sha(target) == row["sha256"], "Final page copy changed.")
        psd = row.get("psd")
        if psd is None and not row["manual"]:
            bundle = revision_path(folder, row["revision"]) / "editable" / row["id"]
            provenance = bundle / "provenance.json"
            if provenance.is_file():
                receipt = read(provenance)
                require(receipt.get("composition_verified") is True and receipt.get("layer_order_verified") is True
                        and receipt.get("preview_sha256") == row["sha256"], "Final native PSD does not match the selected page.")
                psd = bundle / f"{row['id']}.psd"
                require(sha(psd) == receipt.get("psd_sha256"), "Final native PSD changed.")
        if psd is not None:
            editable = pending / "editable" / f"{row['id']}.psd"
            editable.parent.mkdir(exist_ok=True)
            shutil.copy2(psd, editable)
            require(sha(editable) == sha(psd), "Final PSD copy changed.")
    archive = pending / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for row in rows:
            zipped.write(row["path"], f"{row['id']}.png")
    with zipfile.ZipFile(archive) as zipped:
        require(zipped.testzip() is None and zipped.namelist() == [f"{row['id']}.png" for row in rows], "Final ZIP integrity or page order failed.")
        for row in rows:
            require(hashlib.sha256(zipped.read(f"{row['id']}.png")).hexdigest() == row["sha256"], "Final ZIP member changed.")
    write(pending / "manifest.json", {"selection": value, "at": stamp(), "format": package, "archive_sha256": sha(archive),
          "pages": [{**{key: row[key] for key in ("id", "revision", "sha256", "manual", "pinned", "psd_sha256") if key in row},
                     "source": row["path"].relative_to(folder).as_posix()} for row in rows]})
    require(snapshot(folder, data, resolved(folder, data)) == value, "Output changed during finalization. Pending output was retained.")
    shutil.move(str(pending), str(final))
    write(folder / "final/current.json", {"directory": final.name, "selection": value})
    return final
