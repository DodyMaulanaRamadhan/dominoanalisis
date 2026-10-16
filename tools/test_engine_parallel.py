#!/usr/bin/env python3
"""Regression tests: paralelisasi mesin + perbaikan crash.

Dua hal yang dijaga di sini:

1. **Output paralel == output sekuensial.** Mesin menurunkan state RNG tiap
   simulasi dari snapshot stream yang sama, jadi jumlah thread tidak boleh
   mengubah satu angka pun. Dibandingkan byte-per-byte dari biner yang sama.
2. **Pool kartu tak diketahui kosong tidak lagi membuat mesin crash.** Sebelum
   perbaikan, `shuffle` pada vector kosong memakai indeks SIZE_MAX dan
   `nextInt(0)` (modulo nol) -> proses mati (0xC0000094 / 0xC0000005).

Jalankan: python tools/test_engine_parallel.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ROOT / "bin" / ("domino_engine.exe" if sys.platform == "win32" else "domino_engine")

ALL_TILES = [f"{a}-{b}" for a in range(7) for b in range(a, 7)]

BASE = {
    "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7,
    "seed": 20240922, "leftEnd": 3, "rightEnd": 5,
    "myHand": ["0-0", "1-2", "3-3", "4-6", "5-5", "6-6", "2-3"],
    "played": ["3-4", "1-5", "2-6"], "playedBy": ["me", "opp1", "opp2"],
    "nextSeat": 1, "deadlockRule": "lowest", "tieRule": "win",
    "cangkul": True, "adversarial": False,
    "opponents": [{"passes": 1, "eliminated": [3, 1]}, {}, {}],
}

# numSims >= 2000 memakai jalur paralel; di bawah itu jalur sekuensial.
CASES = {
    "paralel_4p_3000": {**BASE, "numSims": 3000},
    "paralel_adversarial_2500": {**BASE, "numSims": 2500, "adversarial": True},
    "sekuensial_2p_500": {
        "cmd": "analyze", "numPlayers": 2, "cardsPerPlayer": 7, "numSims": 500,
        "seed": 777, "leftEnd": -1, "rightEnd": -1,
        "myHand": ["0-0", "1-2", "3-3", "4-6", "5-5", "6-6", "2-3"],
        "played": [], "opponents": [{}],
    },
    "boundary_2000": {**BASE, "numSims": 2000, "seed": 4242},
}


def run(payload: dict, threads: int | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    if threads is not None:
        env["DOMINO_THREADS"] = str(threads)
    proc = subprocess.run([str(ENGINE)], input=json.dumps(payload).encode("utf-8"),
                          capture_output=True, env=env, timeout=900)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


@unittest.skipUnless(ENGINE.exists(), "engine belum di-build (python tools/build_engine.py)")
class TestEngineParallel(unittest.TestCase):
    def test_parallel_equals_sequential(self):
        for name, payload in CASES.items():
            with self.subTest(case=name):
                code1, out1 = run(payload, threads=1)
                self.assertEqual(code1, 0, f"{name}: exit {code1} pada 1 thread")
                for threads in (2, 8):
                    code_n, out_n = run(payload, threads=threads)
                    self.assertEqual(code_n, 0, f"{name}: exit {code_n} pada {threads} thread")
                    self.assertEqual(out1, out_n,
                                     f"{name}: output {threads} thread berbeda dari 1 thread")

    def test_default_threads_matches_sequential(self):
        payload = CASES["paralel_4p_3000"]
        _, seq = run(payload, threads=1)
        _, default = run(payload, threads=None)
        self.assertEqual(seq, default, "output mode default berbeda dari mode sekuensial")

    def test_threads_zero_or_negative_means_sequential(self):
        payload = CASES["sekuensial_2p_500"]
        _, seq = run(payload, threads=1)
        for bad in (0, -3):
            code, out = run(payload, threads=bad)
            self.assertEqual(code, 0, f"DOMINO_THREADS={bad} membuat mesin gagal")
            self.assertEqual(seq, out, f"DOMINO_THREADS={bad} tidak sama dengan sekuensial")

    def test_empty_unknown_pool_does_not_crash(self):
        # 2 pemain x 14 kartu: seluruh 28 kartu diketahui (14 di tangan, 14 di
        # papan) -> pool tak diketahui kosong. Sebelum perbaikan: crash.
        payload = {
            "cmd": "analyze", "numPlayers": 2, "cardsPerPlayer": 14, "numSims": 50,
            "seed": 1, "leftEnd": -1, "rightEnd": -1,
            "myHand": ALL_TILES[:14], "played": ALL_TILES[14:],
            "playedBy": ["unknown"] * 14, "opponents": [{}],
        }
        code, out = run(payload, threads=1)
        self.assertEqual(code, 0, f"mesin crash (exit {code}) saat pool kosong")
        self.assertTrue(json.loads(out).get("ok"), "balasan harus ok:true")


@unittest.skipUnless(ENGINE.exists(), "engine belum di-build (python tools/build_engine.py)")
@unittest.skipUnless(os.environ.get("DOMINO_SLOW_TESTS"),
                     "tes beban penuh: set DOMINO_SLOW_TESTS=1 (≈1–2 menit)")
class TestEngineHeavyLoad(unittest.TestCase):
    """Tier 1.700.000 simulasi: beban maksimum yang ditawarkan aplikasi.

    Dua hal yang harus tetap benar justru ketika bebannya ekstrem:
    jumlah thread tidak mengubah hasil, dan angka hasilnya tetap konsisten
    (menang + kalah = jumlah simulasi, konservasi kartu terjaga, interval
    keyakinan benar-benar menyempit ke ±0,1%).
    """

    NUM_SIMS = 1700000
    PAYLOAD = {
        **BASE, "numSims": NUM_SIMS,
    }

    @classmethod
    def setUpClass(cls):
        cls.code_seq, cls.out_seq = run(cls.PAYLOAD, threads=1)

    def test_no_crash_and_ok(self):
        self.assertEqual(self.code_seq, 0, "mesin gagal pada beban 1,7 juta simulasi")
        data = json.loads(self.out_seq)
        self.assertTrue(data.get("ok"), "balasan harus ok:true")
        self.assertEqual(data["numSims"], self.NUM_SIMS, "numSims tidak boleh dipangkas")

    def test_counts_and_conservation_at_full_load(self):
        data = json.loads(self.out_seq)
        for mv in data["moves"]:
            with self.subTest(move=mv["key"]):
                self.assertEqual(mv["wins"] + mv["losses"], self.NUM_SIMS,
                                 "menang + kalah harus sama dengan jumlah simulasi")
                self.assertEqual(mv["winByEmpty"] + mv["winByValue"], mv["wins"],
                                 "rincian kemenangan harus konsisten")
                self.assertTrue(mv["conserved"], "konservasi kartu gagal di beban penuh")
                self.assertLessEqual(mv["winLo"], mv["winRate"])
                self.assertLessEqual(mv["winRate"], mv["winHi"])
                lebar = mv["winHi"] - mv["winLo"]
                self.assertLess(lebar, 0.002,
                                f"interval terlalu lebar untuk 1,7 juta sim: {lebar:.5f}")

    def test_rankScore_sorted(self):
        data = json.loads(self.out_seq)
        scores = [m["rankScore"] for m in data["moves"]]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "moves harus terurut rankScore menurun")

    def test_full_load_parallel_equals_sequential(self):
        for threads in (4, 12):
            code, out = run(self.PAYLOAD, threads=threads)
            self.assertEqual(code, 0, f"exit {code} pada {threads} thread")
            self.assertEqual(self.out_seq, out,
                             f"beban 1,7 juta: output {threads} thread berbeda dari 1 thread")


if __name__ == "__main__":
    unittest.main(verbosity=2)
