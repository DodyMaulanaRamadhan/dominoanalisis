#!/usr/bin/env python3
"""Unit tests for the Domino Analyzer Pro HTTP server (v3).

Run:  python tools/test_server.py
Covers: tile-key normalization, request validation, /api/meta, auth token,
        and one end-to-end /api/analyze against the real engine (if built).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import unittest
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import domino_server as ds  # noqa: E402


def http_post(port: int, path: str, payload: dict, token: str = "",
               ctype: str = "application/json", raw: bytes | None = None,
               extra_headers: dict | None = None) -> tuple[int, dict]:
    data = raw if raw is not None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": ctype,
                 **(extra_headers or {}),
                 **({"X-App-Token": token} if token else {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def http_get_raw(port: int, path: str) -> tuple[int, dict, bytes]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=30) as res:
        return res.status, dict(res.headers), res.read()


def http_get(port: int, path: str) -> tuple[int, dict]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=30) as res:
        return res.status, json.loads(res.read().decode("utf-8"))


class TestNormalization(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(ds.normalize_key("3-5"), "3-5")
        self.assertEqual(ds.normalize_key("6-1"), "1-6")
        self.assertEqual(ds.normalize_key("1-6"), "1-6")

    def test_friendly_separators(self):
        self.assertEqual(ds.normalize_key("6|1"), "1-6")
        self.assertEqual(ds.normalize_key("3:2"), "2-3")
        self.assertEqual(ds.normalize_key("4 5"), "4-5")
        self.assertEqual(ds.normalize_key("61"), "1-6")

    def test_invalid(self):
        self.assertIsNone(ds.normalize_key("7-1"))
        self.assertIsNone(ds.normalize_key("a-b"))
        self.assertIsNone(ds.normalize_key(""))
        self.assertIsNone(ds.normalize_key("1-2-3"))
        self.assertIsNone(ds.normalize_key(35))  # non-string rejected

    def test_error_message_never_echoes_raw_input(self):
        # payload HTML di myHand tidak boleh muncul mentah di pesan error
        # (dulu direfleksikan ke innerHTML klien = XSS)
        norm, err = ds.normalize_tile_list(["<img src=x onerror=alert(1)>"])
        self.assertIsNone(norm)
        self.assertNotIn("<img", err)
        self.assertIn("elemen ke-1", err)


class TestValidate(unittest.TestCase):
    def base_ok(self):
        return {
            "numPlayers": 4, "cardsPerPlayer": 7,
            "myHand": ["1-6"], "played": ["3-5"],
            "nextSeat": 1, "deadlockRule": "lowest", "tieRule": "win",
            "opponents": [{}, {}, {}],
            "playedBy": ["unknown"],
        }

    def test_valid(self):
        self.assertIsNone(ds.validate_analyze(self.base_ok()))

    def test_nextSeat_bounds(self):
        bad = self.base_ok(); bad["nextSeat"] = 4
        self.assertIsNotNone(ds.validate_analyze(bad))
        bad["nextSeat"] = -1
        self.assertIsNotNone(ds.validate_analyze(bad))

    def test_rules(self):
        bad = self.base_ok(); bad["deadlockRule"] = "median"
        self.assertIsNotNone(ds.validate_analyze(bad))
        bad = self.base_ok(); bad["tieRule"] = "draw"
        self.assertIsNotNone(ds.validate_analyze(bad))

    def test_playedBy_length(self):
        bad = self.base_ok(); bad["playedBy"] = []
        self.assertIsNotNone(ds.validate_analyze(bad))
        bad = self.base_ok(); bad["playedBy"] = ["opp9"]
        self.assertIsNotNone(ds.validate_analyze(bad))

    def test_overlap_rejected(self):
        bad = self.base_ok(); bad["played"] = ["1-6"]
        self.assertIsNotNone(ds.validate_analyze(bad))

    def test_numSims_bounds(self):
        # anti-DoS: wajib 1..10000; hilang -> default 1000; bukan angka -> tolak
        self.assertIsNone(ds.validate_analyze(self.base_ok()))
        lo = self.base_ok(); lo["numSims"] = 1
        self.assertIsNone(ds.validate_analyze(lo))
        hi = self.base_ok(); hi["numSims"] = 10000
        self.assertIsNone(ds.validate_analyze(hi))
        for v in (10001, 0, -5, 10**12, "banyak", None):
            bad = self.base_ok(); bad["numSims"] = v
            self.assertIsNotNone(ds.validate_analyze(bad),
                                 f"numSims={v!r} harus ditolak")


class TestServerLive(unittest.TestCase):
    """Boots the real server on an ephemeral port and exercises endpoints."""

    @classmethod
    def setUpClass(cls):
        ds.PORT = 0  # ephemeral
        ds.APP_TOKEN = ""
        cls.httpd = ds.ThreadingHTTPServer((ds.HOST, ds.PORT), ds.Handler)
        cls.port = cls.httpd.server_address[1]
        import threading
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def test_health(self):
        status, data = http_get(self.port, "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])

    def test_meta_normalizes(self):
        status, data = http_post(self.port, "/api/meta",
                                 {"myHand": ["6-1", "0|0"], "played": []})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertNotIn("1-6", data["remaining"])
        self.assertNotIn("0-0", data["remaining"])

    def test_analyze_e2e(self):
        if not ds.ENGINE.exists():
            self.skipTest("engine belum di-build")
        payload = {
            "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7,
            "numSims": 200, "seed": 99, "leftEnd": -1, "rightEnd": -1,
            "myHand": ["0-0", "1-6", "2-5"], "played": [],
            "nextSeat": 2, "deadlockRule": "lowest", "tieRule": "win",
            "opponents": [{}, {}, {}],
        }
        status, data = http_post(self.port, "/api/analyze", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["engine"].split("/")[1][0], "3")
        self.assertIn("boneyardCount", data)
        self.assertIn("opponents", data)
        for mv in data["moves"]:
            self.assertIn("winLo", mv)
            self.assertIn("winHi", mv)
            self.assertIn("rankScore", mv)
            self.assertLessEqual(mv["winLo"], mv["winRate"] + 1e-9)
            self.assertGreaterEqual(mv["winHi"], mv["winRate"] - 1e-9)

    def test_analyze_cangkul_false_and_dead_tiles(self):
        if not ds.ENGINE.exists():
            self.skipTest("engine belum di-build")
        payload = {
            "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 6,
            "numSims": 100, "seed": 11, "leftEnd": -1, "rightEnd": -1,
            "myHand": ["0-0", "1-2", "3-4", "5-6"], "played": [],
            "cangkul": False, "nextSeat": 1, "opponents": [{}, {}, {}],
        }
        status, data = http_post(self.port, "/api/analyze", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertFalse(data["cangkul"])
        self.assertGreater(data["boneyardCount"], 0)
        self.assertGreater(len(data["deadTiles"]), 0)
        self.assertEqual(len(data["deadByNumber"]), 7)
        probs = [d["prob"] for d in data["deadTiles"]]
        self.assertEqual(probs, sorted(probs, reverse=True))
        # 28 - 4*6 = 4 kartu sisa -> ekspektasi total kartu mati = 4
        self.assertAlmostEqual(sum(data["deadByNumber"]), 4.0, places=1)

    def test_analyze_playedBy(self):
        if not ds.ENGINE.exists():
            self.skipTest("engine belum di-build")
        payload = {
            "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7,
            "numSims": 100, "seed": 7, "leftEnd": 3, "rightEnd": 5,
            "myHand": ["1-6", "2-5"], "played": ["3-5", "4-4", "6-6"],
            "playedBy": ["opp1", "opp2", "unknown"],
            "nextSeat": 1, "opponents": [{}, {}, {}],
        }
        status, data = http_post(self.port, "/api/analyze", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["hasAttribution"])
        self.assertEqual(data["opponents"][0]["heldKnown"], 1)
        self.assertEqual(data["opponents"][1]["heldKnown"], 1)

    def test_analyze_endgame_attribution(self):
        # Regresi: end-game dengan 12 kartu teratribusi lawan dulu melempar
        # "atribusi kartu melebihi jumlah kartu lawan" — padahal data sah.
        if not ds.ENGINE.exists():
            self.skipTest("engine belum di-build")
        payload = {
            "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7,
            "numSims": 100, "seed": 7, "leftEnd": 3, "rightEnd": 0,
            "myHand": ["0-0"],
            "played": ["1-2", "1-3", "1-4", "1-5", "1-6", "2-3", "2-4",
                       "2-5", "2-6", "3-4", "4-5", "5-6", "0-1", "0-2",
                       "0-3", "0-4", "0-5", "0-6", "3-6"],
            "playedBy": ["opp1", "opp1", "opp1", "opp1", "opp1",
                         "opp2", "opp2", "opp2", "opp2", "opp2", "opp2",
                         "opp3", "me", "me", "me", "me", "me", "me", "me"],
            "nextSeat": 1, "opponents": [{}, {}, {}],
        }
        status, data = http_post(self.port, "/api/analyze", payload)
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(data["hasAttribution"])
        self.assertEqual(data["totalOppCards"], 8)
        self.assertEqual(data["boneyardCount"], 0)
        self.assertEqual(data["opponents"][0]["heldKnown"], 5)
        self.assertEqual(data["opponents"][1]["heldKnown"], 6)
        self.assertEqual(data["opponents"][2]["heldKnown"], 1)
        self.assertGreater(len(data["moves"]), 0)

    def test_played_by_contradiction_rejected(self):
        # opp1 yang di-PASS atas angka 3 tidak mungkin memainkan 3-5
        payload = {
            "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7,
            "numSims": 50, "seed": 7, "leftEnd": 3, "rightEnd": 5,
            "myHand": ["1-6", "2-5"], "played": ["3-5"],
            "playedBy": ["opp1"],
            "opponents": [{"eliminated": [3], "passes": 1}, {}, {}],
        }
        status, data = http_post(self.port, "/api/analyze", payload)
        # kontradiksi di-drop diam-diam (heldKnown=0), bukan error
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertFalse(data["hasAttribution"])

    # ---- kontrak keamanan (audit) -------------------------------------
    def simple_payload(self, **over):
        p = {"cmd": "analyze", "numPlayers": 2, "cardsPerPlayer": 3,
             "numSims": 1, "seed": 1, "leftEnd": -1, "rightEnd": -1,
             "myHand": ["0-1", "0-2"], "played": [], "nextSeat": 1,
             "deadlockRule": "lowest", "tieRule": "win",
             "opponents": [{"passes": 0, "eliminated": []}]}
        p.update(over)
        return p

    def test_security_headers_present(self):
        for path in ("/", "/api/health"):
            status, headers, _body = http_get_raw(self.port, path)
            self.assertEqual(status, 200)
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
            self.assertIn("frame-ancestors 'none'",
                          headers.get("Content-Security-Policy", ""))

    def test_reject_non_json_content_type(self):
        # vektor CSRF "simple request" browser lintas-situs
        for ctype in ("text/plain", "application/x-www-form-urlencoded"):
            status, data = http_post(self.port, "/api/analyze",
                                     self.simple_payload(), ctype=ctype)
            self.assertEqual(status, 400, ctype)
            self.assertFalse(data["ok"])

    def test_reject_cross_origin(self):
        status, data = http_post(self.port, "/api/analyze", self.simple_payload(),
                                 extra_headers={"Origin": "http://evil.com"})
        self.assertEqual(status, 400)
        # positif-kontrol: origin == Host tetap diterima
        status, data = http_post(self.port, "/api/analyze", self.simple_payload(),
                                 extra_headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])

    def test_numSims_out_of_range_rejected(self):
        for v in (10001, 10**12, 0):
            status, data = http_post(self.port, "/api/analyze",
                                     self.simple_payload(numSims=v))
            self.assertEqual(status, 400, f"numSims={v}")

    def test_malformed_bodies_clean_400(self):
        # body non-dict & JSON bersarang dalam -> 400 rapi, bukan koneksi putus
        status, data = http_post(self.port, "/api/analyze", None, raw=b"[1,2,3]")
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])
        deep = b'{"cmd":"analyze","x":' + b"[" * 5000 + b"]" * 5000 + b"}"
        status, data = http_post(self.port, "/api/analyze", None, raw=deep)
        self.assertEqual(status, 400)
        self.assertFalse(data["ok"])

    def test_error_over_http_never_echoes_input(self):
        status, data = http_post(self.port, "/api/analyze",
                                 self.simple_payload(
                                     myHand=["<img src=x onerror=alert(1)>"]))
        self.assertEqual(status, 400)
        self.assertNotIn("<img", data["error"])
        self.assertIn("elemen ke-1", data["error"])

    def test_error_never_returns_http_200(self):
        # Regresi: engine_command() dulu selalu dikirim dengan status 200
        # walau isinya {"ok": false}. Konsumen luar (curl, skrip, monitor)
        # hanya bisa rely pada status code -> 200 berarti "sukses" palsu.
        cases = [
            # (payload, status yang diharapkan)
            (self.simple_payload(numPlayers=99), 400),        # validasi server
            (self.simple_payload(deadlockRule="ngawur"), 400), # validasi server
            (self.simple_payload(myHand=["<img src=x>"]), 400),
            ({"cmd": "analyze"}, 400),                          # field inti hilang
            # tieRule nakal: LOLOS validasi server, ditolak engine — inilah
            # kasus yang dulu keluar sebagai HTTP 200 + ok:false.
            (self.simple_payload(tieRule="ngawur"), 400),
        ]
        for payload, want in cases:
            status, data = http_post(self.port, "/api/analyze", payload)
            self.assertEqual(status, want, f"payload={payload}")
            self.assertFalse(data["ok"], f"payload={payload}")
            self.assertNotEqual(status, 200, f"payload={payload}")

    def test_ok_false_body_always_paired_with_non_200(self):
        # Syarat yang lebih umum: kapan pun body ok:false, status != 200.
        payloads = [
            self.simple_payload(numPlayers=99),
            self.simple_payload(deadlockRule="ngawur"),
            {"cmd": "analyze"},
            {"cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7,
             "numSims": 50, "seed": 3, "leftEnd": -1, "rightEnd": -1,
             "myHand": [], "played": [], "opponents": [{}] * 3},
        ]
        for p in payloads:
            status, data = http_post(self.port, "/api/analyze", p)
            if data.get("ok") is False:
                self.assertGreaterEqual(status, 400, f"payload={p}")
                self.assertLess(status, 600, f"payload={p}")

    def test_unknown_endpoint_and_method_still_4xx(self):
        status, data = http_post(self.port, "/api/tidak-ada", {})
        self.assertEqual(status, 404)
        self.assertFalse(data["ok"])

    def test_meta_only_real_tiles(self):
        # INFO-8: dulu menghasilkan tile mustahil "0-7".."6-7" (35 entri)
        status, data = http_post(self.port, "/api/meta",
                                 {"myHand": [], "played": []})
        self.assertEqual(status, 200)
        self.assertEqual(len(data["remaining"]), 28)
        for k in data["remaining"]:
            self.assertRegex(k, r"^[0-6]-[0-6]$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
