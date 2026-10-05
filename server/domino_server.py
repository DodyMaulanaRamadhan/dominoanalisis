#!/usr/bin/env python3
"""Domino Analyzer Pro — HTTP server (API + static UI). v3

Endpoints:
    GET  /                  -> web/index.html
    GET  /<path>            -> static files from web/
    GET  /api/health        -> server + engine status
    POST /api/analyze       -> run C++ Monte-Carlo analysis (JSON in/out)
    POST /api/selftest      -> run C++ engine self-test (JSON in/out)
    POST /api/meta          -> remaining-tile info for the UI

The heavy computation lives in the C++ engine (bin/domino_engine); this
server only validates input, normalizes tile keys, spawns the engine, and
forwards its JSON.

Optional hardening (for public tunnels):
    APP_TOKEN=secret python server/domino_server.py
    -> POST /api/* then require header  X-App-Token: secret

Port/host overrides:
    DOMINO_PORT=8080 HOST=0.0.0.0 python server/domino_server.py
"""
from __future__ import annotations

import hmac
import json
import os
import pathlib
import re
import subprocess
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
BIN_DIR = ROOT / "bin"

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("DOMINO_PORT", "2024"))
if PORT <= 0:
    PORT = 2024  # PORT=0 biasanya artefak environment, bukan niat pengguna
APP_TOKEN = os.environ.get("APP_TOKEN", "").strip()
MAX_BODY = 1 << 20  # 1 MiB

# Dikirim di SETIAP respons (static & JSON): anti-sniff, anti-clickjacking,
# CSP minimal — app hanya memuat aset same-origin tanpa inline script.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
    ),
}

if sys.platform == "win32":
    ENGINE = BIN_DIR / "domino_engine.exe"
else:
    ENGINE = BIN_DIR / "domino_engine"

# "6-1", "6|1", "6:1", "6 1", "61" -> all accepted, normalized to "1-6"
KEY_RE = re.compile(r"^\s*([0-6])\s*[-|:. ]?\s*([0-6])\s*$")


def normalize_key(raw) -> str | None:
    """Normalize a user-supplied tile key to canonical 'lo-hi', or None."""
    if not isinstance(raw, str):
        return None
    m = KEY_RE.match(raw)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    return f"{min(a, b)}-{max(a, b)}"


def normalize_tile_list(value) -> tuple[list[str] | None, str]:
    """Return (normalized list, error message). Error message empty on success."""
    if value is None:
        return [], ""
    if not isinstance(value, list):
        return None, "harus array"
    out: list[str] = []
    for idx, item in enumerate(value):
        key = normalize_key(item)
        if key is None:
            # Jangan echo isi `item`: pesan error bisa direfleksikan ke
            # innerHTML oleh klien (XSS). Sebutkan posisinya saja.
            return None, (
                f"format kartu tidak dikenal (elemen ke-{idx + 1}) — gunakan angka 0..6, "
                "contoh yang benar: '3-5' atau '6-1' (urutan bebas)"
            )
        out.append(key)
    return out, ""


def engine_command(payload: dict) -> tuple[dict, HTTPStatus]:
    """Send a JSON payload to the C++ engine.

    Return (result, status). `result` is what the engine produced (or an error
    dict we synthesised); `status` is the HTTP status the caller MUST send —
    never 200 for a failed command, so external clients can branch on the
    status code alone instead of having to parse the body.
    """
    if not ENGINE.exists():
        return ({"ok": False,
                 "error": "engine belum di-build. Jalankan: python tools/build_engine.py"},
                HTTPStatus.SERVICE_UNAVAILABLE)
    try:
        proc = subprocess.run(
            [str(ENGINE)],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return ({"ok": False, "error": "engine timeout (>300s)"},
                HTTPStatus.GATEWAY_TIMEOUT)
    if proc.returncode != 0:
        # Detail crash hanya untuk log server — jangan bocorkan ke klien.
        print(f"[engine] exit {proc.returncode}: "
              f"{proc.stderr.decode(errors='replace')[:400]}", file=sys.stderr)
        return ({"ok": False,
                 "error": f"engine error (exit {proc.returncode}) — detail ada di log server"},
                HTTPStatus.INTERNAL_SERVER_ERROR)
    try:
        out = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        return ({"ok": False, "error": "engine menghasilkan output tidak valid"},
                HTTPStatus.BAD_GATEWAY)
    # Engine berjalan tapi menolak/menolak-logika -> kesalahan permintaan (4xx),
    # BUKAN kegagalan server. Body tetap ok:false supaya UI yang hanya
    # membaca `ok` tetap menampilkan pesan errornya.
    if isinstance(out, dict) and out.get("ok") is False:
        return (out, HTTPStatus.BAD_REQUEST)
    return (out, HTTPStatus.OK)


def validate_analyze(req: dict) -> str | None:
    """Return an error message, or None if the request looks sane.

    Assumes tile lists are already normalized by the caller.
    """
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

    # numSims = work factor per request — wajib dibatasi (anti-DoS CPU)
    try:
        nsims = int(req.get("numSims", 1000))
    except (TypeError, ValueError):
        return "numSims harus angka 1..10000"
    if not (1 <= nsims <= 10000):
        return "numSims harus angka 1..10000"
    req["numSims"] = nsims

    hand = req.get("myHand", [])
    played = req.get("played", [])
    if len(set(hand)) != len(hand):
        return "ada kartu duplikat di myHand"
    if set(hand) & set(played):
        return "kartu tidak bisa di tangan dan di papan sekaligus"
    if len(hand) + len(played) > 28:
        return "total kartu diketahui melebihi 28"

    # --- v3 fields ---
    ns = req.get("nextSeat", 1)
    if not isinstance(ns, int) or not (0 <= ns < n):
        return f"nextSeat harus angka 0..{n - 1}"
    if req.get("deadlockRule", "lowest") not in ("lowest", "average"):
        return "deadlockRule harus 'lowest' atau 'average'"
    if req.get("tieRule", "win") not in ("win", "lose"):
        return "tieRule harus 'win' atau 'lose'"
    if not isinstance(req.get("cangkul", True), bool):
        return "cangkul harus boolean"

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

    pb = req.get("playedBy")
    if pb is not None:
        if not isinstance(pb, list) or len(pb) != len(played):
            return "playedBy harus array sepanjang played"
        for w in pb:
            if not isinstance(w, str) or not (
                w in ("me", "unknown") or re.fullmatch(r"opp[1-4]", w)
            ):
                return "playedBy hanya boleh 'me', 'unknown', atau 'opp1'..'opp4'"
    return None


def remaining_pieces(req: dict) -> dict:
    """Pieces not in my hand and not played, keyed 'a-b'."""
    hand = set(req.get("myHand", []))
    played = set(req.get("played", []))
    pieces = []
    for a in range(7):
        for b in range(a, 7):
            key = f"{a}-{b}"
            if key not in hand and key not in played:
                pieces.append(key)
    return {"ok": True, "remaining": pieces}


class Handler(BaseHTTPRequestHandler):
    server_version = "DominoAnalyzerPy/3.0"

    # ---- helpers -------------------------------------------------------
    def _send_json(self, obj: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, rel: str) -> None:
        web_root = WEB_DIR.resolve()
        target = (WEB_DIR / rel).resolve()
        # is_relative_to: rel benar-benar di dalam web/ (aman utk sibling
        # "web*" & symlink keluar — cek prefix string lama bisa dilewati)
        if not target.is_relative_to(web_root):
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
            ".webmanifest": "application/manifest+json",
            ".woff2": "font/woff2",
        }.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        # CORS "simple request" (Content-Type text/plain) dikirim browser tanpa
        # preflight — tolak di sini agar halaman lintas-situs tak bisa memicu
        # /api (CSRF/DoS drive-by ke localhost).
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return None
        # Origin yang ada tapi beda dengan Host = permintaan lintas-situs.
        origin = self.headers.get("Origin")
        if origin is not None:
            origin_netloc = origin.split("://", 1)[-1].rstrip("/").lower()
            if origin_netloc != self.headers.get("Host", "").lower():
                return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0 or length > MAX_BODY:
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
            return None

    def _authorized(self) -> bool:
        """APP_TOKEN mode: POST /api/* requires the right X-App-Token."""
        if not APP_TOKEN:
            return True
        # compare_digest: perbandingan waktu-konstan (tahan timing-oracle)
        return hmac.compare_digest(
            self.headers.get("X-App-Token", "").encode("utf-8"),
            APP_TOKEN.encode("utf-8"),
        )

    # ---- HTTP methods --------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send_static("index.html")
        elif path == "/api/health":
            self._send_json({
                "ok": True,
                "server": "python",
                "version": 3,
                "engine": ENGINE.name if ENGINE.exists() else None,
                "engineReady": ENGINE.exists(),
                "tokenRequired": bool(APP_TOKEN),
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
        if path.startswith("/api/") and not self._authorized():
            self._send_json({"ok": False, "error": "token tidak valid atau hilang "
                                                  "(header X-App-Token)"},
                            HTTPStatus.UNAUTHORIZED)
            return
        body = self._read_json_body()
        if body is None:
            self._send_json({"ok": False, "error": "body JSON tidak valid"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(body, dict):
            self._send_json({"ok": False, "error": "body harus objek JSON"}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/analyze":
            # normalize tile keys first (friendly input: "6-1" -> "1-6")
            norm_err = None
            for field in ("myHand", "played"):
                norm, err = normalize_tile_list(body.get(field))
                if err:
                    norm_err = f"myHand/played: {err}"
                    break
                body[field] = norm
            if norm_err:
                self._send_json({"ok": False, "error": norm_err}, HTTPStatus.BAD_REQUEST)
                return
            err = validate_analyze(body)
            if err:
                self._send_json({"ok": False, "error": err}, HTTPStatus.BAD_REQUEST)
                return
            result, status = engine_command(body)
            self._send_json(result, status)
        elif path == "/api/selftest":
            # Self-test gagal = engine bermasalah, bukan salah permintaan.
            result, status = engine_command({"cmd": "selftest"})
            if status == HTTPStatus.OK and result.get("ok") is False:
                status = HTTPStatus.INTERNAL_SERVER_ERROR
            self._send_json(result, status)
        elif path == "/api/meta":
            for field in ("myHand", "played"):
                norm, err = normalize_tile_list(body.get(field))
                if err:
                    self._send_json({"ok": False, "error": f"{field}: {err}"},
                                    HTTPStatus.BAD_REQUEST)
                    return
                body[field] = norm
            self._send_json(remaining_pieces(body))
        else:
            self._send_json({"ok": False, "error": "endpoint tidak dikenal"}, HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stderr.write("[http] %s - %s\n" % (self.address_string(), fmt % args))


def main() -> int:
    if not ENGINE.exists():
        print("[server] PERINGATAN: engine C++ belum ada — jalankan: python tools/build_engine.py",
              file=sys.stderr)
    if APP_TOKEN:
        print("[server] mode proteksi AKTIF: POST /api/* butuh header X-App-Token", file=sys.stderr)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[server] Domino Analyzer Pro v3 -> http://{HOST}:{PORT}", file=sys.stderr)
    print(f"[server] engine: {ENGINE} ({'OK' if ENGINE.exists() else 'MISSING'})", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] dimatikan.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
