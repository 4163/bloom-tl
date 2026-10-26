"""Loopback review server. Serves only review UI and catalogued page images."""
import json
import mimetypes
import secrets
import socket
import threading
import uuid
import shutil
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit, parse_qs

from .files import ROOT, require, retry_file_operation
from .review import Catalog
from .workflow import add_issue, remove_issue
from .output import choose

STATIC = {"/": "index.html", "/index.html": "index.html", "/global.css": "global.css", "/regions.js": "regions.js",
          "/review.css": "review.css", "/app.js": "app.js", "/theme.js": "theme.js", "/state.js": "state.js",
          "/favicon.png": "favicon.png", "/favicon.ico": "favicon.png"}


class ReviewServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        # Windows otherwise permits multiple servers to bind the same local port.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def serve(port=8765):
    require(1 <= port <= 65535, "Invalid port.")
    catalog, token, lock = Catalog(), secrets.token_urlsafe(32), threading.RLock()
    origin = f"http://127.0.0.1:{port}"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, status, content, mime="application/json; charset=utf-8"):
            try:
                self.send_content(status, content, mime)
            except ConnectionError:
                pass

        def send_content(self, status, content, mime):
            if not isinstance(content, bytes):
                content = json.dumps(content, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            try:
                if path == "/api/catalog":
                    with lock:
                        value = catalog.get()
                        value = dict(value, version=f'{value["version"]}-{token[:8]}')
                        etag = f'"{value["version"]}"'
                        if self.headers.get("If-None-Match") == etag:
                            self.send_response(304)
                            self.send_header("ETag", etag)
                            self.end_headers()
                            return
                        return self.respond(200, dict(value, token=token, workspace=str(ROOT)))
                if path in STATIC:
                    file = ROOT / "web" / STATIC[path]
                elif path.startswith("/assets/"):
                    file = catalog.assets.get(path[len("/assets/"):])
                    if file is None:
                        return self.respond(404, {"error": "Unknown page."})
                else:
                    return self.respond(404, {"error": "Not found."})
                mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
                # Versioned assets may be reused while navigating; stream large PSDs.
                with file.open("rb") as stream:
                    stat = os.fstat(stream.fileno())
                    etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'
                    cached = path.startswith("/assets/") and bool(parse_qs(urlsplit(self.path).query).get("v"))
                    if cached and self.headers.get("If-None-Match") == etag:
                        self.send_response(304)
                        self.send_header("ETag", etag)
                        self.end_headers()
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(stat.st_size))
                    self.send_header("Cache-Control", "private, max-age=86400" if cached else "no-store")
                    self.send_header("ETag", etag)
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    shutil.copyfileobj(stream, self.wfile, 1024 * 1024)
            except (OSError, ValueError, KeyError) as error:
                self.respond(400, {"error": str(error)})

        def do_POST(self):
            upload = None
            try:
                host = self.headers.get("Host")
                require(host in {f"127.0.0.1:{port}", f"localhost:{port}"}, "Use the loopback review address.")
                require(self.headers.get("Origin") == f"http://{host}", "Review actions must come from this site.")
                require(secrets.compare_digest(self.headers.get("X-Review-Token", ""), token), "Invalid review token.")
                length = int(self.headers.get("Content-Length", "0"))
                if self.path == "/api/import":
                    from .editing import MAX_IMPORT_BYTES, import_edit
                    require(0 < length <= MAX_IMPORT_BYTES, "Manual import must be smaller than 512 MiB.")
                    filename = unquote(self.headers.get("X-File-Name", ""))
                    extension = Path(filename).suffix.lower()
                    require(extension == ".psd", "Import a saved PSD file.")
                    expected = self.headers.get("X-Edit-State")
                    require(bool(expected), "Missing review state. Reload before importing.")
                    upload = ROOT / ".runtime/uploads" / (uuid.uuid4().hex + extension)
                    upload.parent.mkdir(parents=True, exist_ok=True)
                    with upload.open("wb") as output:
                        remaining = length
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            require(bool(chunk), "Upload ended early.")
                            output.write(chunk)
                            remaining -= len(chunk)
                    with lock:
                        result = import_edit(self.headers.get("X-Project", ""), self.headers.get("X-Revision", ""), self.headers.get("X-Page", ""), upload, filename, expected)
                    return self.respond(200, result)
                require(0 < length <= 16384, "Invalid request size.")
                payload = json.loads(self.rfile.read(length))
                with lock:
                    if self.path == "/api/issues":
                        result = add_issue(payload["project"], "visual", payload["page"], payload["note"],
                                           payload["revision"], region=payload.get("region"), regions=payload.get("regions"))
                    elif self.path == "/api/remove-note":
                        result = remove_issue(payload["project"], payload["issue"])
                    elif self.path == "/api/output-choice":
                        require(isinstance(payload.get("selection"), str), "Missing output selection. Reload before choosing.")
                        require("revision" in payload and (payload["revision"] is None or isinstance(payload["revision"], str)), "Choose a revision or use latest.")
                        if payload["revision"] is not None:
                            require(isinstance(payload.get("image_sha256"), str), "Missing reviewed image. Reload before choosing.")
                        result = choose(payload["project"], payload["page"], payload["revision"],
                                        payload["selection"], payload.get("image_sha256"))
                    elif self.path == "/api/discard-revision":
                        from .editing import discard_revision
                        require(isinstance(payload.get("page"), str), "Identify the page whose imported revision should be discarded.")
                        result = discard_revision(payload["project"], payload.get("revision"), payload["page"])
                    else:
                        return self.respond(404, {"error": "Unknown action."})
                self.respond(200, result)
            except (OSError, ValueError, KeyError, TypeError) as error:
                self.respond(400, {"error": str(error)})
            finally:
                if upload is not None:
                    retry_file_operation(lambda: upload.unlink(missing_ok=True))

    server = ReviewServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    print(f"Review at {origin}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
