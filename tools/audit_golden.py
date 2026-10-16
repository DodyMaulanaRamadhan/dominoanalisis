#!/usr/bin/env python3
"""Audit harness: capture golden engine outputs + measure throughput.

Usage:
    python tools/audit_golden.py capture   # tulis golden/*.json + bench_before.txt
    python tools/audit_golden.py verify    # bandingkan output mesin dengan golden/
    python tools/audit_golden.py bench     # ukur sims/detik saja

Direktori golden default: %TEMP%/domino_audit (di luar repo, tidak ikut commit).
Alasan: verifikasi refactor performa harus membuktikan output **identik**,
bukan sekadar "masih jalan".
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ROOT / "bin" / ("domino_engine.exe" if sys.platform == "win32" else "domino_engine")
OUT = pathlib.Path(tempfile.gettempdir()) / "domino_audit"

BASE = {
    "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7, "numSims": 300,
    "seed": 20240922, "leftEnd": 3, "rightEnd": 5,
    "myHand": ["0-0", "1-2", "3-3", "4-6", "5-5", "6-6", "2-3"],
    "played": ["3-4", "1-5", "2-6"], "playedBy": ["me", "opp1", "opp2"],
    "nextSeat": 1, "deadlockRule": "lowest", "tieRule": "win",
    "cangkul": True, "adversarial": False,
    "opponents": [{"passes": 1, "eliminated": [3, 1]}, {}, {"passes": 0, "eliminated": []}],
}

SCENARIOS = {
    "s1_base": BASE,
    "s2_adversarial": {**BASE, "adversarial": True},
    "s3_two_player": {
        "cmd": "analyze", "numPlayers": 2, "cardsPerPlayer": 7, "numSims": 400,
        "seed": 777, "leftEnd": -1, "rightEnd": -1,
        "myHand": ["0-0", "1-2", "3-3", "4-6", "5-5", "6-6", "2-3"],
        "played": [], "opponents": [{}],
    },
    "s4_cangkul_off": {**BASE, "cangkul": False, "deadlockRule": "average", "tieRule": "lose"},
    "s5_first_move": {
        "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7, "numSims": 250,
        "seed": 12345, "leftEnd": -1, "rightEnd": -1,
        "myHand": ["0-0", "0-1", "2-2", "3-4", "5-6", "6-6", "1-1"],
        "played": [], "opponents": [{}],
    },
    # numSims >= 2000 -> memicu jalur PARALEL (12 thread). Tanpa skenario ini,
    # verifikasi hanya menguji jalur sekuensial.
    "s7_parallel_5k": {**BASE, "numSims": 5000},
    "s8_parallel_boundary_2k": {**BASE, "numSims": 2000, "seed": 4242},
    "s9_unknown_empty": {
        "cmd": "analyze", "numPlayers": 2, "cardsPerPlayer": 14, "numSims": 100,
        "seed": 1, "leftEnd": -1, "rightEnd": -1,
        "myHand": [f"{a}-{b}" for a in range(7) for b in range(a, 7)][:14],
        "played": [f"{a}-{b}" for a in range(7) for b in range(a, 7)][14:],
        "playedBy": ["unknown"] * 14, "opponents": [{}],
    },
    "s6_three_player_attrib": {
        "cmd": "analyze", "numPlayers": 3, "cardsPerPlayer": 6, "numSims": 200,
        "seed": 99, "leftEnd": 6, "rightEnd": 0,
        "myHand": ["1-1", "2-5", "4-4", "6-6", "0-3"],
        "played": ["2-6", "0-1", "4-5"], "playedBy": ["me", "opp2", "opp1"],
        "opponents": [{"passes": 2, "eliminated": [5]}, {"passes": 1, "eliminated": [2]}],
    },
}


def run_raw(payload: dict) -> tuple[int, str]:
    """Jalankan mesin, kembalikan (exit code, stdout). Tidak pernah raise."""
    proc = subprocess.run([str(ENGINE)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, timeout=900)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def run(payload: dict) -> str:
    code, text = run_raw(payload)
    if code != 0:
        raise SystemExit(f"engine exit {code}: {text[:300]!r}")
    return text


def write_text_raw(path: pathlib.Path, text: str) -> None:
    """Tulis apa adanya: newline="" mencegah translasi \\n -> \\r\\n di Windows
    (translasi itu akan membuat perbandingan byte selalu gagal)."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def read_text_raw(path: pathlib.Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def cmd_capture() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in SCENARIOS.items():
        code, text = run_raw(payload)
        if code != 0:
            # Mesin baseline bisa crash (mis. modulo nol pada pool kosong).
            # Catat sebagai penanda supaya verify() memeriksa "sudah tidak crash".
            write_text_raw(OUT / f"{name}.json",
                           json.dumps({"__crash__": True, "exit": code}))
            print(f"[golden] {name}: CRASH (exit {code}) — dicatat sebagai regresi")
            continue
        write_text_raw(OUT / f"{name}.json", text)
        print(f"[golden] {name}: {len(text)} chars")
    bench_payload = {**BASE, "numSims": 20000}
    t0 = time.perf_counter()
    res = json.loads(run(bench_payload))
    dt = time.perf_counter() - t0
    total = bench_payload["numSims"] * len(res["moves"])
    write_text_raw(OUT / "bench_before.txt", f"{dt:.6f} {total}")
    write_text_raw(OUT / "bench.txt", f"{dt:.6f} {total}")
    print(f"[bench] sebelum: {dt:.2f}s untuk {total:,} simulasi-engine "
          f"({total / dt:,.0f} sim/detik)")
    return 0


def golden_dir() -> pathlib.Path:
    """Direktori golden: argumen kedua opsional (mis. hasil build baseline HEAD)."""
    if len(sys.argv) > 2:
        return pathlib.Path(sys.argv[2])
    return OUT


def cmd_verify() -> int:
    bad = 0
    gdir = golden_dir()
    for name, payload in SCENARIOS.items():
        ref = gdir / f"{name}.json"
        if not ref.exists():
            print(f"[verify] LEWAT {name}: golden tidak ada")
            continue
        expected_crash = "__crash__" in read_text_raw(ref)
        code, got = run_raw(payload)
        if expected_crash:
            if code == 0:
                print(f"[verify] OK {name}: crash baseline HILANG (bug diperbaiki)")
            else:
                bad += 1
                print(f"[verify] GAGAL {name}: masih crash (exit {code})")
            continue
        if code != 0:
            bad += 1
            print(f"[verify] GAGAL {name}: mesin crash (exit {code})")
            continue
        if got == read_text_raw(ref):
            print(f"[verify] IDENTIK {name}")
        else:
            bad += 1
            print(f"[verify] BERBEDA {name}  <-- regresi numerik")
            a, b = json.loads(read_text_raw(ref)), json.loads(got)
            for k in a:
                if a.get(k) != b.get(k):
                    print(f"          field beda: {k}")
    print("[verify] hasil:", "SEMUA IDENTIK" if bad == 0 else f"{bad} skenario BERBEDA")
    return 1 if bad else 0


def _flat(d, pre=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, pre + k + "."))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, dict):
                    out.update(_flat(x, f"{pre}{k}[{i}]."))
                else:
                    out[f"{pre}{k}[{i}]"] = x
        else:
            out[pre + k] = v
    return out


def cmd_diff() -> int:
    """Tunjukkan field mana yang berbeda dari golden (untuk melacak regresi)."""
    name = sys.argv[2] if len(sys.argv) > 2 else "s3_two_player"
    gdir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else OUT
    ref = json.loads(read_text_raw(gdir / f"{name}.json"))
    got = json.loads(run(SCENARIOS[name]))
    a, b = _flat(ref), _flat(got)
    keys = [k for k in a if a[k] != b.get(k)]
    print(f"[diff] {name}: {len(keys)} field beda dari {len(a)}")
    for k in keys[:40]:
        print(f"   {k}: ref={a[k]!r} got={b.get(k)!r}")
    return 1 if keys else 0


def cmd_bench() -> int:
    bench_payload = {**BASE, "numSims": 20000}
    t0 = time.perf_counter()
    res = json.loads(run(bench_payload))
    dt = time.perf_counter() - t0
    total = bench_payload["numSims"] * len(res["moves"])
    print(f"[bench] {dt:.2f}s untuk {total:,} simulasi-engine ({total / dt:,.0f} sim/detik)")
    ref = OUT / "bench_before.txt"
    if ref.exists():
        before = float(read_text_raw(ref).split()[0])
        print(f"[bench] sebelum {before:.2f}s -> sekarang {dt:.2f}s "
              f"= {before / dt:.2f}x lebih cepat")
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "capture"
    if mode == "capture":
        return cmd_capture()
    if mode == "verify":
        return cmd_verify()
    if mode == "bench":
        return cmd_bench()
    if mode == "diff":
        return cmd_diff()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
