#!/usr/bin/env python3
"""Domino Analyzer Pro — HTTP server (API + static UI).

Endpoints:
    GET  /                  -> web/index.html
    GET  /<path>            -> static files from web/
    GET  /api/health        -> server + engine status
    POST /api/analyze       -> run C++ Monte-Carlo analysis (JSON in/out)
    POST /api/selftest      -> run C++ engine self-test (JSON in/out)
    GET  /api/meta          -> new tile info for the remaining-pool UI

The heavy computation lives in the C++ engine (bin/domino_engine); this
server only validates input, spawns the engine, and forwards its JSON.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
BIN_DIR = ROOT / "bin"

PORT = 2024
HOST = "127.0.0.1"
MAX_BODY = 1 << 20  # 1 MiB

if sys.platform == "win32":
    ENGINE = BIN_DIR / "domino_engine.exe"
else:
    ENGINE = BIN_DIR / "domino_engine"

VALID_KEY = re.compile(r"^[0-6]-[0-6]$")


def engine_command(payload: dict) -> dict:
    """Send a JSON payload to the C++ engine, return parsed JSON output."""
    if not ENGINE.exists():
        return {"ok": False, "error": "engine belum di-build. Jalankan: python tools/build_engine.py"}
    try:
        proc = subprocess.run(
            [str(ENGINE)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "engine timeout (>120s)"}
    if proc.returncode != 0:
        return {"ok": False, "error": f"engine exit {proc.returncode}: {proc.stderr.decode(errors='replace')[:400]}"}
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "error": "engine menghasilkan output tidak valid"}


def validate_analyze(req: dict) -> str | None:
    """Return an error message, or None if the request looks sane."""
    if not isinstance(req, dict):
        return "body harus objek JSON"
    try:
        n = int(req["numPlayers"])
        c = int(req["cardsPerPlayer"])
    except (KeyError, TypeError, ValueError):
        return "numPlayers dan cardsPerPlayer wajib angka"
    if n not in (2, 3, 4):
        return "numPlayers harus 2..4"
    if not (1 <= c <= 14):
        return "cardsPerPlayer tidak wajar"
    if n * c > 28:
        return "total kartu melebihi 28"
    for field in ("myHand", "played"):
        arr = req.get(field, [])
        if not isinstance(arr, list):
            return f"{field} harus array"
        for k in arr:
            if not isinstance(k, str) or not VALID_KEY.match(k):
                return f"key kartu tidak valid di {field}: {k!r}"
    hand = req.get("myHand", [])
    played = req.get("played", [])
    if len(set(hand)) != len(hand):
        return "ada kartu duplikat di myHand"
    if set(hand) & set(played):
        return "kartu tidak bisa di tangan dan di papan sekaligus"
    if len(hand) + len(played) > 28:
        return "total kartu diketahui melebihi 28"
    opps = req.get("opponents", [])
    if not isinstance(opps, list):
        return "opponents harus array"
    for o in opps:
        if not isinstance(o, dict):
            return "elemen opponents harus objek"
        el = o.get("eliminated", [])
        if not isinstance(el, list) or any(
            (not isinstance(x, int)) or not (0 <= x <= 6) for x in el
        ):
            return "eliminated harus array angka 0..6"
    return None


def remaining_pieces(req: dict) -> dict:
    """Pieces not in my hand and not played, keyed 'a-b'."""
    hand = set(req.get("myHand", []))
    played = set(req.get("played", []))
    pieces = []
    for a in range(7):
        for b in range(a, 8):
            key = f"{a}-{b}"
            if key not in hand and key not in played:
                pieces.append(key)
    return {"ok": True, "remaining": pieces}


class Handler(BaseHTTPRequestHandler):
    server_version = "DominoAnalyzerPy/2.0"

    # ---- helpers -------------------------------------------------------
    def _send_json(self, obj: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel: str) -> None:
        target = (WEB_DIR / rel).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())):
            self._send_json({"ok": False, "error": "forbidden"}, HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self._send_json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    # ---- HTTP methods --------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send_static("index.html")
        elif path == "/api/health":
            self._send_json({
                "ok": True,
                "server": "python",
                "engine": ENGINE.name if ENGINE.exists() else None,
                "engineReady": ENGINE.exists(),
            })
        elif path == "/api/meta":
            self._send_json({"ok": False, "error": "gunakan POST untuk /api/meta"},
                            HTTPStatus.METHOD_NOT_ALLOWED)
        elif path.startswith("/api/"):
            self._send_json({"ok": False, "error": "endpoint tidak dikenal"}, HTTPStatus.NOT_FOUND)
        else:
            rel = path.lstrip("/")
            if rel:
                self._send_static(rel)
            else:
                self._send_static("index.html")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        body = self._read_json_body()
        if body is None:
            self._send_json({"ok": False, "error": "body JSON tidak valid"}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/analyze":
            err = validate_analyze(body)
            if err:
                self._send_json({"ok": False, "error": err}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(engine_command(body))
        elif path == "/api/selftest":
            self._send_json(engine_command({"cmd": "selftest"}))
        elif path == "/api/meta":
            self._send_json(remaining_pieces(body))
        else:
            self._send_json({"ok": False, "error": "endpoint tidak dikenal"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stderr.write("[http] %s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    if not ENGINE.exists():
        print("[server] PERINGATAN: engine C++ belum ada — jalankan: python tools/build_engine.py",
              file=sys.stderr)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[server] Domino Analyzer Pro -> http://{HOST}:{PORT}", file=sys.stderr)
    print(f"[server] engine: {ENGINE} ({'OK' if ENGINE.exists() else 'MISSING'})", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] dimatikan.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
