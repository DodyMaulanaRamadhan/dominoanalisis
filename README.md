# 🎲 Domino Analyzer Pro

![CI](https://github.com/DodyMaulanaRamadhan/dominoanalisis/actions/workflows/ci.yml/badge.svg)

Aplikasi analisis langkah domino (klik/kartu 0–6) dengan mesin simulasi Monte-Carlo **C++20**,
server API **Python 3**, dan UI web ringan. Dirancang untuk permainan domino 28 kartu
(2–4 pemain) dengan mekanik **cangkul** (menyampan kartu saat PASS).

```
web/        UI (HTML/CSS/JS + PWA)  ── fetch JSON ──┐
server/     HTTP server Python (port 2024)          │ validasi + normalisasi
engine/     Mesin C++20 (Monte-Carlo)  ◄── stdin/stdout JSON
```

## Fitur

### Mesin analisis (v3)
- **Monte-Carlo adversarial**: setiap kandidat langkah disimulasikan ribuan hingga
  1,7 juta kali (tier bawaan 10 rb ≈ 95% ±1%; tertinggi 1,7 jt ≈ 99% ±0,1%) melawan
  lawan AI dengan **3 profil gaya** (Blocker / Hoarder / Dumper) yang dirotasi antar-sim —
  rekomendasi tidak overfit ke satu gaya main.
- **Mode teliti (adversarial)**: lawan pertama membalas dengan permainan deterministik
  ketat, bukan heuristik berisik → estimasi lebih konservatif & realistis.
- **Simulasi cangkul (boneyard)**: pemain yang PASS menyampan kartu hingga bisa main —
  konservasi 28 kartu diverifikasi self-test.
- **Konvensi meja yang bisa diatur**: aturan adu (mata terkecil vs rata-rata) dan
  aturan seri (menang vs kalah).
- **Confidence interval Wilson 95%** di setiap win rate → perbedaan tipis tidak menyesatkan.
- **Ranking satu sumber kebenaran** (`rankScore`) dihitung di engine, bukan di UI.
- **Deterministik**: seed tetap → hasil identik (RNG xoshiro256**).

### Tracking lawan
- **PASS lawan** → eliminasi angka ujung dari kemungkinan kartu mereka.
- **Atribusi kartu (baru v3)**: klik kartu sisa → pilih lawan pemainnya → kartu itu
  dipastikan di tangan lawan tersebut dan **dieliminasi dari lawan lain**.
- **Profil kekayaan angka per lawan**: perkiraan angka yang dikuasai (+ berapa kartu,
  % kepercayaan) dan perkiraan jumlah balak.
- Urutan giliran (`Main Setelah Saya`) ikut dipertimbangkan simulasi.

### UI/UX
- Autosave ke localStorage + **Export/Import sesi** (JSON).
- **Undo timeline** konsisten — kartu, atribusi, dan PASS lawan ikut ter-undo.
- Banner menang saat tangan habis; panduan PASS saat tidak ada langkah valid.
- Analisis bisa **dibatalkan**; pesan error ramah (format kartu dinormalisasi otomatis:
  `6-1`, `6|1`, `6:1`, `61` → semua diterima).
- **PWA** (installable, offline shell) + label aksesibilitas pada semua kartu.

## Menjalankan

```bash
python start.py            # build engine (jika perlu) + self-test + serve di :2024
python start.py --check    # build + self-test saja
```

Buka `http://127.0.0.1:2024`. Untuk tunnel publik:
```bash
cloudflared tunnel --url http://127.0.0.1:2024
```

### Variabel lingkungan
| Var | Default | Arti |
|---|---|---|
| `PORT` | `2024` | Port server (atau `DOMINO_PORT`, yang diprioritaskan) |
| `HOST` | `127.0.0.1` | Bind address |
| `APP_TOKEN` | *(kosong)* | Jika diisi: semua `POST /api/*` wajib header `X-App-Token` |

## API

| Endpoint | Metode | Keterangan |
|---|---|---|
| `/api/health` | GET | Status server + engine |
| `/api/analyze` | POST | Analisis Monte-Carlo (JSON) |
| `/api/selftest` | POST | Self-test engine |
| `/api/meta` | POST | Daftar kartu sisa |

Contoh `/api/analyze` (field v3): `nextSeat`, `deadlockRule`, `tieRule`, `adversarial`,
`playedBy` (paralel dengan `played`: `"me" | "opp1".. | "unknown"`).
Respons berisi `winLo/winHi` (interval Wilson), `rankScore`, `boneyardCount`,
`opponents[]` (profil kekayaan angka per lawan).

## Panduan strategi singkat

- **Jerat** — mainkan kartu yang menyisakan angka dominan Anda di ujung; lawan yang
  menyambung wajib membuka jalur Anda kembali.
- **Blok/kunci** — jika peta angka menunjukkan angka ujung habis dari lawan
  (`❓0`), Anda memegang satu-satunya akses: kunci ujung itu.
- **Adu** — jika tangan Anda ringan, dorong permainan macet; menang adu dihitung
  sesuai konvensi yang Anda atur di panel setup.
- **Balak** — umumnya buang cepat, kecuali balaknya angka dominan Anda.

## Dokumentasi

Buku penjelasan sekaligus panduan lengkap ada di `docs/`:

| Berkas | Isi |
|---|---|
| `docs/Domino-Analyzer-Pro-Dokumentasi.pdf` | buku lengkap — 10 Bagian, 106 sub-bab bernomor, 9 diagram, daftar isi bertaut |
| `docs/Domino-Analyzer-Pro-Dokumentasi.md` | sumber buku dalam Markdown |
| `docs/Domino-Analyzer-Pro-Dokumentasi.docx` | versi yang bisa diedit |
| `docs/Domino-Analyzer-Pro-Presentasi.pptx` | presentasi ringkas (31 slide, ada catatan pembicara) |

Isi buku ditulis di `docs/src/*.md` dan dibangun ulang dengan:

```bash
pip install fpdf2 python-docx python-pptx    # hanya untuk membangun dokumen
python tools/build_docs.py                   # Markdown + PDF + DOCX
python tools/build_deck.py                   # PPTX
```

Diagram digambar oleh pembangun PDF, jadi di versi Markdown penandanya masih berupa
komentar `<!--DIAGRAM:...-->`.

Teks buku memakai **Times New Roman** (cadangan: Liberation Serif, Georgia, DejaVu Serif).
Gambar latar sampul digambar dengan Pillow saat build dan disimpan di direktori sementara,
jadi tidak ada aset biner di dalam repo — `python tools/build_docs.py` cukup untuk
membangun ulang semuanya dari `docs/src/*.md`.

## Testing

```bash
python tools/selftest.py     # 11 invarian engine (deck, parser, determinisme,
                             #   konservasi+constraint deal, simulasi, cangkul,
                             #   ranking, aturan adu, atribusi, interval Wilson)
python tools/test_server.py  # 27 unit test server (normalisasi, validasi, e2e, keamanan)
```

CI (GitHub Actions) menjalankan keduanya di Linux (g++) dan Windows (MSVC) pada setiap push.
