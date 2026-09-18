#!/usr/bin/env python3
"""
A local HTTP server that puts a browser UI in front of seal.py.

Runs on the loopback interface only. Sealing needs qpdf, a native binary, so it
cannot happen in the browser -- and rewriting it in JavaScript would mean
rebuilding the PDF, which is exactly the mistake this whole tool exists to avoid.
The browser therefore uploads the file once and the sealing happens here.

Deliberately built on nothing but the standard library, so the promise that this
project installs nothing still holds. That rules out multipart form parsing
(`cgi` is gone as of Python 3.13), hence the two-step API: the PDF is uploaded
once as a raw body, then sealed as many times as there are buyers.

    POST /api/upload          body: the PDF        -> {"id", "pages", "counts"}
    POST /api/seal            body: JSON job       -> the sealed PDF, or a ZIP
    GET  /api/health                               -> {"qpdf": "..."}
    GET  /                                         -> the built web UI

Uploads live in a temporary directory that is removed when the server stops.

    python server.py                 # http://127.0.0.1:8000
    python server.py --port 9000
"""

from __future__ import annotations

import argparse
import atexit
import io
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import seal

# A 96 MB e-book is a realistic input, so the ceiling is generous -- but it is a
# ceiling, because without one a single request could fill the disk.
MAX_UPLOAD = 512 * 1024 * 1024
MAX_ROWS = 2000

UPLOADS = Path(tempfile.mkdtemp(prefix='pdf-seal-'))
atexit.register(lambda: shutil.rmtree(UPLOADS, ignore_errors=True))

WEB_ROOT = Path(__file__).resolve().parent / 'web' / 'dist' / 'pdf-seal' / 'browser'


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def stored_pdf(upload_id: str) -> Path:
    # The id comes from the client, so it must never be allowed to walk the
    # filesystem; only the exact shape we handed out is accepted.
    if not re.fullmatch(r'[0-9a-f]{32}', upload_id or ''):
        raise ApiError(400, 'Unknown upload id.')
    path = UPLOADS / f'{upload_id}.pdf'
    if not path.is_file():
        raise ApiError(404, 'That upload is gone. Upload the PDF again.')
    return path


def page_count(pdf: Path) -> int:
    done = subprocess.run(['qpdf', '--show-npages', str(pdf)], capture_output=True, text=True)
    return int(done.stdout.strip()) if done.returncode in (0, 3) else 0


def safe_filename(name: str) -> str:
    name = seal.strip_accents(name).strip() or 'sealed'
    name = re.sub(r'[^A-Za-z0-9._@-]', '_', name)
    return name if name.lower().endswith('.pdf') else f'{name}.pdf'


def handle_upload(body: bytes) -> dict:
    if not body.startswith(b'%PDF'):
        raise ApiError(400, 'That does not look like a PDF.')
    upload_id = uuid4().hex
    path = UPLOADS / f'{upload_id}.pdf'
    path.write_bytes(body)
    try:
        counts = seal.count_navigation(path)
    except Exception as err:  # a damaged file should not take the server down
        path.unlink(missing_ok=True)
        raise ApiError(400, f'qpdf could not read the file: {err}') from None
    return {'id': upload_id, 'pages': page_count(path), 'counts': counts}


def handle_seal(job: dict) -> tuple[bytes, str, str]:
    """Returns (body, content type, filename)."""
    source = stored_pdf(job.get('id', ''))
    visible = bool(job.get('visible'))
    rows = job.get('rows') or []
    if not isinstance(rows, list) or not rows:
        raise ApiError(400, 'No buyers to seal for.')
    if len(rows) > MAX_ROWS:
        raise ApiError(400, f'That is more than {MAX_ROWS} rows in one go.')

    before = seal.count_navigation(source)
    work = Path(tempfile.mkdtemp(dir=UPLOADS))
    try:
        produced: list[tuple[str, Path]] = []
        for index, row in enumerate(rows):
            text = str(row.get('text') or '').strip()
            if not text:
                raise ApiError(400, f'Row {index + 1} has no seal text.')
            name = safe_filename(str(row.get('filename') or f'sealed-{index + 1}.pdf'))
            target = work / f'{index}.pdf'
            seal.seal(source, target, text, visible)
            produced.append((name, target))

        after = seal.count_navigation(produced[0][1])
        if after != before:
            raise ApiError(
                500,
                'Links or bookmarks were lost while sealing. '
                'Nothing was returned; this is a bug.',
            )

        if len(produced) == 1:
            name, path = produced[0]
            return path.read_bytes(), 'application/pdf', name

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as archive:
            used: set[str] = set()
            for name, path in produced:
                # Two buyers can share a filename; neither may overwrite the other.
                unique, counter = name, 2
                while unique in used:
                    unique = f'{name[:-4]}-{counter}.pdf'
                    counter += 1
                used.add(unique)
                archive.write(path, unique)
        return buffer.getvalue(), 'application/zip', 'sealed.zip'
    finally:
        shutil.rmtree(work, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'pdf-seal'
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt: str, *args) -> None:
        print(f'{self.command} {self.path} -> {args[1] if len(args) > 1 else ""}')

    def _send(
        self, status: int, body: bytes, content_type: str, filename: str | None = None
    ) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), 'application/json')

    def _read_body(self) -> bytes:
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_UPLOAD:
            raise ApiError(413, 'That file is larger than this server accepts.')
        return self.rfile.read(length)

    def do_POST(self) -> None:  # noqa: N802 -- name fixed by BaseHTTPRequestHandler
        route = urlparse(self.path).path
        try:
            if route == '/api/upload':
                self._send_json(200, handle_upload(self._read_body()))
            elif route == '/api/seal':
                job = json.loads(self._read_body() or b'{}')
                body, content_type, filename = handle_seal(job)
                self._send(200, body, content_type, filename)
            else:
                raise ApiError(404, 'No such endpoint.')
        except ApiError as err:
            self._send_json(err.status, {'error': err.message})
        except json.JSONDecodeError:
            self._send_json(400, {'error': 'The request body is not valid JSON.'})
        except Exception as err:  # never leave the browser hanging
            self._send_json(500, {'error': str(err)})

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == '/api/health':
            version = subprocess.run(
                ['qpdf', '--version'], capture_output=True, text=True
            ).stdout.strip()
            self._send_json(200, {'qpdf': version.splitlines()[0] if version else None})
            return

        if not WEB_ROOT.is_dir():
            hint = b'The web UI is not built yet. Run: cd web && npm ci && npm run build'
            self._send(200, hint, 'text/plain; charset=utf-8')
            return

        # Anything that is not a real file falls back to index.html, so Angular's
        # router owns the URL space.
        wanted = (WEB_ROOT / route.lstrip('/')).resolve()
        if not str(wanted).startswith(str(WEB_ROOT)) or not wanted.is_file():
            wanted = WEB_ROOT / 'index.html'
        types = {
            '.html': 'text/html; charset=utf-8',
            '.js': 'text/javascript',
            '.css': 'text/css',
            '.ico': 'image/x-icon',
            '.svg': 'image/svg+xml',
            '.json': 'application/json',
            '.woff2': 'font/woff2',
        }
        self._send(
            200, wanted.read_bytes(), types.get(wanted.suffix, 'application/octet-stream')
        )


def main() -> None:
    parser = argparse.ArgumentParser(description='Browser UI for pdf-seal.')
    parser.add_argument('--port', type=int, default=8000)
    # Loopback by default on purpose: this server seals whatever it is given and
    # has no authentication, so it has no business being reachable from a network.
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()

    if not shutil.which('qpdf'):
        raise SystemExit('qpdf is missing. Install it: apt install qpdf / brew install qpdf')

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'pdf-seal on http://{args.host}:{args.port}  (uploads in {UPLOADS})')
    if not WEB_ROOT.is_dir():
        print('The web UI is not built. Run: cd web && npm ci && npm run build')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nstopping')


if __name__ == '__main__':
    main()
