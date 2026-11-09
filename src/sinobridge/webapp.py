"""Local-only, no-login casual interface. Users bring their own model/API key.

Security boundaries:
- Server listens on loopback only and checks Host, Origin and an in-memory CSRF token.
- Untrusted uploads are limited by size and extension and saved outside the source repo.
- API keys live in one worker's memory, never files/HTML responses.
- Exactly one opted-in translation job runs at a time; stop the server to stop the app.
- No analytics, registration, remote database, account or implicit paid API request.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
import re
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from urllib.parse import parse_qs, quote, unquote, urlsplit
import webbrowser

from .ingest import ingest
from .store import load_project, load_segments
from .translate import translate, PROVIDERS
from .qa import audit
from .review import review_html
from . import export as outputs

MAX_FILE = 64 * 1024 * 1024
SUPPORTED = {".txt", ".md", ".markdown", ".docx", ".epub", ".pdf", ".html", ".htm", ".srt", ".vtt"}
API_PROVIDERS = ("gemini", "openai", "deepseek", "qwen", "openrouter", "ollama")
IDENT = re.compile(r"^[a-f0-9]{16}$")
DEFAULT_HOME = Path.home() / ".sinobridge" / "projects"


class LocalApp:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = Lock()
        self.job: dict = {"state": "idle", "workspace": None, "done": 0, "total": 0, "error": None}

    def workspace(self, uid: str) -> Path:
        if not IDENT.fullmatch(uid):
            raise ValueError("Invalid project identifier")
        folder = self.root / uid
        if not folder.is_dir() or not (folder / "project.json").is_file():
            raise FileNotFoundError("Project not found")
        if folder.is_symlink() or folder.resolve().parent != self.root:
            raise ValueError("Unsafe project path")
        return folder

    def describe(self, uid: str) -> dict:
        folder = self.workspace(uid)
        project = load_project(folder)
        segs = load_segments(folder)
        translated = sum(bool(s.get("translation")) for s in segs)
        with self.lock:
            job = dict(self.job) if self.job["workspace"] == uid else {"state": "idle"}
        return {
            "id": uid,
            "title": project["source_filename"],
            "kind": project["kind"],
            "segments": len(segs),
            "translated": translated,
            "target": project.get("target_language", "vi"),
            "review": ("machine draft, not reviewed" if translated else "not translated"),
            "warnings": project.get("extraction_warnings", []),
            "job": job,
        }

    def list_projects(self) -> list[dict]:
        found = []
        for directory in sorted(self.root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if IDENT.fullmatch(directory.name) and directory.is_dir() and not directory.is_symlink():
                try:
                    found.append(self.describe(directory.name))
                except (ValueError, OSError, KeyError, json.JSONDecodeError):
                    continue
            if len(found) >= 25:
                break
        return found

    def upload(self, name: str, data: bytes, kind: str, target: str = "vi") -> dict:
        # Do not preserve arbitrary remote paths or dot-file uploads.
        name = name.replace("\\", "/").split("/")[-1].strip()
        if len(name) > 140 or name.startswith(".") or not name:
            raise ValueError("Invalid filename")
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED:
            raise ValueError("Unsupported file type. Use TXT, MD, DOCX, EPUB, PDF, HTML or SRT/VTT")
        if kind not in ("book", "paper"):
            raise ValueError("Choose book or paper")
        if target not in ("vi", "en"):
            raise ValueError("Choose Vietnamese or English as the target language")
        if not data or len(data) > MAX_FILE:
            raise ValueError("File must be between 1 byte and 64 MB")
        uid = secrets.token_hex(8)
        folder = self.root / uid
        folder.mkdir(mode=0o700)
        # Do not delete imports automatically; the user owns local originals.
        source = folder / name
        source.write_bytes(data)
        ingest(source, folder, "subtitle" if suffix in (".srt", ".vtt") else kind, target=target)
        return self.describe(uid)

    def start(self, uid: str, provider: str, model: str, credential: str | None) -> dict:
        folder = self.workspace(uid)
        if provider not in API_PROVIDERS or provider not in PROVIDERS:
            raise ValueError("Unsupported model provider")
        if not model or len(model) > 120 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model):
            raise ValueError("Enter a valid model ID")
        if provider != "ollama" and not credential:
            raise ValueError("Enter your own provider API key")
        if credential and len(credential) > 4000:
            raise ValueError("API key too long")
        segs = load_segments(folder)
        pending = sum(s["status"] == "PENDING" for s in segs)
        if not pending:
            raise ValueError("No untranslated segments remain")
        with self.lock:
            if self.job["state"] in ("running", "stopping"):
                raise ValueError("Another translation is running")
            self.job = {
                "state": "running", "workspace": uid,
                "done": len(segs)-pending, "total": len(segs), "error": None,
                "cancel": False,
            }
        worker = Thread(target=self._translate_job, args=(uid, provider, model, credential), daemon=True)
        worker.start()
        return {"started": True, "workspace": uid, "total": len(segs)}

    def cancel(self, uid: str) -> dict:
        with self.lock:
            if self.job["workspace"] != uid or self.job["state"] != "running":
                raise ValueError("No active translation for this project")
            self.job["cancel"] = True
            self.job["state"] = "stopping"
        return {"stopping": True, "note": "Current model request may finish before stopping"}

    def _translate_job(self, uid: str, provider: str, model: str, credential: str | None) -> None:
        workspace = self.root / uid
        try:
            while True:
                with self.lock:
                    if self.job.get("cancel"):
                        self.job["state"] = "stopped"
                        break
                segs = load_segments(workspace)
                if not any(s["status"] == "PENDING" for s in segs):
                    audit(workspace)
                    with self.lock:
                        self.job["state"] = "done"
                    break
                translate(workspace, provider, model, allow_external=(provider != "ollama"),
                          dry_run=False, limit=1, credential=credential)
                with self.lock:
                    self.job["done"] = sum(s["status"] != "PENDING" for s in load_segments(workspace))
        except Exception as exc:
            with self.lock:
                self.job["state"] = "error"
                self.job["error"] = str(exc)[:500]
        finally:
            # Do not store key on self, in projects or in any logs.
            credential = None


def clean(seg: dict, text: str) -> str:
    """Preview text without Markdown heading marks."""
    return re.sub(r"^\s{0,3}#{1,6}\s+", "", text) if seg.get("kind") == "heading" else text


def make_handler(app: LocalApp, port: int):
    origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "SinoBridgeLocal/0.1"
        def log_message(self, fmt, *args):
            # Do not log document names, query strings, keys, file paths or metadata.
            return

        def _headers(self, status: int, mime: str, size: int, filename: str | None = None):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            if filename:
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(filename, safe=""))
            self.end_headers()

        def _send(self, body: bytes, mime: str = "application/json; charset=utf-8",
                  status: int = 200, filename: str | None = None):
            self._headers(status, mime, len(body), filename)
            self.wfile.write(body)

        def _json(self, record: object, status: int = 200):
            self._send(json.dumps(record, ensure_ascii=False).encode("utf-8"), status=status)

        def _valid_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _authorized(self, *, post: bool = False):
            if not self._valid_host() or self.headers.get("X-SinoBridge-Token") != app.token:
                self._json({"error": "Unauthorized request"}, 403)
                return False
            if post and self.headers.get("Origin") not in origins:
                self._json({"error": "Invalid origin"}, 403)
                return False
            return True

        def _parse_body(self):
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > MAX_FILE + 8192:
                raise ValueError("Invalid upload or request size (maximum 64 MB)")
            return self.rfile.read(size)

        def do_GET(self):
            try:
                url = urlsplit(self.path)
                if url.path == "/":
                    if not self._valid_host():
                        self._json({"error": "Bad host"}, 403)
                        return
                    page = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
                    page = page.replace("__SERVER_TOKEN__", json.dumps(app.token))
                    self._send(page.encode("utf-8"), "text/html; charset=utf-8")
                    return
                if not self._authorized():
                    return
                q = parse_qs(url.query)
                uid = q.get("id", [""])[0]
                if url.path == "/api/projects":
                    self._json({"projects": app.list_projects()})
                elif url.path == "/api/status":
                    self._json(app.describe(uid))
                elif url.path == "/api/preview":
                    folder = app.workspace(uid)
                    segs = load_segments(folder)
                    self._json({"segments": [
                        {"source": clean(s, s["source"])[:2000], "translation": clean(s, s.get("translation") or "")[:2000]}
                        for s in segs[:8]
                    ]})
                elif url.path == "/api/download":
                    folder = app.workspace(uid)
                    fmt = q.get("format", ["epub"])[0]
                    bilingual = q.get("bilingual", ["0"])[0] == "1"
                    if fmt not in ("epub", "docx", "md", "html", "srt"):
                        raise ValueError("Invalid export format")
                    if fmt == "html":
                        target = folder / "review.html"
                        review_html(folder, target)
                        mime = "text/html; charset=utf-8"
                    else:
                        target = folder / ("translation." + fmt)
                        formats = {"epub": outputs.epub, "docx": outputs.docx, "md": outputs.markdown,
                                   "srt": outputs.subtitles}
                        formats[fmt](folder, target, bilingual=bilingual)
                        mime = {"epub": "application/epub+zip",
                                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                "md": "text/markdown; charset=utf-8", "srt": "application/x-subrip"}[fmt]
                    self._send(target.read_bytes(), mime, filename=f"SinoBridge-{uid[:6]}.{fmt}")
                else:
                    self._json({"error": "Unknown endpoint"}, 404)
            except (ValueError, RuntimeError, KeyError, FileNotFoundError, OSError) as exc:
                self._json({"error": str(exc)[:300]}, 400)

        def do_POST(self):
            try:
                if not self._authorized(post=True):
                    return
                url = urlsplit(self.path).path
                if url == "/api/upload":
                    filename = unquote(self.headers.get("X-Filename", ""))
                    kind = self.headers.get("X-Document-Kind", "book")
                    target = self.headers.get("X-Target-Language", "vi")
                    raw = self._parse_body()
                    self._json(app.upload(filename, raw, kind, target), 201)
                    return
                body = json.loads(self._parse_body())
                if not isinstance(body, dict):
                    raise ValueError("Expected an object")
                if url == "/api/start":
                    self._json(app.start(body.get("id", ""), body.get("provider", ""),
                                         body.get("model", ""), body.get("key", "")))
                elif url == "/api/cancel":
                    self._json(app.cancel(body.get("id", "")))
                else:
                    self._json({"error": "Unknown endpoint"}, 404)
            except (ValueError, RuntimeError, KeyError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
                self._json({"error": str(exc)[:300]}, 400)
    return Handler


def create_server(root: Path = DEFAULT_HOME, port: int = 8765) -> ThreadingHTTPServer:
    app = LocalApp(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    server.daemon_threads = True
    return server


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="SinoBridge local drag-and-drop UI (no cloud account)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_HOME)
    parser.add_argument("--open", action="store_true", help="Open the system default browser")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Port must be 1024–65535")
    try:
        server = create_server(args.data_dir, args.port)
    except OSError as exc:
        parser.error(f"Cannot start on port {args.port}: {exc}")
    url = f"http://127.0.0.1:{args.port}"
    print(f"SinoBridge local interface: {url}")
    print(f"Documents remain on this machine: {args.data_dir.expanduser()}")
    print("Press Ctrl+C to stop the app.")
    try:
        if args.open:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
