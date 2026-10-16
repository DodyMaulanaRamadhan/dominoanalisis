#!/usr/bin/env python3
"""Uji antarmuka TANPA KEPALA untuk tier 1.700.000 simulasi.

Menjalankan aplikasi yang sungguhan — server Python, aset `web/`, dan mesin C++
— di peramban tanpa jendela (Playwright). Yang dijaga di sini adalah perilaku
yang tidak bisa dibuktikan uji unit mana pun:

1. **Peringatan sebelum tier berat dipakai.** Saat pengguna memilih 1.700.000,
   dialog konfirmasi muncul dan isinya menyebut jumlah simulasi, perkiraan
   waktu, dan cara membatalkan; banner kuning + label sekali-jalan ikut menyala.
2. **Menolak peringatan benar-benar mengembalikan pilihan** ke tier sebelumnya
   (tanpa dialog "tembus" ke server, tanpa mode Live yang mati).
3. **Label tombol selalu cocok dengan tier** (dan pulih setelah Batal) — inilah
   cacat yang dulu muncul: label tertinggal "1,7 jt (sekali)" padahal tiernya
   sudah ringan, dan sebaliknya.
4. **Tombol Batal mematikan proses mesin.** Bukan sekadar membatalkan tampilan:
   server mendeteksi koneksi yang ditutup, menulis log pembatalan, dan proses
   `domino_engine` benar-benar hilang dari daftar proses komputer.

Peramban: memakai peramban sistem (Edge/Chrome) bila ada sehingga tidak perlu
mengunduh Chromium. Bila tidak ada peramban sama sekali, uji ini **dilewati**
(skip), bukan gagal.

Agar tidak menjadi uji yang selalu hijau, tiap klaim di atas pernah diperiksa
dengan **mutasi**: satu aturan dicabut dari `web/app.js`/`server/domino_server.py`
dan uji harus gagal dengan gejala yang tepat (label tertinggal, tier tidak
kembali, Live tetap hidup, atau mesin yang tidak dimatikan).

Yang TIDAK dicakup: tata letak papan, modal, masukan cepat, dan alur Undo masih
diverifikasi manual.

Jalankan:
    pip install playwright          # sekali saja
    python tools/test_ui_heavy.py   # tambahkan -v untuk rincian
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import threading
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import domino_server as ds  # noqa: E402

HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None

STORAGE_KEY = "domino-analyzer-v3"
HEAVY = "1700000"
LIGHT = "10000"
MIDS = "50000"

# Label tombol yang diharapkan (satu sumber untuk seluruh uji).
LABEL_LIVE = "▶️ Analisis Live"
LABEL_PAUSED = "⏸ Jeda Live"
LABEL_HEAVY = "▶️ Analisis 1,7 jt (sekali)"
LABEL_CANCEL = "✕ Batal"

# Dibaca dari DOM — sengaja hanya sinyal yang benar-benar dilihat pengguna.
PAGE_STATE = """() => ({
  tier: document.getElementById('simCount').value,
  label: document.getElementById('analyzeBtn').textContent.trim(),
  banner: document.getElementById('simWarn').classList.contains('active'),
  bannerText: document.getElementById('simWarn').textContent,
  live: document.getElementById('liveChip').classList.contains('active'),
  headerLive: document.getElementById('headerLive').textContent.trim(),
  progressActive: document.getElementById('progressContainer').classList.contains('active'),
  progressText: document.getElementById('progressText').textContent,
})"""


def heavy_session() -> dict:
    """Sesi tersimpan (localStorage) dengan 5 langkah kandidat.

    Papan bermata 3 dan 5, tangan 7 kartu -> 5 langkah: cukup lama (≈10-20 detik
    pada 1,7 juta simulasi) untuk menekan Batal sebelum analisis selesai, jadi
    pembatalan benar-benar teruji dan bukan balapan.
    """
    return {
        "version": 3,
        "setup": {
            "playerCount": "4", "cardsPerPlayer": "7", "simCount": HEAVY,
            "nextSeat": "1", "deadlockRule": "lowest", "tieRule": "win",
            "cangkulMode": "ya", "adversarial": False,
        },
        "state": {
            "myHand": ["3-3", "2-5", "5-5", "1-3", "0-5", "4-6", "6-6"],
            "boardTiles": [
                {"tile": [3, 5], "origKey": "3-5", "owner": "me",
                 "source": "play", "first": True},
            ],
            "allPlayed": ["3-5"],
            "playedBy": ["me"],
            "opponents": [{"passes": [], "eliminated": []} for _ in range(3)],
        },
    }


def engine_processes() -> int:
    """Jumlah proses `domino_engine` yang hidup di komputer ini."""
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq domino_engine.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True).stdout
        return sum(1 for line in out.splitlines() if "domino_engine" in line.lower())
    try:
        out = subprocess.run(["pgrep", "-x", "domino_engine"],
                             capture_output=True, text=True).stdout
        return len(out.split())
    except FileNotFoundError:  # pgrep tak ada: baca daftar proses apa adanya
        out = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True).stdout
        return sum(1 for line in out.splitlines() if line.strip() == "domino_engine")


@contextlib.contextmanager
def capture_server_log():
    """Tampung `print()` server supaya baris pembatalan bisa diperiksa.

    domino_server memanggil print() lewat lookup global modulnya, jadi menimpa
    atribut `print` pada modul itu menangkap pesannya tanpa menyentuh stderr uji.
    """
    lines: list[str] = []
    had_print = hasattr(ds, "print")
    original = getattr(ds, "print", None)

    def recorder(*args, **kwargs):
        lines.append(" ".join(str(a) for a in args))

    ds.print = recorder
    try:
        yield lines
    finally:
        if had_print:
            ds.print = original
        else:
            del ds.print
        for line in lines:  # tetap tampilkan supaya kegagalan mudah dilacak
            print(f"[log server] {line}", file=sys.stderr)


class Dialogs(list):
    """Pesan dialog yang muncul, sekaligus keputusan yang akan diambil.

    Satu penangan per halaman: Playwright menyerahkan setiap dialog ke penangan
    pertama, jadi menambah penangan kedua justru menggagalkan penanganan
    ("already handled"). Ubah `action` kapan saja selama uji.
    """

    def __init__(self, page, action: str = "accept"):
        super().__init__()
        self.action = action  # "accept" | "dismiss"
        page.on("dialog", self._handle)

    def _handle(self, dialog):
        self.append(dialog.message)
        if self.action == "accept":
            dialog.accept()
        else:
            dialog.dismiss()


def wait_until(predicate, timeout: float, message: str, interval: float = 0.05):
    """Tunggu predikat Python; gagal dengan pesan yang jelas bila kehabisan waktu."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    raise AssertionError(message)


@unittest.skipUnless(HAS_PLAYWRIGHT, "perlu playwright — jalankan: pip install playwright")
@unittest.skipUnless(ds.ENGINE.exists(), "engine belum di-build (python tools/build_engine.py)")
class TestHeavyTierUI(unittest.TestCase):
    """Alur tier 1,7 juta dari sudut pandang pengguna."""

    @classmethod
    def setUpClass(cls):
        ds.APP_TOKEN = ""  # tanpa token: halaman web asli bisa memanggil /api
        cls.httpd = ds.ThreadingHTTPServer((ds.HOST, 0), ds.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        from playwright.sync_api import sync_playwright
        cls._pw = sync_playwright().start()
        cls.browser = cls._launch()

    @classmethod
    def _launch(cls):
        """Peramban tanpa kepala — utamakan peramban sistem (tanpa unduhan)."""
        errors = []
        for kwargs in ({"channel": "msedge"}, {"channel": "chrome"}, {}):
            try:
                return cls._pw.chromium.launch(headless=True, **kwargs)
            except Exception as exc:  # peramban belum terpasang
                errors.append(f"{kwargs.get('channel', 'chromium bawaan')}: "
                              f"{str(exc).splitlines()[0][:120]}")
        cls._pw.stop()
        raise unittest.SkipTest(
            "tidak ada peramban untuk uji UI — pakai Edge/Chrome yang terpasang, "
            "atau `playwright install chromium`. Detail: " + " | ".join(errors))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._pw.stop()
        cls.httpd.shutdown()

    # ---- perkakas -------------------------------------------------------
    def new_page(self, session: dict | None = None, dialog_action: str = "accept"):
        """Halaman baru (konteks bersih) + daftar pesan dialog yang muncul."""
        ctx = self.browser.new_context(service_workers="block", locale="id-ID")
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        page.set_default_timeout(20000)
        dialogs = Dialogs(page, dialog_action)
        page.goto(self.url, wait_until="load")
        if session is not None:
            # Sesi tersimpan adalah jalur pengguna yang sah (autosave/import):
            # ditulis ke localStorage lalu halaman dimuat ulang.
            page.evaluate("([k, v]) => localStorage.setItem(k, v)",
                          [STORAGE_KEY, json.dumps(session)])
            page.reload(wait_until="load")
        return page, dialogs

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def ui(self, page) -> dict:
        return page.evaluate(PAGE_STATE)

    def select_tier(self, page, tier: str, dialogs: Dialogs, expect_dialog: bool | None):
        """Ganti tier lewat <select> (jalur pengguna) dan tunggu dialognya."""
        before = len(dialogs)
        page.select_option("#simCount", tier)
        if expect_dialog is True:
            wait_until(lambda: len(dialogs) > before, 5,
                       f"dialog peringatan tidak muncul saat memilih tier {tier}")
        if expect_dialog is False:
            self.assertEqual(len(dialogs), before,
                             "dialog tak terduga muncul untuk tier ringan")
        return page.evaluate(PAGE_STATE)

    def assert_heavy_ui(self, ui: dict):
        self.assertEqual(ui["tier"], HEAVY)
        self.assertTrue(ui["banner"], "banner peringatan tier berat harus menyala")
        self.assertIn("1.700.000", ui["bannerText"])
        self.assertIn("Live", ui["bannerText"], "banner harus menjelaskan mode Live")
        self.assertEqual(ui["label"], LABEL_HEAVY,
                         "label harus menandai analisis sekali-jalan")
        self.assertFalse(ui["live"], "mode Live tidak boleh hidup di tier berat")
        self.assertEqual(ui["headerLive"], "⏸ LIVE")

    def assert_light_ui(self, ui: dict):
        self.assertNotEqual(ui["tier"], HEAVY)
        self.assertFalse(ui["banner"], "banner tier berat harus padam di tier ringan")
        self.assertEqual(ui["bannerText"].strip(), "")
        self.assertIn(ui["label"], (LABEL_LIVE, LABEL_PAUSED),
                      f"label salah untuk tier ringan: {ui['label']!r}")

    # ---- 1. peringatan muncul sebelum tier berat dipakai ----------------
    def test_heavy_option_exists_and_warns_before_use(self):
        page, dialogs = self.new_page()
        option = page.locator("#simCount option[value='1700000']")
        self.assertEqual(option.count(), 1, "opsi 1.700.000 harus ada di daftar tier")
        self.assertIn("LAMBAT", option.inner_text())

        ui = self.select_tier(page, HEAVY, dialogs, expect_dialog=True)
        self.assertEqual(len(dialogs), 1, "tepat satu dialog peringatan")
        msg = dialogs[0]
        self.assertIn("1.700.000", msg, "dialog harus menyebut jumlah simulasinya")
        self.assertIn("perkiraan", msg, "dialog harus memberi perkiraan waktu")
        self.assertIn("Batal", msg, "dialog harus menjelaskan cara membatalkan")
        self.assertIn("Lanjutkan memakai tier ini?", msg)
        self.assert_heavy_ui(ui)

    # ---- 2. menolak peringatan mengembalikan pilihan --------------------
    def test_declining_warning_reverts_to_previous_tier(self):
        page, dialogs = self.new_page(dialog_action="dismiss")
        self.select_tier(page, MIDS, dialogs, expect_dialog=False)
        self.assertEqual(self.ui(page)["tier"], MIDS)

        ui = self.select_tier(page, HEAVY, dialogs, expect_dialog=True)
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(ui["tier"], MIDS,
                         "menolak peringatan harus mengembalikan tier sebelumnya")
        self.assert_light_ui(ui)
        self.assertTrue(ui["live"], "mode Live tidak boleh ikut berubah saat menolak")
        self.assertEqual(ui["headerLive"], "🔴 LIVE")

        # Tier berat tetap bisa dipakai setelah pengguna menyetujui dialognya.
        dialogs.action = "accept"
        ui = self.select_tier(page, HEAVY, dialogs, expect_dialog=True)
        self.assert_heavy_ui(ui)

    # ---- 3. label tombol selalu cocok dengan tier -----------------------
    def test_button_label_always_matches_tier(self):
        page, dialogs = self.new_page()
        steps = [MIDS, HEAVY, MIDS, HEAVY]
        for tier in steps:
            heavy = tier == HEAVY
            ui = self.select_tier(page, tier, dialogs, expect_dialog=heavy)
            if heavy:
                self.assert_heavy_ui(ui)
            else:
                self.assert_light_ui(ui)
        self.assertEqual(len(dialogs), 2,
                         "setiap kenaikan ke tier berat harus diperingatkan lagi")

    # ---- 4. jeda manual pengguna dihormati ------------------------------
    def test_manual_pause_survives_tier_change(self):
        page, dialogs = self.new_page()
        self.assertTrue(self.ui(page)["live"], "aplikasi normalnya hidup dengan Live")
        page.click("#analyzeBtn")  # Live -> jeda
        ui = self.ui(page)
        self.assertFalse(ui["live"])
        self.assertEqual(ui["label"], LABEL_LIVE)

        ui = self.select_tier(page, HEAVY, dialogs, expect_dialog=True)
        self.assert_heavy_ui(ui)

        # Kembali ke tier ringan: Live TIDAK boleh menyala sendiri, karena
        # sebelumnya dijeda oleh pengguna, bukan dimatikan oleh aturan tier.
        ui = self.select_tier(page, LIGHT, dialogs, expect_dialog=False)
        self.assert_light_ui(ui)
        self.assertEqual(ui["label"], LABEL_LIVE)
        self.assertFalse(ui["live"], "jeda manual pengguna harus tetap dihormati")

    # ---- 5. tier berat tetap diperingatkan setelah reload ---------------
    def test_heavy_tier_still_warned_after_reload(self):
        page, dialogs = self.new_page()
        self.assert_heavy_ui(self.select_tier(page, HEAVY, dialogs, expect_dialog=True))
        before = len(dialogs)
        page.reload(wait_until="load")
        ui = self.ui(page)
        self.assert_heavy_ui(ui)  # banner + label sekali-jalan muncul lagi
        self.assertEqual(len(dialogs), before,
                         "peringatan reload lewat banner, bukan dialog yang memblokir")

    # ---- 6. Batal benar-benar mematikan proses mesin --------------------
    def test_cancel_button_stops_engine_process(self):
        page, dialogs = self.new_page(session=heavy_session())
        ui = self.ui(page)
        self.assert_heavy_ui(ui)  # sesi tersimpan: banner, tanpa dialog
        self.assertEqual(dialogs, [], "sesi tersimpan hanya memakai banner, bukan dialog")

        baseline = engine_processes()
        with capture_server_log() as log:
            page.click("#analyzeBtn")  # tier berat: tombol = analisis sekali-jalan
            wait_until(lambda: engine_processes() > baseline, 20,
                       "proses mesin tidak pernah mulai dijalankan")
            wait_until(lambda: self.ui(page)["label"] == LABEL_CANCEL, 10,
                       f"label saat berjalan bukan {LABEL_CANCEL!r}")
            self.assertTrue(self.ui(page)["progressActive"],
                            "bilah kemajuan harus aktif selama analisis berat")
            # Analisis wajib MASIH berjalan tepat sebelum Batal ditekan, kalau
            # tidak uji ini tidak membuktikan apa pun: label hanya kembali ke
            # mode sekali-jalan di blok finally setelah analisis benar-benar
            # berakhir (dan proses mesinnya sudah tiada).
            self.assertEqual(self.ui(page)["label"], LABEL_CANCEL,
                             "analisis sudah selesai sebelum Batal ditekan")

            started = time.monotonic()
            page.click("#analyzeBtn")  # Batal: membatalkan + mematikan mesin
            wait_until(lambda: engine_processes() <= baseline, 8,
                       "proses mesin masih hidup > 8 detik setelah Batal — "
                       "server tidak mematikannya")
            elapsed = time.monotonic() - started
            print(f"[ui] Batal ditekan -> proses mesin mati dalam {elapsed:.2f}s",
                  file=sys.stderr)
            self.assertLess(elapsed, 5.0,
                            f"pembatalan terlalu lambat: mesin hidup {elapsed:.1f}s setelah Batal")

            wait_until(lambda: "dibatalkan" in self.ui(page)["progressText"], 10,
                       "antarmuka tidak menandai analisis sebagai dibatalkan")
            wait_until(lambda: self.ui(page)["label"] == LABEL_HEAVY, 10,
                       "label tidak pulih ke mode sekali-jalan setelah Batal")

        self.assertTrue(any("dibatalkan" in line for line in log),
                        f"server tidak mencatat pembatalan; log: {log}")

        # Mesin yang dibatalkan tidak boleh menghasilkan hasil di layar.
        ui = self.ui(page)
        self.assertNotIn("Selesai", ui["progressText"])
        self.assert_heavy_ui(ui)


if __name__ == "__main__":
    unittest.main(verbosity=2)
