#!/usr/bin/env python3
"""Benchmark 3 arah: mesin HEAD (baseline) vs optimasi 1 thread vs optimasi paralel.

Bergantian beberapa putaran supaya tidak tertipu cache disk/CPU. Sementara —
bagian dari audit, bukan bagian aplikasi.
"""
from __future__ import annotations

import json
import os
import pathlib
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import audit_golden as ag  # noqa: E402

BASE_BIN = pathlib.Path(tempfile.gettempdir()) / "domino_baseline" / "domino_engine_baseline.exe"
NEW_BIN = ag.ENGINE
REPS = 5


def time_run(binary: pathlib.Path, payload: dict, env_extra: dict | None = None) -> tuple[float, int]:
    env = dict(os.environ)
    env.update(env_extra or {})
    t0 = time.perf_counter()
    proc = subprocess.run([str(binary)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=900, env=env)
    dt = time.perf_counter() - t0
    if proc.returncode != 0:
        raise SystemExit(f"{binary.name} exit {proc.returncode}")
    res = json.loads(proc.stdout.decode("utf-8"))
    return dt, payload["numSims"] * len(res["moves"])


def bench(num_sims: int) -> None:
    payload = {**ag.BASE, "numSims": num_sims}
    variants = {
        "HEAD (baseline)": (BASE_BIN, None),
        "optimasi 1 thread": (NEW_BIN, {"DOMINO_THREADS": "1"}),
        "optimasi paralel": (NEW_BIN, None),
    }
    times: dict[str, list[float]] = {k: [] for k in variants}
    total = 0
    for _ in range(REPS):
        for label, (binary, env) in variants.items():
            dt, total = time_run(binary, payload, env)
            times[label].append(dt)
    print(f"\nbeban: {num_sims:,} sim x langkah = {total:,} simulasi-engine, {REPS} putaran")
    head = statistics.median(times["HEAD (baseline)"])
    for label in variants:
        med = statistics.median(times[label])
        print(f"  {label:18s}: {med:.3f}s  ({total/med:>9,.0f} sim/detik)  {head/med:5.2f}x vs HEAD")


def main() -> int:
    if not BASE_BIN.exists():
        raise SystemExit("jalankan tools/_baseline_check.py dulu")
    print(f"inti logis: {os.cpu_count()} | DOMINO_THREADS default = semua inti")
    bench(20000)
    bench(50000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
