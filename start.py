#!/usr/bin/env python3
"""One-shot launcher for Domino Analyzer Pro.

  python start.py            # build engine (jika perlu) + jalankan server di :2024
  python start.py --check    # build + self-test engine, tanpa menjalankan server
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
PORT = 2024


def run_module(script: str, *args: str) -> int:
    proc = subprocess.run([sys.executable, str(ROOT / script), *args])
    return proc.returncode


def main() -> int:
    check_only = "--check" in sys.argv

    # 1) build engine (idempotent — skipped when binary is up to date)
    if run_module("tools/build_engine.py") != 0:
        print("[start] build engine gagal.", file=sys.stderr)
        return 1

    # 2) engine self-test
    if run_module("tools/selftest.py") != 0:
        print("[start] self-test engine GAGAL — perhitungan mungkin tidak akurat.",
              file=sys.stderr)
        return 1

    if check_only:
        print("[start] build + self-test OK (tanpa menjalankan server).")
        return 0

    # 3) sanity-check that the port is free
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1):
            print(f"[start] Port {PORT} sudah dipakai — server lain mungkin berjalan.",
                  file=sys.stderr)
            return 1
    except (urllib.error.URLError, TimeoutError, OSError):
        pass  # connection refused = port free

    # 4) serve
    return run_module("server/domino_server.py")


if __name__ == "__main__":
    sys.exit(main())
