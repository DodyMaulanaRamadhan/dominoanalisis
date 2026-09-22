#!/usr/bin/env python3
"""Run the C++ engine self-test and report pass/fail as exit code."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ROOT / "bin" / ("domino_engine.exe" if sys.platform == "win32" else "domino_engine")


def main() -> int:
    if not ENGINE.exists():
        print(f"[selftest] engine tidak ditemukan: {ENGINE}", file=sys.stderr)
        return 1
    proc = subprocess.run([str(ENGINE)], input='{"cmd":"selftest"}'.encode("utf-8"),
                          capture_output=True, timeout=300)
    if proc.returncode != 0:
        print(f"[selftest] engine exit {proc.returncode}", file=sys.stderr)
        return 1
    try:
        data = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        print("[selftest] output engine tidak valid", file=sys.stderr)
        return 1

    for check in data.get("checks", []):
        status = "PASS" if check["pass"] else "FAIL"
        print(f"[selftest] [{status}] {check['name']} — {check['detail']}")
    if not data.get("allPass"):
        return 1
    print("[selftest] semua check LOLOS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
