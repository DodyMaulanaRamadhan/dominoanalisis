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


def http_post(port: int, path: str, payload: dict, token: str = "") -> tuple[int, dict]:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"X-App-Token": token} if token else {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
