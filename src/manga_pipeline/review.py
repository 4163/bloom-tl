"""Review catalog and allowlisted assets. Independent of HTTP and the browser UI."""
from pathlib import Path
from functools import lru_cache

from .files import PROJECTS, ROOT, fingerprint, issues, project, read as read_file, require, sha
from .editing import edit_contents
from . import output


def version(path):
    stat = path.stat()
    return f"{stat.st_mtime_ns:x}-{stat.st_size:x}"


class Catalog:
    def __init__(self):
        self.signature = None
        self.value = None
        self.assets = {}
        self.pages = {}

    def get(self):
        read = lru_cache(maxsize=None)(read_file)
        files = [ROOT / "profiles/lettering.json"]
        for metadata in sorted(PROJECTS.glob("*/project.json")):
            folder = metadata.parent
            files.extend(folder / item["path"] for item in read(metadata).get("variants", []))
            # Import history, archives and native layer rasters are not catalog inputs.
            for directory in ("source/pages", "variants"):
                base = folder / directory
                files.extend(path for path in base.rglob("*") if path.is_file())
            for revision in sorted((folder / "revisions").glob("*")):
                if not revision.is_dir():
                    continue
                files.extend(revision.glob("*.json"))
                files.extend((revision / "pages").glob("*.png"))
                files.extend((revision / "editable").glob("*/*.psd"))
                files.extend((revision / "editable").glob("*/provenance.json"))
                manual = folder / "manual" / revision.name
                for directory, pattern in (("pages", "*.png"), ("editable", "*.psd"), ("receipts", "*.json")):
                    files.extend((manual / directory).glob(pattern))
            files.extend(folder / name for name in ("project.json", "issues.json", "output.json", "output-finished.json", "final/current.json") if (folder / name).exists())
            files.extend((folder / "final").glob("*/manifest.json"))
        signature = tuple((str(path), version(path)) for path in files)
        versions = dict(signature)
        if signature == self.signature:
            return self.value
        assets, projects, page_cache = {}, [], {}

        def asset(path, key):
            require(path.resolve().is_relative_to(PROJECTS.resolve()), "Asset escaped project storage.")
            assets[key] = path
            return f"/assets/{key}?v={version(path)}"

        for metadata in sorted(PROJECTS.glob("*/project.json")):
            folder, data = project(metadata.parent.name)
            name = data["id"]
            revisions = []
            children = set()
            for other in (folder / "revisions").iterdir():
                for filename, key in (("import.json", "parent"), ("parent.json", "revision")):
                    meta = other / filename
                    if meta.is_file():
                        children.add(read(meta).get(key))
            protected = {pin["revision"] for pin in output.state(folder, data)["pins"].values()}
            for receipt in [folder / "output-finished.json", *(folder / "final").glob("*/manifest.json")]:
                if receipt.is_file():
                    protected.update(row.get("revision") for row in read(receipt).get("pages", []))
            for revision in sorted((folder / "revisions").glob("*")):
                if not (revision / "pages").is_dir():
                    continue
                pages = []
                for page in data["pages"]:
                    filename = page["id"] + ".png"
                    rendered = revision / "pages" / filename
                    if not rendered.exists():
                        continue
                    manual = folder / "manual" / revision.name / "pages" / filename
                    bundle = revision / "editable" / page["id"]
                    psd = bundle / f"{page['id']}.psd"
                    provenance = bundle / "provenance.json"
                    manual_psd = folder / "manual" / revision.name / "editable" / f"{page['id']}.psd"
                    receipt_path = folder / "manual" / revision.name / "receipts" / f"{page['id']}.json"
                    source = folder / "source/pages" / page["source"]
                    dependencies = [rendered, manual, psd, provenance, manual_psd, receipt_path, source]
                    dependencies.extend(folder / item["path"] for item in data.get("variants", []) if item["page"] == page["id"])
                    key = (name, revision.name, page["id"], fingerprint([page, data.get("canvas_size"), data.get("variants", [])]),
                           tuple(versions.get(str(path)) for path in dependencies))
                    cached = self.pages.get(key)
                    if cached:
                        row, contents, page_assets = cached
                        assets.update(page_assets)
                        pages.append(dict(row, edit_state=fingerprint({"current_revision": data.get("current_revision"), **contents})))
                        page_cache[key] = cached
                        continue
                    contents = edit_contents(folder, revision.name, page["id"])
                    receipt = read(provenance) if provenance.exists() else {}
                    captured = (receipt.get("composition_verified") is True
                                and receipt.get("layer_order_verified") is True
                                and receipt.get("preview_sha256") == sha(rendered))
                    pages.append({"id": page["id"], "source": asset(folder / "source/pages" / page["source"], f"{name}/source/{page['source']}"),
                        "english": asset(rendered, f"{name}/revisions/{revision.name}/{filename}"),
                        "manual": asset(manual, f"{name}/manual/{revision.name}/{filename}") if manual.exists() else None,
                        "psd": asset(psd, f"{name}/editable/{revision.name}/{page['id']}.psd") if captured and psd.exists() else None,
                        "manual_psd": asset(manual_psd, f"{name}/manual-editable/{revision.name}/{page['id']}.psd") if manual.exists() and manual_psd.exists() else None,
                        "edit_state": fingerprint({"current_revision": data.get("current_revision"), **contents}),
                        "review_image_sha256": sha(manual if manual.exists() else rendered),
                        "source_width": page["size"][0], "canvas_size": data.get("canvas_size") or page["size"],
                        "variants": [{"label": item["label"], "url": asset(folder / item["path"], f"{name}/variants/{item['id']}/{filename}")}
                                     for item in data.get("variants", []) if item["page"] == page["id"]]})
                    urls = [pages[-1][field] for field in ("source", "english", "manual", "psd", "manual_psd")]
                    urls.extend(item["url"] for item in pages[-1]["variants"])
                    keys = [url.split("?", 1)[0][len("/assets/"):] for url in urls if url]
                    page_cache[key] = (pages[-1], contents, {key: assets[key] for key in keys})
                import_meta = revision / "import.json"
                is_imported = import_meta.is_file()
                imported = read(import_meta) if is_imported else {}
                render_meta = revision / "render.json"
                rendered = read(render_meta) if render_meta.is_file() else {}
                parent_meta = revision / "parent.json"
                parent = imported.get("parent") if is_imported else (
                    read(parent_meta).get("revision") if parent_meta.is_file() else rendered.get("parent"))
                changed_pages = [imported["page"]] if is_imported else (
                    [Path(filename).stem for filename in rendered["rendered_pages"]]
                    if "rendered_pages" in rendered else [page["id"] for page in pages])
                is_parent = revision.name in children
                has_approval = any((revision / filename).exists() for filename in ("approval.json", "manual-approval.json"))
                can_discard = bool(is_imported and not has_approval and not is_parent and revision.name not in protected)
                revisions.append({"id": revision.name, "pages": pages,
                                  "can_discard": can_discard, "parent": parent,
                                  "imported_page": imported.get("page"), "changed_pages": changed_pages,
                                  "complete": output.complete(folder, data, revision.name)})
            try:
                rows = output.resolved(folder, data)
                selection = {"selection": output.selection_key(rows), "error": None,
                    "pages": [{key: row[key] for key in ("id", "revision", "pinned", "latest_revision", "sha256", "manual")} for row in rows]}
            except (ValueError, OSError, KeyError) as failure:
                selection = {"selection": None, "pages": [], "error": str(failure)}
            projects.append({"id": name, "title": data.get("title", name), "current_revision": data.get("current_revision"),
                             "revisions": revisions, "issues": issues(folder), "output": selection})
        import hashlib
        self.value = {"version": hashlib.sha256(repr(signature).encode()).hexdigest()[:16], "projects": projects}
        self.assets, self.signature, self.pages = assets, signature, page_cache
        return self.value
