#!/usr/bin/env python3
"""Bangun mesin dari git HEAD (sebelum optimasi) dan rekam golden output-nya.

Dipakai sebagai baseline pembanding: `tools/audit_golden.py verify <dir>` lalu
membuktikan mesin hasil optimasi menghasilkan angka yang identik.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import audit_golden as ag  # noqa: E402
import build_engine as be  # noqa: E402

WORK = pathlib.Path(tempfile.gettempdir()) / "domino_baseline"
WORK.mkdir(parents=True, exist_ok=True)
GOLD = pathlib.Path(tempfile.gettempdir()) / "domino_audit_head"
GOLD.mkdir(parents=True, exist_ok=True)

src = WORK / "domino_engine_baseline.cpp"
old = subprocess.run(["git", "show", "HEAD:engine/domino_engine.cpp"],
                     cwd=ROOT, capture_output=True, check=True)
src.write_bytes(old.stdout)
print(f"[baseline] sumber HEAD -> {src} ({len(old.stdout)} bytes)")

out = WORK / ("domino_engine_baseline.exe" if sys.platform == "win32" else "domino_engine_baseline")
# PENTING: arahkan compiler ke sumber HEAD, bukan SRC (sumber kerja).
be.SRC = src
vcvars = be.find_msvc()
if not be.build_with_msvc(vcvars, out, False):
    raise SystemExit("[baseline] build MSVC gagal")
print(f"[baseline] build OK -> {out}")

ag.ENGINE = out
ag.OUT = GOLD
rc = ag.cmd_capture()
print(f"[baseline] golden tersimpan di {GOLD} (exit {rc})")
sys.exit(rc)
