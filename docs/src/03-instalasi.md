# Bagian III — Memasang & Menjalankan

Bagian ini menuntun Anda dari komputer kosong sampai aplikasi berjalan di peramban.
Semuanya berjalan **lokal**: tidak ada akun, tidak ada pendaftaran, tidak ada data yang
dikirim ke luar komputer Anda.

## Kebutuhan minimum

| Komponen | Kebutuhan | Catatan |
|---|---|---|
| Python | 3.10 atau lebih baru (disarankan 3.11+) | dipakai untuk server, build, dan pengujian |
| Compiler C++20 | MSVC (Windows), g++, atau clang++ | hanya untuk membangun mesin analisis |
| Peramban modern | Chrome, Edge, Firefox, atau Safari terbaru | mendukung PWA dan service worker |
| Ruang disk | sekitar 5 MB untuk kode + 1 MB biner mesin | tanpa basis data |

Anda **tidak** butuh Node.js, npm, Docker, atau koneksi internet setelah pemasangan awal.
Antarmuka memakai HTML, CSS, dan JavaScript biasa tanpa kerangka kerja, dan mesin
analisisnya adalah satu berkas C++ mandiri tanpa pustaka pihak ketiga.

Pemeriksaan cepat sebelum mulai, di jendela terminal:

```bash
python --version
```

Bila perintah itu gagal, pasang Python dari python.org dan pastikan opsi "Add Python to
PATH" dicentang pada saat pemasangan di Windows.

## Menjalankan dalam satu perintah

Cara terpendek dan paling disarankan:

```bash
python start.py
```

Perintah itu menjalankan empat langkah berurutan:

1. **Membangun mesin** lewat `tools/build_engine.py`. Langkah ini pintar: bila biner
   sudah ada dan lebih baru daripada sumber `engine/domino_engine.cpp`, pembangunan
   dilewati sama sekali.
2. **Memeriksa mesin** lewat `tools/selftest.py`. Mesin menjalankan sebelas pemeriksaan
   mandiri (lihat Bagian VII). Bila ada satu saja yang gagal, aplikasi menolak berjalan,
   karena angka analisis tidak bisa dipercaya.
3. **Memeriksa port.** Bila port 2024 sudah melayani `/api/health`, start.py berhenti
   dengan pesan bahwa server lain mungkin sedang berjalan.
4. **Menyalakan server** di `http://127.0.0.1:2024`.

Keluaran yang wajar terlihat seperti ini:

```text
[build] engine up to date: C:\...\bin\domino_engine.exe
[selftest] [PASS] deck_28_kartu - 28 tile unik 0-0 .. 6-6
[selftest] [PASS] parser_json - ok
...
[selftest] semua check LOLOS
[server] Domino Analyzer Pro v3 -> http://127.0.0.1:2024
[server] engine: C:\...\bin\domino_engine.exe (OK)
```

Setelah itu buka `http://127.0.0.1:2024` di peramban. Server berjalan di latar depan;
menutup jendela terminal akan mematikannya.

Untuk memeriksa pemasangan **tanpa** menyalakan server:

```bash
python start.py --check
```

Perintah ini hanya membangun mesin dan menjalankan pemeriksaan mandiri. Berguna untuk
memastikan masalah ada di aplikasi, bukan di jaringan atau port.

## Membangun mesin secara manual

`tools/build_engine.py` mencari compiler dengan urutan berikut:

1. **MSVC** di Windows, ditemukan lewat `vswhere.exe`, lalu lingkungannya dimuat dari
   `vcvars64.bat`. Hasilnya `bin/domino_engine.exe`.
2. **g++** bila ada di PATH. Hasilnya `bin/domino_engine`.
3. **clang++** bila ada di PATH.

Pilihan tambahannya:

```bash
python tools/build_engine.py            # build bila sumber lebih baru
python tools/build_engine.py --force    # selalu build ulang
python tools/build_engine.py --debug    # /Od /Zi atau -O0 -g, untuk penelusuran
```

Bendera yang dipakai: `/EHsc /std:c++20 /utf-8 /O2 /DNDEBUG` untuk MSVC, dan
`-std=c++20 -O2 -DNDEBUG -Wall -Wextra` untuk g++/clang++.

Bila tidak ada compiler yang ditemukan, skrip mencetak
`TIDAK ADA compiler yang bisa dipakai (MSVC/g++/clang++)` dan keluar dengan kode 1.
Aplikasi web tetap bisa dibuka, tetapi setiap analisis akan dijawab dengan pesan bahwa
mesin belum dibangun (HTTP 503) — jadi pemasangan belum lengkap sampai langkah ini
berhasil.

> Untuk Windows, cara termudah mendapat MSVC adalah memasang **Visual Studio Build
> Tools** dan mencentang beban kerja "Desktop development with C++". Setelah itu build
> berjalan tanpa perlu membuka Visual Studio.

## Menjalankan server secara terpisah

```bash
python server/domino_server.py
```

Perintah ini berguna bila Anda ingin mengubah kode frontend tanpa membangun ulang mesin,
atau saat melakukan penelusuran masalah. Berkas statis dilayani apa adanya dengan
`Cache-Control: no-cache`, jadi menyegarkan peramban cukup untuk melihat perubahan
HTML, CSS, atau JavaScript.

Peringatan yang mungkin muncul:

| Pesan | Arti | Tindakan |
|---|---|---|
| `PERINGATAN: engine C++ belum ada` | biner mesin belum dibangun | jalankan `python tools/build_engine.py` |
| `mode proteksi AKTIF: POST /api/* butuh header X-App-Token` | `APP_TOKEN` terisi | kirim header itu dari klien, atau kosongkan variabelnya |

## Konfigurasi lewat variabel lingkungan

| Variabel | Bawaan | Arti |
|---|---|---|
| `HOST` | `127.0.0.1` | alamat bind server. Hanya komputer ini yang bisa mengakses bila `127.0.0.1` |
| `DOMINO_PORT` | `2024` | port server. Nilai `<= 0` dikembalikan ke 2024 |
| `APP_TOKEN` | *(kosong)* | bila diisi, semua `POST /api/*` wajib menyertakan header `X-App-Token` |

Contoh menyalakan di seluruh antarmuka jaringan lokal:

```bash
DOMINO_PORT=8080 HOST=0.0.0.0 python server/domino_server.py
```

> **Catatan akurasi.** Berkas README proyek menyebut variabel `PORT`, tetapi kode di
> `server/domino_server.py` membaca **`DOMINO_PORT`** saja. Selain itu, `start.py`
> memeriksa ketersediaan port pada angka tetap 2024. Jadi bila Anda mengubah port lewat
> `DOMINO_PORT`, jalankan server secara manual — jangan lewat `start.py`.

> **Peringatan keamanan.** `HOST=0.0.0.0` membuat aplikasi bisa diakses siapa pun di
> jaringan yang sama, dan setiap permintaan analisis membebani CPU komputer Anda.
> Endpoint analisis memang dibatasi (maksimum 10.000 simulasi per permintaan), tetapi
> tetap lebih aman membiarkannya di `127.0.0.1` kecuali Anda memang membutuhkan akses
> dari perangkat lain.

### Tentang `APP_TOKEN` dan antarmuka web

`APP_TOKEN` adalah pengaman untuk klien luar: skrip, `curl`, atau alat monitoring. Bila
variabel itu diisi, klien harus mengirim header `X-App-Token` yang nilainya sama.

Penting diketahui: **antarmuka web bawaan belum mengirim header itu.** Bila Anda menyalakan
`APP_TOKEN`, panel analisis di peramban akan menerima HTTP 401 dan menampilkan pesan
kesalahan. Jadi ada dua pilihan yang masuk akal:

- biarkan `APP_TOKEN` kosong dan lindungi aplikasi di lapisan lain (misalnya Cloudflare
  Access atau aturan firewall), atau
- isi `APP_TOKEN` bila Anda hanya memakai API dari skrip, dan jangan buka antarmuka web
  ke publik.

## Membuka akses dari internet (opsional)

Aplikasi ini dirancang untuk pemakaian lokal. Namun ada kalanya Anda ingin memantaunya
dari ponsel saat bermain bersama orang lain. Pola paling aman adalah **tunnel terowongan
yang memberi nama acak**, bukan membuka port ke internet.

```bash
# jendela 1
python start.py
# jendela 2
cloudflared tunnel --url http://127.0.0.1:2024
```

`cloudflared` akan mencetak URL publik acak seperti `https://kata-acak.trycloudflare.com`.
URL itu berlaku selama prosesnya hidup dan berhenti bekerja begitu Anda menutupnya.

Yang perlu Anda sadari sebelum melakukan ini:

- **URL itu terbuka untuk siapa saja yang tahu alamatnya.** Tidak ada kata sandi.
- **Setiap permintaan analisis memakai CPU Anda.** Batas 10.000 simulasi per permintaan
  ada tepat untuk alasan ini, tetapi beberapa pengunjung sekaligus tetap bisa membuat
  komputer Anda sibuk.
- **Isi sesi permainan bersifat pribadi.** Tidak ada data yang dikirim keluar, tetapi
  siapa pun yang membuka URL itu bisa memakai analisis Anda.

Karena itu, untuk pemakaian publik, jauh lebih baik memasang pengaman di lapisan tunnel
(Cloudflare Access, atau proxy yang meminta kata sandi) daripada menambah kerumitan di
dalam aplikasi.

## Memasang sebagai aplikasi (PWA)

Aplikasi ini menyertakan manifest dan service worker, sehingga bisa dipasang seperti
aplikasi biasa. Manfaatnya: jendela sendiri tanpa bilah alamat, dan antarmuka tetap
membuka saat koneksi ke server terputus.

**Di Android (Chrome).** Buka `http://127.0.0.1:2024` (atau alamat LAN Anda) → menu tiga
titik → **Tambahkan ke layar utama**.

**Di iOS (Safari).** Buka alamatnya → tombol **Bagikan** → **Tambahkan ke Layar Utama**.

**Di desktop (Chrome/Edge).** Klik ikon pasang di bilah alamat, atau menu → **Pasang
aplikasi**.

Yang perlu dipahami: PWA memasang **antarmuka**-nya supaya bisa dibuka offline. Analisis
tetap membutuhkan server dan mesin yang berjalan, karena perhitungan beratnya memang
dilakukan di komputer, bukan di peramban. Saat offline, layar terakhir yang tersimpan di
tembolok masih bisa dibuka, tetapi tombol analisis akan gagal terhubung.

Bila Anda mengubah berkas di `web/`, naikkan nama tembolok di `web/sw.js`
(saat ini `domino-analyzer-v3.19`) agar peramban mengambil versi baru. Ini praktik yang
disengaja: strategi temboloknya adalah *cache-first* untuk berkas statis, jadi perubahan
tidak langsung terlihat tanpa mengganti nama tembolok.

## Struktur proyek

```text
domino move analisis/
├── start.py                  peluncur: build + selftest + serve
├── engine/
│   └── domino_engine.cpp     mesin analisis C++20 (satu berkas, tanpa dependensi)
├── bin/
│   ├── domino_engine.exe     biner mesin (Windows)
│   └── domino_engine         biner mesin (Linux/macOS)
├── server/
│   └── domino_server.py      server HTTP + API + penyaji berkas statis
├── web/
│   ├── index.html            kerangka antarmuka
│   ├── app.js                seluruh logika antarmuka
│   ├── styles.css            tema gelap dan tata letak responsif
│   ├── sw.js                 service worker (tembolok offline)
│   ├── manifest.json         metadata PWA
│   └── icon.svg              ikon aplikasi
├── tools/
│   ├── build_engine.py       pencari compiler + pembangun mesin
│   ├── selftest.py           menjalankan pemeriksaan mandiri mesin
│   ├── test_server.py        uji unit server (27 tes)
│   ├── build_docs.py         pembangun buku dokumentasi ini (Markdown, PDF, DOCX)
│   └── build_deck.py         pembangun presentasi PPTX
├── docs/                     buku dokumentasi (sumber + hasil)
└── .github/workflows/ci.yml  alur integrasi berkelanjutan
```

Susunan ini mengikuti satu aturan: **antarmuka boleh sederhana, mesin harus benar.**
Karena itu mesin analisis berdiri sendiri sebagai satu berkas C++ yang bisa dijalankan
dari terminal tanpa server sama sekali, seperti yang akan Anda lihat di Bagian VI.

## Menguji pemasangan Anda

Tiga perintah yang membuktikan pemasangan berjalan benar:

```bash
python tools/selftest.py      # 11 pemeriksaan mandiri mesin
python tools/test_server.py   # 27 uji unit server (butuh mesin untuk tes end-to-end)
python start.py --check       # build + selftest saja, tanpa menjalankan server
```

Bila ketiganya keluar dengan kode 0 dan mencetak "OK" atau "semua check LOLOS",
pemasangan Anda sudah lengkap. Bagian VII menjelaskan apa yang sebenarnya diperiksa
oleh masing-masing perintah.
