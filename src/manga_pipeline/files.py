"""Shared serialization, hashing and project path rules."""
import hashlib
import json
import re
import struct
import os
import shutil
import tempfile
import time
from functools import lru_cache
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ROOT / "projects"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        retry_file_operation(lambda: temporary.replace(path))
    finally:
        temporary.unlink(missing_ok=True)


def retry_file_operation(operation):
    # Windows readers and virus scanners can briefly deny rename/delete sharing.
    for attempt in range(6):
        try:
            return operation()
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.02 * 2 ** attempt)


def copy_snapshot(source, destination):
    """Share immutable stored rasters; metadata remains independently editable."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError(f"Snapshot destination already exists: {destination}")
    if source.suffix.lower() in {".png", ".psd"} and not source.is_symlink():
        try:
            os.link(source, destination)
            return str(destination)
        except OSError:
            pass
    return shutil.copy2(source, destination)


def sha(path):
    path = Path(path)
    stat = path.stat()
    filename = str(path.absolute())
    identity = (stat.st_dev, stat.st_ino or filename, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return _sha(HashInput(identity, filename))


@dataclass(frozen=True)
class HashInput:
    identity: tuple
    filename: str = field(compare=False)


@lru_cache(maxsize=32768)
def _sha(source):
    with Path(source.filename).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def jsonl(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    ids = [row.get("id") for row in rows]
    require(all(isinstance(item, str) and item for item in ids), f"Missing ID in {path}")
    require(len(ids) == len(set(ids)), f"Duplicate IDs in {path}")
    return rows


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def project(name):
    require(bool(SLUG.fullmatch(name)), "Use a lowercase project slug.")
    folder = PROJECTS / name
    require((folder / "project.json").is_file(), f"Unknown project: {name}")
    return folder, read(folder / "project.json")


def revision_path(folder, revision):
    require(bool(SLUG.fullmatch(revision)), "Invalid revision name.")
    return folder / "revisions" / revision


def issues(folder):
    path = folder / "issues.json"
    return read(path) if path.exists() else []


def verify_source(folder, data):
    if data.get("source_archive"):
        archive = folder / "source" / data["source_archive"]
        require(archive.is_file() and sha(archive) == data["source_archive_sha256"], "Original source archive changed.")
    for page in data["pages"]:
        path = folder / "source/pages" / page["source"]
        require(path.is_file() and sha(path) == page["sha256"], f"Original changed: {path}")


def png_size(path):
    with Path(path).open("rb") as stream:
        header = stream.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR", f"Not a PNG: {path}")
    return list(struct.unpack(">II", header[16:24]))
