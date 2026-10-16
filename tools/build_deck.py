#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Domino Analyzer Pro presentation deck (PPTX).

Output : docs/Domino-Analyzer-Pro-Presentasi.pptx

Dependensi : pip install python-pptx
Contoh     : python tools/build_deck.py
             python tools/build_deck.py --out docs/lain.pptx

Isi slide disusun sebagai data (SLIDES) supaya mudah disunting: setiap entri
adalah satu slide dengan judul, daftar poin, kotak panel opsional, dan catatan
pembicara. Nomor versi dan nama penulis diambil dari konstanta di bawah.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DEFAULT = ROOT / "docs" / "Domino-Analyzer-Pro-Presentasi.pptx"
BOOK_PDF = ROOT / "docs" / "Domino-Analyzer-Pro-Dokumentasi.pdf"


def pdf_page_count(path: pathlib.Path) -> int | None:
    """Jumlah halaman buku PDF, dibaca saat build supaya slide tidak menyebut
    angka basi (dulu jumlah halaman ditulis tetap di dalam teks slide)."""
    if not path.exists():
        return None
    try:
        import pymupdf
        doc = pymupdf.open(str(path))
        pages = doc.page_count
        doc.close()
        return pages
    except Exception:
        pass
    try:
        counts = [int(m.group(1)) for m in re.finditer(rb"/Count\s+(\d+)", path.read_bytes())]
        return max(counts) if counts else None
    except Exception:
        return None


BOOK_PAGES = pdf_page_count(BOOK_PDF)
BOOK_BULLET = (f"Buku: docs/{BOOK_PDF.name} ({BOOK_PAGES} halaman, 9 diagram vektor)"
               if BOOK_PAGES else
               f"Buku: docs/{BOOK_PDF.name} (9 diagram vektor)")

TITLE = "Domino Analyzer Pro"
SUBTITLE = "Analisis langkah domino dengan simulasi Monte-Carlo"
AUTHOR = "Dody Maulana Ramadhan"
APP_VERSION = "v3.3 · engine 3.0.0"
BUILD_DATE = datetime.date.today().isoformat()

BG = (0x0A, 0x0E, 0x14)
FG = (0xE6, 0xED, 0xF3)
MUTED = (0x8B, 0x94, 0x9E)
ACCENT = (0x58, 0xA6, 0xFF)
GREEN = (0x3F, 0xB9, 0x50)
RED = (0xF8, 0x51, 0x49)
ORANGE = (0xD2, 0x9A, 0x22)
PURPLE = (0xBC, 0x8C, 0xFF)
PANEL = (0x16, 0x1B, 0x22)
LINE = (0x30, 0x36, 0x3D)


# ---------------------------------------------------------------------------
# Data presentasi
# ---------------------------------------------------------------------------
SLIDES: list[dict] = [
    dict(kind="title", title=TITLE, subtitle=SUBTITLE,
         note="Slide pembuka. Sebutkan bahwa ini alat bantu keputusan, bukan pengganti "
              "keputusan pemain."),

    dict(title="Masalah yang dipecahkan",
         kicker="Latar belakang",
         bullets=[
             "Informasi tersembunyi terlalu banyak: 28 kartu, kita hanya tahu 7 di antaranya",
             "Setiap PASS lawan membocorkan fakta penting — dan hampir selalu terbuang",
             "Beda tipis antar langkah tidak bisa dibedakan dari keberuntungan",
             "Menghitung peluang secara manual saat bermain tidak mungkin",
         ],
         note="Tiga masalah ini menjadi dasar seluruh desain aplikasi: catat bukti, "
              "hitung peluang, tampilkan ketidakpastian."),

    dict(title="Apa itu Domino Analyzer Pro",
         kicker="Ringkas",
         bullets=[
             "Aplikasi analisis untuk domino 28 kartu (angka 0-6), 2 sampai 4 pemain",
             "Anda masukkan kartu tangan, kartu di meja, PASS lawan, dan atribusi kartu",
             "Mesin memainkan ribuan gim domino di dalam komputer untuk tiap langkah",
             "Hasilnya: urutan langkah terbaik, peluang menang, dan alasannya",
             "Semuanya berjalan lokal di komputer Anda — tanpa akun, tanpa data keluar",
         ],
         note="Tegaskan: aplikasi tidak tahu kartu lawan; ia menghitung peluang dari "
              "informasi yang Anda berikan."),

    dict(title="Fitur utama",
         kicker="Kemampuan",
         panels=[
             ("Mesin analisis", ["Monte-Carlo per kandidat langkah",
                                 "3 profil lawan AI yang dirotasi",
                                 "Mode teliti (lawan tanpa derau)",
                                 "Simulasi cangkul + kartu sisa mati",
                                 "Interval keyakinan Wilson 95%",
                                 "Deterministik: seed tetap"]),
             ("Pelacakan lawan", ["PASS lawan -> eliminasi angka",
                                  "Atribusi kartu ke lawan tertentu",
                                  "Kisi kemungkinan kartu per lawan",
                                  "Profil kekayaan angka per lawan",
                                  "Urutan giliran diperhitungkan"]),
             ("Antarmuka", ["Papan bergaya ular, mengecil otomatis",
                            "Siluet rekomendasi di papan",
                            "Mode LIVE: analisis ulang otomatis",
                            "Undo timeline + simpan otomatis",
                            "Export/Import sesi (JSON)",
                            "PWA: bisa dipasang, ada offline shell"]),
         ],
         note="Tiga kolom: mesin, pelacakan, antarmuka. Jangan membacakan semuanya; "
              "pilih dua-tiga yang paling relevan dengan audiens."),

    dict(kind="boxes", title="Arsitektur: tiga lapisan",
         kicker="Cara kerja",
         boxes=[("UI Web (web/)", "index.html, app.js\nstyles.css, sw.js\nPWA + offline shell", ACCENT),
                ("Server Python", "server/domino_server.py\nport 2024\nnormalisasi + validasi", GREEN),
                ("Engine C++20", "engine/domino_engine.cpp\nbin/domino_engine\nMonte-Carlo + ranking", ORANGE)],
         note="Pemisahan ini membuat mesin bisa diuji langsung dari terminal tanpa "
              "server, peramban, atau jaringan."),

    dict(title="Alur satu permintaan",
         kicker="Data mengalir",
         steps=["Aksi pengguna di UI (ketuk kartu / catat PASS)",
                "app.js menyusun JSON: tangan, papan, atribusi, aturan meja, seed",
                "POST /api/analyze: server menormalkan kunci kartu + memvalidasi",
                "Engine dijalankan: payload ke stdin, ribuan gim dimainkan",
                "Balasan JSON: moves[], opponents[], deadTiles[]",
                "UI menggambar ulang: glow rekomendasi, siluet, panel hasil"],
         note="Semua perhitungan berat hanya di engine; UI murni menggambar. Satu "
              "sumber kebenaran untuk urutan kartu."),

    dict(title="Menjalankan aplikasi",
         kicker="Instalasi",
         code=["python start.py            # build engine + self-test + serve di :2024",
               "python start.py --check    # build + self-test saja",
               "python tools/build_engine.py --force    # bangun ulang mesin C++",
               "python tools/selftest.py                # 11 pemeriksaan mandiri mesin",
               "python tools/test_server.py             # 29 uji server",
               "python tools/test_ui_heavy.py           # 6 uji UI tanpa kepala (1,7 juta)"],
         bullets=["Prasyarat: Python 3.10+ dan satu compiler C++20 (MSVC / g++ / clang++)",
                  "Buka http://127.0.0.1:2024 — server berjalan lokal"],
         note="Sebutkan bahwa start.py menolak menjalankan server bila self-test mesin "
              "gagal: lebih baik menolak daripada memberi angka yang salah."),

    dict(title="Panel Setup",
         kicker="Antarmuka 1/5",
         bullets=["Jumlah pemain (2/3/4) dan kartu per pemain",
                  "Simulasi per kartu: 1000 / 5000 / 10000 (bawaan) / 50000 / 1,7 juta",
                  "Tier 1,7 juta: peringatan waktu, tanpa mode Live, bisa dibatalkan",
                  "Main Setelah Saya: siapa yang bermain tepat setelah Anda",
                  "Adu: banding mata terkecil atau rata-rata",
                  "Seri dihitung menang atau kalah",
                  "Main cangkul? (sisa bisa disambar atau mati)",
                  "Mode teliti: lawan respons cerdas, lebih lambat tapi lebih akurat"],
         note="Setel aturan meja SEBELUM mencatat kartu: mengubahnya di tengah permainan "
              "membuat hasil sebelum dan sesudah tidak bisa dibandingkan."),

    dict(title="Papan bergaya ular",
         kicker="Antarmuka 2/5",
         bullets=["Rantai disusun dalam baris bergantian arah (boustrophedon)",
                  "Kartu pertama berdiri tegak dan ditandai emas — pusat rantai",
                  "Kartu siku di tikungan digambar berdiri agar sambungan rapat",
                  "Ukuran kartu mengecil otomatis (sampai setengah) agar semua terlihat",
                  "Kartu pertama selalu diupayakan berada di tengah papan",
                  "Siluet biru menunjukkan tempat rekomendasi: di kepala atau kaki kartu pertama"],
         note="Inti keputusan desain: pemain tidak boleh kehilangan gambaran besar "
              "hanya karena rantai sudah panjang."),

    dict(title="Tangan, modal kartu, dan masukan cepat",
         kicker="Antarmuka 3/5",
         bullets=["Kartu hijau = bisa dimainkan; abu-abu = belum bisa",
                  "Cincin biru berdenyut = kartu peringkat #1 dari analisis terakhir",
                  "Modal 28 kartu: ketuk untuk memilih atau membatalkan pilihan",
                  "Masukan cepat: dua kotak angka 0-6, urutan bebas, Enter untuk menambah",
                  "Mengetik kartu yang sudah ada = menghapusnya (bolak-balik)",
                  "Batas kartu per pemain ditegakkan dengan peringatan"],
         note="Masukan cepat dibuat karena saat bermain, tangan fisik masih memegang "
              "kartu — mengetuk kisi 28 kartu terlalu lambat."),

    dict(title="Pelacakan lawan & atribusi",
         kicker="Antarmuka 4/5",
         bullets=["Tombol PASS / LEWAT: mencatat ujung meja saat lawan tidak bisa jalan",
                  "Efeknya: kedua angka ujung dihapus dari kemungkinan kartu lawan itu",
                  "Kartu sisa diklik -> pilih lawan pemainnya (atribusi)",
                  "Kartu yang diatribusikan otomatis dieliminasi dari lawan lain",
                  "Kisi kemungkinan kartu per lawan; yang berkilau merah bisa dimainkan sekarang",
                  "Filter PASS menunjukkan berapa persen kemungkinan sudah dipersempit"],
         note="Tekankan: PASS adalah bukti keras. Satu PASS palsu membuat analisis "
              "berikutnya yakin pada hal yang salah. Catat hanya yang benar-benar terlihat."),

    dict(title="Peta angka & kartu sisa",
         kicker="Antarmuka 5/5",
         bullets=["Peta angka: untuk tiap angka 0-6, berapa di tangan saya / sudah keluar / belum diketahui",
                  "Angka yang Anda kuasai 3 kali atau lebih ditandai dominan",
                  "Angka yang habis dari peredaran ditandai exhausted — meja akan macet di situ",
                  "Kartu sisa berubah perilaku sesuai pengaturan cangkul",
                  "Cangkul mati: ditampilkan kartu yang paling mungkin tidak pernah masuk permainan"],
         note="Peta angka adalah alat penalaran tercepat yang bisa dipakai tanpa membaca "
              "satu pun statistik."),

    dict(title="Mode LIVE, undo, dan sesi",
         kicker="Alur kerja",
         bullets=["LIVE aktif sejak aplikasi dibuka: analisis ulang setiap data berubah",
                  "Tombol yang sama untuk menjeda; perhitungan berjalan bisa dibatalkan",
                  "Permintaan baru saat analisis berjalan akan diantrekan, bukan ditumpuk",
                  "Undo memulihkan kartu, PASS lawan, dan atribusi sekaligus (100 langkah)",
                  "Simpan otomatis ke penyimpanan peramban",
                  "Export/Import sesi sebagai JSON, divalidasi ketat saat dibaca"],
         note="Undo dirancang konsisten supaya data pelacakan tidak pernah setengah "
              "jalan — sumber kesalahan yang halus."),

    dict(title="Dasar domino yang dipakai aplikasi",
         kicker="Istilah",
         bullets=["28 kartu: 21 kartu beda angka + 7 balak (angka kembar)",
                  "Nilai mata = jumlah kedua angka; balak 6-6 bernilai 12 (terbesar)",
                  "Setiap angka 0-6 muncul tepat 7 kali di seluruh set",
                  "Ujung meja: angka bebas di kiri dan kanan rantai",
                  "PASS: tidak ada kartu yang bisa disambungkan",
                  "Adu: permainan macet, pemenang ditentukan nilai mata"],
         note="Kunci: setiap angka ada 7 kartu — dasar peta angka dan semua perhitungan "
              "eliminasi."),

    dict(title="Cangkul dan sisa mati",
         kicker="Aturan meja",
         bullets=["Cangkul: pemain yang PASS menyambar kartu sisa sampai bisa main",
                  "Jumlah sisa = 28 - (pemain x kartu per pemain): 4 pemain x 7 = 0 sisa",
                  "Bila cangkul aktif, setiap sambaran yang terlihat sebaiknya diatribusikan",
                  "Bila cangkul mati, sisa tidak pernah masuk permainan",
                  "Mesin menghitung peluang tiap kartu berakhir di sisa (simulasi pembagian)",
                  "Angka yang banyak mati di sisa menjadi langka -> meja lebih mudah macet"],
         note="Kartu sisa mati adalah informasi strategis yang jarang disadari pemain "
              "manual."),

    dict(title="Adu dan konvensi meja",
         kicker="Aturan meja",
         bullets=["Adu terjadi bila semua pemain PASS dalam satu putaran penuh",
                  "Mata terkecil: nilai mata Anda dibandingkan nilai mata terkecil lawan",
                  "Rata-rata: dibandingkan rata-rata nilai mata semua lawan",
                  "Seri: bisa dihitung menang atau kalah",
                  "Pilihan ini mengubah seluruh angka peluang dan bar 'menang lewat adu'",
                  "Kartu besar dan balak adalah beban bila permainan mengarah ke adu"],
         note="Kesalahan paling umum: aplikasi disetel rata-rata padahal meja memakai "
              "mata terkecil. Seluruh angka lalu menyimpang."),

    dict(kind="flow", title="Mesin: Monte-Carlo per kandidat langkah",
         kicker="Isi mesin",
         steps=["Satu kandidat langkah", "N pembagian kartu (batasan dihormati)",
                "N gim penuh dimainkan", "Agregasi hasil", "rankScore + interval"],
         bullets=["Setiap ulangan memakai pembagian kartu dan gaya lawan yang berbeda",
                  "Konservasi kartu diverifikasi setiap gim (28 kartu tidak boleh berubah)",
                  "Batas 300 giliran menjamin simulasi selalu berhenti"],
         note="Determinisme: seed sama -> hasil identik. Ini yang membuat angka bisa "
              "diverifikasi ulang."),

    dict(title="Tiga profil lawan + mode teliti",
         kicker="Isi mesin",
         bullets=["Blocker: menyisakan ujung sepi, membuat lawan PASS",
                  "Hoarder: menyimpan kartu dari angka kuatnya",
                  "Dumper: cepat membuang kartu besar dan balak",
                  "Profil dirotasi antar simulasi -> rekomendasi tidak terjebak satu gaya",
                  "Mode teliti: lawan yang bermain tepat setelah Anda bermain ketat tanpa derau",
                  "Efeknya: estimasi lebih konservatif, seperti melawan lawan tanpa kesalahan bodoh"],
         note="Rotasi profil adalah jawaban atas risiko overfitting: rekomendasi harus "
              "kuat melawan berbagai gaya, bukan hanya satu."),

    dict(title="Pembagian kartu yang sadar batasan",
         kicker="Isi mesin",
         bullets=["Prioritas 0: kartu yang PASTI milik lawan (atribusi Anda) dipaksa masuk ke tangannya",
                  "Prioritas 1: kartu berangka yang di-PASS lawan dibuang dari undian untuknya",
                  "Prioritas 2: bila kuota mustahil dipenuhi, batasan dilepas dan dicatat sebagai fallback",
                  "Lawan dengan batasan paling ketat dilayani lebih dulu",
                  "Bila atribusi bertentangan dengan bukti PASS, bukti PASS yang menang",
                  "Fallback dilaporkan, bukan disembunyikan: sekitar 57 dari 400 skenario acak"],
         note="Inilah bagian yang membuat catatan PASS dan atribusi benar-benar "
              "mengubah hasil, bukan sekadar hiasan."),

    dict(title="rankScore: satu sumber kebenaran",
         kicker="Isi mesin",
         bars=[("winRate x 100", 100, ACCENT), ("domSupport x 0,6", 60, GREEN),
               ("trapScore x 0,8", 80, PURPLE), ("blockScore x 0,7", 70, ORANGE),
               ("deadlock x 20", 20, (0x2A, 0x9D, 0x8F)),
               ("guaranteedBlocks x 8", 8, RED), ("avgOppPasses x 3", 3, MUTED),
               ("safetyRatio x 30", 30, (0xB4, 0x7E, 0x1D)),
               ("selfTrap x -0,5", 50, RED), ("riskScore x -0,5", 50, (0x9B, 0x2C, 0x2C))],
         bullets=["Peluang menang berbobot paling besar: komponen taktis hanya memisahkan langkah yang berdekatan",
                  "Formula ini empat baris kode di mesin, bukan skor rahasia"],
         note="Jelaskan contoh nyata di slide berikutnya: peluang lebih tinggi bisa "
              "kalah peringkat karena menyisakan ujung berbahaya."),

    dict(title="Contoh nyata: peluang vs bentuk permainan",
         kicker="Bukti",
         table=[["Kartu", "Ujung baru", "Peluang", "Selang 95%", "rankScore", "Jerat", "Jebakan diri"],
                ["3-6 (kiri)", "6 | 1", "69,2%", "65,0-73,1%", "84,2", "15", "0"],
                ["2-3 (kiri)", "2 | 1", "71,2%", "67,1-75,0%", "60,4", "0", "6"],
                ["1-5 (kanan)", "3 | 5", "60,0%", "55,6-64,2%", "51,3", "0", "6"]],
         bullets=["2-3 punya peluang menang lebih tinggi, tetapi #1 adalah 3-6",
                  "Alasannya: 3-6 memasang jerat angka dominan 6 dan tidak menyisakan ujung berbahaya",
                  "Selang kedua kartu saling menumpuk -> beda 2 poin persen itu bukan sinyal"],
         note="Angka ini keluaran mesin sungguhan (seed 20240922, 500 simulasi), bukan "
              "ilustrasi. Inilah inti argumen mengapa rankScore ada."),

    dict(title="Interval keyakinan Wilson 95%",
         kicker="Kejujuran statistik",
         bullets=["Setiap peluang menang disertai selang: rentang nilai yang masuk akal",
                  "Lebar selang menyempit mengikuti akar jumlah simulasi",
                  "200 simulasi: lebar sekitar 13,7 poin; 2000: 4,4 poin; 5000: 2,8 poin",
                  "Dua langkah hanya berbeda nyata bila selangnya tidak bertumpuk",
                  "Rumus ini pernah salah dan selalu menghasilkan 0-100%",
                  "Sudah diperbaiki, dan kini dijaga oleh pemeriksaan mandiri khusus"],
         note="Ceritakan: cacat ditemukan saat menyusun dokumentasi karena contoh "
              "keluaran diperiksa satu per satu. Uji lama terlalu longgar untuk "
              "menangkapnya."),

    dict(title="Membaca panel hasil",
         kicker="Panduan",
         bullets=["Peringkat kartu, ujung baru yang dihasilkan, dan lencana status",
                  "Kotak statistik: Win, Jerat, Kunci, Lawan Pass, Sisa Mata, Risk",
                  "Bar: peluang menang (+selang), menang lewat adu, kekuatan jerat",
                  "Mode kartu pertama: bar keamanan putaran 2 dan daftar kartu yang bisa dimainkan",
                  "Kotak strategi: alasan jerat, kunci, jebakan diri — dalam bahasa manusia",
                  "Blok terjamin: lawan yang PASTI mati menurut data PASS"],
         note="Ajarkan satu kebiasaan: baca peringkat #1, selangnya, dan alasannya — "
              "lalu baru putuskan."),

    dict(title="Kartu berbahaya & profil lawan",
         kicker="Panduan",
         bullets=["Kartu berbahaya: lima kartu yang paling sering muncul di tangan lawan pada gim yang Anda kalahi",
                  "Tafsirkan sebagai 'alat kekalahan', bukan 'kartu yang pasti dipegang lawan'",
                  "Profil lawan: perkiraan angka yang ia kuasai, jumlah kartu, persentase keyakinan",
                  "Perkiraan jumlah balak di tangan lawan",
                  "Kolam kemungkinan menyempit seiring bertambahnya PASS yang Anda catat",
                  "Balasan untuk pertanyaan 'apa yang paling mungkin dipegang lawan?'"],
         note="Semakin disiplin mencatat, semakin tajam profil ini. Data lebih berharga "
              "daripada menambah simulasi."),

    dict(title="Pengujian dan jaminan kualitas",
         kicker="Kualitas",
         bullets=["11 pemeriksaan mandiri mesin (deck, parser, determinisme, konservasi, cangkul, ranking, aturan adu, atribusi, interval)",
                  "29 uji server: normalisasi, validasi, endpoint, dan kontrak keamanan",
                  "6 uji antarmuka tanpa kepala: peringatan tier 1,7 juta, label tombol, Batal mematikan mesin",
                  "Kontrak yang dijaga: ok:false selalu berpasangan dengan status bukan 200",
                  "CI menjalankan empat pekerjaan: Linux g++, Windows MSVC, server tanpa mesin, dan peramban tanpa kepala",
                  "Konservasi kartu diverifikasi pada setiap simulasi",
                  "Determinisme bisa dibuktikan sendiri: jalankan dua kali, bandingkan keluaran"],
         note="Pesan utama: aplikasi ini dirancang supaya kesalahan statistik tidak "
              "bisa lolos diam-diam."),

    dict(title="Keamanan dan ketahanan",
         kicker="Kualitas",
         bullets=["Header keamanan: nosniff, no-referrer, CSP ketat",
                  "Penyajian berkas dibatasi di dalam folder web/ (anti path traversal)",
                  "Hanya application/json yang diterima; Origin lintas situs ditolak (CSRF)",
                  "Batas ukuran isi 1 MiB; permintaan rusak dijawab 400 yang rapi",
                  "Pesan galat tidak pernah memantulkan masukan pengguna (anti XSS)",
                  "APP_TOKEN opsional dengan perbandingan waktu-konstan; batas numSims mencegah pembebanan CPU",
                  "Data sesi impor divalidasi sebelum dipercaya"],
         note="Semua ini hasil audit: setiap celah yang ditemukan menambah satu uji "
              "yang menjaganya."),

    dict(title="Empat prinsip strategi",
         kicker="Strategi",
         bullets=["1. Kuasai satu ANGKA, bukan tujuh kartu — hitung angka, bukan nilai mata",
                  "2. Ujung meja adalah alat: setiap langkah memilih soal untuk lawan",
                  "3. Informasi adalah mata uang: satu PASS bernilai lebih dari satu kartu bagus",
                  "4. Jangan mengadu kecuali tangan Anda ringan",
                  "Jerat: menyisakan angka dominan agar lawan terpaksa membuka jalan Anda",
                  "Kunci: meninggalkan ujung yang hanya Anda miliki aksesnya"],
         note="Empat prinsip ini bisa dibawa ke meja tanpa membuka aplikasi."),

    dict(title="Rutinitas satu langkah",
         kicker="Strategi",
         steps=["Perbarui data dulu (kartu lawan, PASS)", "Baca peringkat #1 + selang + alasan",
                "Periksa keamanan putaran 2", "Cocokkan dengan pengamatan meja"],
         bullets=["Data lama menghasilkan analisis yang salah — urutan ini penting",
                  "Bila rekomendasi bertentangan dengan pengamatan, biasanya data yang kurang lengkap",
                  "Angka tidak menggantikan kepekaan; ia menutup celah yang sulit ditutup manusia: menghitung"],
         note="Tutup bagian strategi dengan rutinitas ini; ajak audiens mengingat "
              "urutan empat langkahnya."),

    dict(title="Yang belum ada / batasan jujur",
         kicker="Batasan",
         bullets=["Lawan di simulasi heuristik, bukan manusia sungguhan",
                  "Pembagian kartu mengasumsikan keacakan",
                  "Konvensi meja harus benar, kalau tidak seluruh angka menyimpang",
                  "Belum ada uji otomatis untuk tata letak antarmuka dan interaksi",
                  "Belum ada tolok ukur kinerja di CI",
                  "Proyek belum menyertakan berkas lisensi",
                  "Tidak mengintip kartu lawan: kualitas hasil sepenuhnya bergantung pada data yang Anda masukkan"],
         note="Bagian ini penting untuk kredibilitas: sebutkan batasan sebelum "
              "ditanya."),

    dict(title="Dokumentasi lengkap",
         kicker="Hasil",
         bullets=[BOOK_BULLET,
                  "Markdown: docs/Domino-Analyzer-Pro-Dokumentasi.md (sumber 10 bagian di docs/src/)",
                  "DOCX: versi yang bisa diedit",
                  "Presentasi: docs/Domino-Analyzer-Pro-Presentasi.pptx (slide ini)",
                  "Dibangun ulang dengan: python tools/build_docs.py dan python tools/build_deck.py",
                  "Setiap angka contoh di buku berasal dari eksekusi mesin yang sesungguhnya"],
         note="Sebutkan bahwa dokumentasi dan presentasi bisa dibangun ulang dari "
              "sumber Markdown — jadi tidak ada dua versi yang berbeda isi."),

    dict(kind="end", title="Terima kasih",
         subtitle=f"by {AUTHOR}",
         bullets=["Domino Analyzer Pro", f"Versi aplikasi {APP_VERSION}",
                  "Panduan pemakaian, penjelasan mesin, rujukan API, dan strategi bermain",
                  "Analisis langkah domino 28 kartu dengan simulasi Monte-Carlo"],
         note="Slide penutup. Ucapkan terima kasih dan buka sesi tanya jawab."),
]


# ---------------------------------------------------------------------------
# Pembangun slide
# ---------------------------------------------------------------------------
def _rgb(t: tuple[int, int, int]):
    from pptx.dml.color import RGBColor
    return RGBColor(*t)


def _set_bg(slide, color=BG):
    from pptx.dml.color import RGBColor
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(*color)


def _textbox(slide, left, top, width, height):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    return tf


def _para(tf, text, size=16, color=FG, bold=False, first=False, space_after=6,
          bullet_char=None, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.text = (f"{bullet_char} " if bullet_char else "") + text
    p.space_after = _pt(space_after)
    for run in p.runs:
        run.font.size = _pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = _rgb(color)
    return p


def _pt(v):
    from pptx.util import Pt
    return Pt(v)


def _inches(v):
    from pptx.util import Inches
    return Inches(v)


def _add_footer(slide, page: int, total: int):
    tf = _textbox(slide, _inches(0.55), _inches(6.95), _inches(8.0), _inches(0.4))
    _para(tf, f"{TITLE} · by {AUTHOR}", size=10, color=MUTED, first=True, space_after=0)
    tf2 = _textbox(slide, _inches(11.3), _inches(6.95), _inches(1.5), _inches(0.4))
    p = tf2.paragraphs[0]
    p.text = f"{page} / {total}"
    p.alignment = 2  # right
    for run in p.runs:
        run.font.size = _pt(10)
        run.font.color.rgb = _rgb(MUTED)


def _header(slide, spec, idx, total):
    title = spec.get("title", "")
    kicker = spec.get("kicker")
    if kicker:
        tf = _textbox(slide, _inches(0.55), _inches(0.32), _inches(8.0), _inches(0.35))
        _para(tf, kicker.upper(), size=11, color=ACCENT, bold=True, first=True, space_after=0)
    tf = _textbox(slide, _inches(0.5), _inches(0.62), _inches(12.3), _inches(0.95))
    _para(tf, title, size=30, color=FG, bold=True, first=True, space_after=0)
    # garis aksen
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, _inches(0.55), _inches(1.62),
                                 _inches(1.6), _inches(0.045))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(ACCENT)
    bar.line.fill.background()
    _add_footer(slide, idx, total)


def _notes(slide, text: str):
    if text:
        slide.notes_slide.notes_text_frame.text = text


def _panel(slide, left, top, width, height, panel_title, lines, accent=ACCENT):
    from pptx.enum.shapes import MSO_SHAPE
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, _inches(left), _inches(top),
                                 _inches(width), _inches(height))
    box.fill.solid()
    box.fill.fore_color.rgb = _rgb(PANEL)
    box.line.color.rgb = _rgb(LINE)
    box.line.width = _pt(0.75)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = _inches(0.18)
    tf.margin_right = _inches(0.12)
    tf.margin_top = _inches(0.12)
    _para(tf, panel_title, size=15, color=accent, bold=True, first=True, space_after=8)
    for line in lines:
        _para(tf, line, size=11.5, color=FG, bullet_char="·", space_after=4)


def build(out_path: pathlib.Path) -> int:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    total = len(SLIDES)

    for idx, spec in enumerate(SLIDES, 1):
        slide = prs.slides.add_slide(blank)
        _set_bg(slide)
        kind = spec.get("kind", "content")

        if kind == "title":
            bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.14))
            bar.fill.solid()
            bar.fill.fore_color.rgb = _rgb(ACCENT)
            bar.line.fill.background()
            tf = _textbox(slide, Inches(0.9), Inches(2.3), Inches(11.5), Inches(1.4))
            _para(tf, spec["title"], size=54, color=FG, bold=True, first=True, space_after=10)
            tf2 = _textbox(slide, Inches(0.9), Inches(3.6), Inches(11.5), Inches(0.8))
            _para(tf2, spec["subtitle"], size=20, color=MUTED, first=True)
            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.95), Inches(4.45),
                                          Inches(2.2), Inches(0.05))
            line.fill.solid()
            line.fill.fore_color.rgb = _rgb(ACCENT)
            line.line.fill.background()
            tf3 = _textbox(slide, Inches(0.9), Inches(4.8), Inches(11.5), Inches(1.2))
            _para(tf3, f"by {AUTHOR}", size=22, color=FG, bold=True, first=True, space_after=6)
            _para(tf3, f"Versi aplikasi {APP_VERSION}  ·  presentasi dibangun {BUILD_DATE}",
                  size=13, color=MUTED)
            _notes(slide, spec.get("note", ""))

        elif kind == "end":
            tf = _textbox(slide, Inches(0.9), Inches(1.6), Inches(11.5), Inches(1.2))
            _para(tf, spec["title"], size=44, color=FG, bold=True, first=True, space_after=8)
            tf2 = _textbox(slide, Inches(0.9), Inches(2.7), Inches(11.5), Inches(0.7))
            _para(tf2, spec["subtitle"], size=24, color=ACCENT, bold=True, first=True)
            tf3 = _textbox(slide, Inches(0.9), Inches(3.7), Inches(11.5), Inches(2.2))
            for i, b in enumerate(spec.get("bullets", [])):
                _para(tf3, b, size=15, color=MUTED if i else FG, first=(i == 0), bullet_char="·")
            _notes(slide, spec.get("note", ""))

        elif kind == "boxes":
            _header(slide, spec, idx, total)
            boxes = spec["boxes"]
            w, gap = 3.85, 0.42
            left = 0.62
            for i, (b_title, b_body, color) in enumerate(boxes):
                x = left + i * (w + gap)
                box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.2),
                                             Inches(w), Inches(2.5))
                box.fill.solid()
                box.fill.fore_color.rgb = _rgb(PANEL)
                box.line.color.rgb = _rgb(color)
                box.line.width = _pt(1.5)
                tf = box.text_frame
                tf.word_wrap = True
                _para(tf, b_title, size=17, color=_rgb_tuple(color), bold=True, first=True,
                      space_after=10)
                for line in b_body.split("\n"):
                    _para(tf, line, size=12, color=FG, space_after=3)
                if i < len(boxes) - 1:
                    arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + 0.05),
                                                   Inches(3.3), Inches(0.32), Inches(0.3))
                    arrow.fill.solid()
                    arrow.fill.fore_color.rgb = _rgb(MUTED)
                    arrow.line.fill.background()
            _notes(slide, spec.get("note", ""))

        elif kind == "flow":
            _header(slide, spec, idx, total)
            steps = spec["steps"]
            w = 2.35
            gap = 0.2
            total_w = len(steps) * w + (len(steps) - 1) * gap
            left = (13.333 - total_w) / 2
            for i, s in enumerate(steps):
                x = left + i * (w + gap)
                box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.2),
                                             Inches(w), Inches(1.15))
                box.fill.solid()
                box.fill.fore_color.rgb = _rgb(PANEL)
                box.line.color.rgb = _rgb(ACCENT)
                tf = box.text_frame
                tf.word_wrap = True
                _para(tf, s, size=12, color=FG, first=True, space_after=0)
                if i < len(steps) - 1:
                    arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + w + 0.01),
                                                   Inches(2.7), Inches(0.18), Inches(0.22))
                    arrow.fill.solid()
                    arrow.fill.fore_color.rgb = _rgb(MUTED)
                    arrow.line.fill.background()
            tf = _textbox(slide, Inches(0.7), Inches(3.9), Inches(12.0), Inches(2.4))
            for i, b in enumerate(spec.get("bullets", [])):
                _para(tf, b, size=15, color=FG, first=(i == 0), bullet_char="·")
            _notes(slide, spec.get("note", ""))

        else:  # content
            _header(slide, spec, idx, total)
            if spec.get("panels"):
                panels = spec["panels"]
                w = 3.95
                gap = 0.3
                left = (13.333 - (len(panels) * w + (len(panels) - 1) * gap)) / 2
                for i, (p_title, lines) in enumerate(panels):
                    _panel(slide, left + i * (w + gap), 2.1, w, 4.3, p_title, lines)
            elif spec.get("steps"):
                steps = spec["steps"]
                tf = _textbox(slide, Inches(0.7), Inches(2.0), Inches(11.9), Inches(1.6))
                for i, s in enumerate(steps):
                    _para(tf, s, size=16, color=FG, first=(i == 0),
                          bullet_char=f"{i+1}.", space_after=7)
                tf2 = _textbox(slide, Inches(0.7), Inches(3.8), Inches(11.9), Inches(2.6))
                for i, b in enumerate(spec.get("bullets", [])):
                    _para(tf2, b, size=14.5, color=MUTED, first=(i == 0), bullet_char="·")
            elif spec.get("code"):
                tf = _textbox(slide, Inches(0.7), Inches(2.05), Inches(11.9), Inches(2.5))
                for i, line in enumerate(spec["code"]):
                    p = _para(tf, line, size=13, color=(0xB8, 0xD4, 0xFF), first=(i == 0),
                              space_after=6)
                    for run in p.runs:
                        run.font.name = "Consolas"
                tf2 = _textbox(slide, Inches(0.7), Inches(4.75), Inches(11.9), Inches(1.9))
                for i, b in enumerate(spec.get("bullets", [])):
                    _para(tf2, b, size=14.5, color=MUTED, first=(i == 0), bullet_char="·")
            elif spec.get("table"):
                rows = spec["table"]
                cols = len(rows[0])
                from pptx.util import Inches as In
                tbl_shape = slide.shapes.add_table(len(rows), cols, In(0.7), In(1.95),
                                                   In(11.9), In(1.4))
                table = tbl_shape.table
                for r, row in enumerate(rows):
                    for c, cell in enumerate(row):
                        cell_obj = table.cell(r, c)
                        cell_obj.text = cell
                        for p in cell_obj.text_frame.paragraphs:
                            for run in p.runs:
                                run.font.size = _pt(12 if r else 12.5)
                                run.font.bold = r == 0
                                run.font.color.rgb = _rgb(FG if r == 0 else (0xC9, 0xD1, 0xD9))
                tf = _textbox(slide, Inches(0.7), Inches(3.75), Inches(11.9), Inches(2.7))
                for i, b in enumerate(spec.get("bullets", [])):
                    _para(tf, b, size=14.5, color=MUTED, first=(i == 0), bullet_char="·")
            elif spec.get("bars"):
                max_w = 6.6
                top = 1.95
                for i, (label, val, color) in enumerate(spec["bars"]):
                    y = top + i * 0.42
                    tf = _textbox(slide, Inches(0.7), Inches(y - 0.05), Inches(3.6), Inches(0.35))
                    _para(tf, label, size=11.5, color=FG, first=True, space_after=0)
                    bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(4.35),
                                                 Inches(y), Inches(max_w * val / 100.0), Inches(0.22))
                    bar.fill.solid()
                    bar.fill.fore_color.rgb = _rgb(color)
                    bar.line.fill.background()
                tf = _textbox(slide, Inches(0.7), Inches(6.15), Inches(11.9), Inches(0.7))
                for i, b in enumerate(spec.get("bullets", [])):
                    _para(tf, b, size=12, color=MUTED, first=(i == 0), bullet_char="·")
            else:
                tf = _textbox(slide, Inches(0.7), Inches(2.05), Inches(11.9), Inches(4.4))
                for i, b in enumerate(spec.get("bullets", [])):
                    _para(tf, b, size=16.5, color=FG, first=(i == 0), bullet_char="·",
                          space_after=11)
            _notes(slide, spec.get("note", ""))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    return total


def _rgb_tuple(t):
    from pptx.dml.color import RGBColor
    return RGBColor(*t)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Domino Analyzer Pro deck")
    ap.add_argument("--out", default=str(OUT_DEFAULT), help="berkas PPTX keluaran")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    total = build(out)
    print(f"[deck] {total} slide -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
