# Audit Kualitas Kode — Domino Analyzer Pro

Tanggal: 15 Oktober 2026
Lingkup: `engine/domino_engine.cpp` (C++20), `server/domino_server.py`, `web/` (UI + service
worker), `tools/` (pengujian).
Fokus permintaan: **tidak ada celah sistem yang membuat proses melambat, dan kecepatan
komputasi harus menyeimbangi jumlah simulasi.**

Semua angka di bawah adalah hasil pengukuran di mesin uji (AMD Ryzen 5 5625U — **6 inti
fisik / 12 utas logis**, MSVC 19.44, `/O2`), bukan perkiraan. Cara mengulang ada di
`docs/src/07-pengujian.md`.

---

## 1. Ringkasan

| # | Temuan | Tingkat | Tindakan |
|---|---|---|---|
| 1 | **Crash total** (integer divide by zero / akses di luar batas) pada permintaan sah: pool kartu tak diketahui kosong | Kritis | **Diperbaiki** + tes regresi |
| 2 | Hot loop mengalokasi & menyalin memori ratusan kali per simulasi | Tinggi (kecepatan) | **Diperbaiki** (2,55x) |
| 3 | Simulasi berjalan satu inti saja; 11 dari 12 inti menganggur | Tinggi (kecepatan) | **Diperbaiki** (13,4x) |
| 4 | Kerja sia-sia: `boneyardFinal` disalin tiap simulasi untuk data yang tak pernah dipakai | Sedang | **Dihapus** |
| 5 | Server tanpa batas konkurensi: N permintaan berebut inti CPU yang sama | Sedang (kecepatan) | **Diperbaiki** (antrean) |
| 6 | Potensi null-dereference pada `aiChooseMove` bila skor terbaik tidak pernah terisi | Rendah | **Diperbaiki** (penjaga) |
| 7 | Service worker *cache-first* → UI lama tetap tampil setelah pembaruan | Rendah (UX) | **Diperbaiki** (network-first + bump cache) |
| 8 | Bias modulo pada `nextInt` (`next() % n`) | Rendah (statistik) | **Dibiarkan** (mengubah angka = mengubah kontrak) |
| 9 | `numSims` tanpa hasil paralel untuk UI lain? Tidak — batas 50 rb tetap anti-DoS | Info | Diverifikasi |

**Hasil kinerja (beban 50.000 simulasi x jumlah kandidat langkah = 150.000 simulasi-engine):**

| Versi | Waktu | Laju | Relatif |
|---|---|---|---|
| build HEAD (sebelum audit) | 2,62 s | 57.344 sim/detik | 1,00x |
| setelah audit, 1 thread | 1,03 s | 146.042 sim/detik | **2,55x** |
| setelah audit, 12 thread | 0,20 s | 770.762 sim/detik | **13,44x** |

**Dan output-nya tidak berubah satu angka pun** — 9 skenario dibandingkan byte-per-byte
dengan build HEAD (`tools/audit_golden.py verify`), semuanya `IDENTIK`.

---

## 2. Temuan kritis: mesin bisa dimatikan oleh permintaan yang sah

### Bukti

```bash
# 2 pemain x 14 kartu; 14 kartu di tangan + 14 kartu sudah di papan = 28
# -> tidak ada kartu tersembunyi yang perlu dibagikan
echo '{"cmd":"analyze","numPlayers":2,"cardsPerPlayer":14,"numSims":1,...}' | bin/domino_engine
# exit 3221225477 (0xC0000005) — proses mati, tanpa balasan JSON
```

### Akar masalah

```cpp
void shuffle(std::vector<int>& a) {
    for (size_t k = a.size() - 1; k > 0; --k) {   // vector kosong: k = SIZE_MAX
        size_t j = nextInt(static_cast<int>(k) + 1);  // -> nextInt(0) -> modulo nol
        std::swap(a[k], a[j]);                        // -> tulis di luar batas
    }
}
```

Pada vector kosong `a.size() - 1` menjadi `SIZE_MAX`, lalu `static_cast<int>(SIZE_MAX) + 1`
menjadi `0`: `next() % 0` adalah modulo nol (x86: `0xC0000094`) dan `a[SIZE_MAX]` menulis
di luar batas (`0xC0000005`). Vektor itu kosong ketika **semua** kartu sudah diketahui —
kombinasi yang bisa dicapai pengguna lewat antarmuka (2 pemain, 14 kartu per pemain, semua
kartu sudah ditandai).

### Perbaikan

```cpp
if (a.size() < 2) return;   // tidak ada yang diacak; perilaku ukuran >= 2 tidak berubah
```

Ditambah tes regresi `empty_unknown_pool_does_not_crash`
(`tools/test_engine_parallel.py`) supaya tidak bisa kembali tanpa ketahuan.

---

## 3. Kecepatan: mengapa lambat, dan apa yang diperbaiki

### 3.1 Alokasi memori di hot loop (2,55x)

Setiap simulasi (gim Monte-Carlo penuh) sebelumnya membangun struktur data baru dari nol:

| Lokasi | Alokasi per simulasi |
|---|---|
| `dealConstrained` | `Deal` + vector per lawan + salinan pool + `quotas` + `order` |
| `simulateGame` | salinan tangan sendiri, salinan tangan semua lawan, salinan boneyard |
| `analyzeDominance` (dipanggil ~1x per giliran per lawan) | `ranked` + `std::stable_sort` + `dominant` + `strong` |
| `aiChooseMove` (dipanggil setiap giliran) | vector langkah + satu salinan tangan **per kandidat langkah** |
| `applyMove` (setiap giliran) | vector tangan baru |

Dengan 50.000 simulasi x beberapa kandidat langkah, jumlahnya menjadi puluhan juta
`malloc`/`free` per permintaan.

Perbaikan (semuanya tanpa mengubah aritmetika):

- `Dominance` memakai `std::array` dengan penghitung, dan pengurutan diganti *insertion
  sort* stabil tanpa alokasi (urutan hasil identik dengan `std::stable_sort`).
- `aiChooseMove` menulis langkah ke buffer stack dan **tidak menyalin tangan**: nilai
  `flex`, kemunculan angka ujung, dan `haveL/haveR` dihitung satu lintasan sambil melewati
  kartu yang dimainkan.
- `dealConstrained` dan `simulateGame` memakai buffer yang dipakai ulang
  (`DealScratch`, `SimScratch`) dengan `assign`/`clear` sehingga kapasitas vektor
  dipertahankan antar-simulasi.
- Dominasi lawan di-cache dan hanya dihitung ulang ketika tangan lawan benar-benar berubah.

### 3.2 Satu inti dari dua belas (13,44x)

Mesin sepenuhnya sekuensial. Karena game ke-`s` bergantung pada stream RNG bersama,
paralelisasi naif akan mengubah hasil. Solusinya: **snapshot stream**.

Setiap simulasi mengonsumsi jumlah undian yang **tetap** dari RNG induk
(`shuffle` pool = `n-1` undian, lalu 1 undian untuk seed gim). Jadi state RNG di awal
setiap blok kerja bisa dihitung lebih dulu dengan satu lintasan sekuensial yang murah,
lalu setiap blok dijalankan paralel dari snapshot-nya. Hasilnya:

- urutan undian tiap simulasi **sama persis** seperti mode 1 thread;
- agregasi hanya penjumlahan bilangan bulat → tidak bergantung urutan blok;
- jumlah thread berapa pun memberi angka yang identik.

Verifikasi: `parallel_equals_sequential` (1 vs 2 vs 8 thread) dan 9 skenario golden
dibandingkan byte-per-byte dengan build HEAD.

Bawaan: semua inti logis (maksimum 32), ambang 2000 simulasi ke bawah tetap sekuensial
karena ongkos membuat thread lebih besar dari manfaatnya. `DOMINO_THREADS=1` memaksa
sekuensial.

### 3.3 Kerja sia-sia yang dihapus

`SimResult::boneyardFinal` disalin setiap simulasi (satu salinan vector per gim) hanya
untuk mengisi `deadCnt`, yang **tidak pernah dibaca**. Keduanya dihapus; keluaran tidak
berubah (dibuktikan golden test).

---

## 4. Celah sistem lain

### 4.1 Konkurensi server (diperbaiki)

`ThreadingHTTPServer` membuat thread tanpa batas, sehingga tidak ada yang menahan beberapa
proses mesin agar tidak berebut inti CPU yang sama.

**Bukti terukur** (beban 50.000 simulasi x 3 langkah, 4 permintaan, mesin uji 12 utas
logis / 6 inti fisik):

| Pola | Waktu tiap permintaan | Median |
|---|---|---|
| satu permintaan pada satu waktu | 0,18 / 0,19 / 0,22 / 0,25 s | **0,19 s** |
| 4 permintaan bersamaan | 0,69 / 0,64 / 0,71 / 0,64 s | **0,64 s** |

Setiap permintaan menjadi **3,32x lebih lambat** ketika dijalankan bersamaan — tanpa satu
pun selesai lebih cepat (total waktu kerja tetap sama, hanya dibagi). Karena itu server
sekarang mengantrekan pekerjaan mesin:

| Variabel | Bawaan | Arti |
|---|---|---|
| `DOMINO_MAX_ENGINE` | `1` | jumlah proses mesin bersamaan |
| `DOMINO_ENGINE_WAIT` | `60` | batas tunggu dalam antrean (detik) sebelum 503 |

Satu permintaan pada satu waktu = setiap analisis memakai seluruh inti.

### 4.2 Yang diperiksa dan **sudah** aman (tanpa perubahan)

| Aspek | Cara diperiksa | Hasil |
|---|---|---|
| Path traversal berkas statis | `_send_static` memakai `resolve()` + `is_relative_to(web_root)` | Aman, termasuk `..`, backslash, dan symlink keluar folder |
| XSS dari pesan galat | Pesan validasi tidak pernah memantulkan masukan mentah; diuji `error_over_http_never_echoes_input` | Aman |
| XSS dari keluaran mesin | Semua teks alasan berasal dari mesin (angka + frasa tetap); kartu divalidasi `0-6` di server dan UI | Aman |
| CSRF ke localhost | `Content-Type` wajib `application/json` + `Origin` harus sama dengan `Host` | Aman |
| Pembebanan CPU | `numSims` dibatasi 1..1700000 di server **dan** mesin; badan 1 MiB; timeout 300 s | Aman |
| Konservasi kartu | self-test mengecek `tilesTotal + onBoard == tilesAtDeal` tiap gim | Aman |
| Timing oracle token | `hmac.compare_digest` | Aman |

### 4.3 Dibiarkan sengaja (dengan alasan)

- **Bias modulo kecil pada `nextInt`** (`next() % n`). Bisa dihilangkan dengan *rejection
  sampling*, tetapi itu mengubah urutan angka acak → seluruh angka yang sudah
  didokumentasikan (contoh di buku, presentasi) berubah. Bias untuk `n <= 28` jauh lebih
  kecil daripada lebar interval keyakinan, jadi tidak sebanding dengan risikonya. Dicatat
  di sini sebagai keputusan sadar, bukan kelalaian.
- **Batas 300 detik per permintaan.** Dengan kecepatan baru, 50.000 simulasi x 14 kandidat
  langkah selesai dalam hitungan detik, jadi batas ini praktis tidak pernah tercapai.
- **Proses mesin di-spawn per permintaan.** Ongkos ~10 ms, tidak berarti dibanding detik
  komputasi, dan memberi isolasi kegagalan (crash mesin tidak menjatuhkan server).

---

## 5. Bukti kelengkapan

| Perintah | Hasil |
|---|---|
| `python tools/selftest.py` | 11/11 LOLOS (exit 0) |
| `python tools/test_server.py` | 29/29 OK (exit 0) |
| `python tools/test_engine_parallel.py` | 8/8 OK (exit 0; 4 di antaranya beban penuh) |
| `python tools/test_ui_heavy.py` | 6/6 OK (exit 0) — uji antarmuka tanpa kepala |
| `python tools/audit_golden.py verify <golden HEAD>` | 9/9 IDENTIK; crash pool kosong hilang |
| `python tools/bench_engine.py` | 2,55x (1 thread) / 13,44x (paralel) |

Semua perintah dijalankan tanpa menyaring kode keluar (`echo "exit:$?"`), sehingga status
yang dilaporkan adalah status perintah aslinya.

---

## 6. Pembaruan: tier 1.700.000 dan pembatalan sejati

Setelah audit, tier tertinggi dinaikkan kembali ke **1.700.000 simulasi** (≈95% ±0,1%).
Yang harus dijamin pada beban itu:

**Mesin.** Batas atas kini 1.700.000 dengan pengaman anti-DoS tetap di kedua lapisan
(server dan mesin). Tidak ada overflow: seluruh penghitung besar memakai `long long`
(`totalMyVal`, `totalDraws`, `dangerCnt`), sementara `numSims` (≤1,7 juta) tetap `int`.
Suite beban penuh (`DOMINO_SLOW_TESTS=1`) memverifikasi bahwa `wins + losses == numSims`,
konservasi kartu terjaga, lebar interval < 0,2 poin, dan **output 1/4/12 thread identik**
pada 1,7 juta simulasi.

**Waktu terukur** (mesin uji, 4 pemain, cangkul aktif): 3 kandidat langkah **7,5 s**;
12 kandidat langkah **29,7 s**; mode teliti **7,6 s**; papan kosong dengan seluruh 7 kartu
bisa dibuka (11,9 juta simulasi-langkah) **22,0 s** = 602.081 simulasi-langkah/detik pada
12 utas, efisiensi paralel **87%** dari 6 inti fisik. Semua jauh di bawah batas 300 detik,
jadi tidak ada hasil yang terpotong.

**Pembatalan sejati (celah baru yang ditutup).** Sebelum ini, menekan tombol Batal hanya
memutus koneksi peramban: proses mesin tetap menghitung sampai selesai 1,7 juta simulasi,
memakai seluruh inti CPU untuk hasil yang sudah tidak dipakai siapa pun — dan karena server
mengantrekan pekerjaan, permintaan berikutnya ikut menunggu. Sekarang server mendeteksi
penutupan koneksi (`select` + `MSG_PEEK`) dan **mematikan proses mesin** (`kill`), dengan
polling 0,2 detik. Diuji `test_run_engine_cancel_kills_process` (< 5 detik, tidak ada JSON
utuh) **dan** dari sisi pengguna lewat uji antarmuka tanpa kepala: menekan tombol Batal pada
tier 1,7 juta membuat proses `domino_engine` hilang dalam **~0,4 detik** (dua pengukuran:
0,40 s dan 0,45 s). Keluaran mesin juga
dipindahkan dari pipa ke berkas sementara supaya buffer pipa yang penuh tidak bisa memblokir
mesin pada balasan besar.

**Antarmuka.** Memilih tier ini memunculkan konfirmasi berisi perkiraan waktu (dihitung dari
jumlah kandidat langkah × jumlah simulasi × jumlah inti), mematikan mode Live (agar tidak
ada 1,7 juta simulasi baru di setiap langkah), dan menampilkan waktu berjalan + perkiraan
sisa pada bilah kemajuan. Perilaku ini kini dijaga **uji antarmuka tanpa kepala**
(`tools/test_ui_heavy.py`, 6 uji): peringatan selalu muncul saat tier dinaikkan (termasuk
saat dinaikkan lagi setelah diturunkan), menolak konfirmasi mengembalikan pilihan
sebelumnya, label tombol tidak pernah tertinggal dari tiernya, jeda Live buatan pengguna
tidak dinyalakan kembali oleh pergantian tier, sesi tersimpan tetap diperingatkan setelah
muat ulang, dan Batal benar-benar mematikan proses mesin (log server mencatat
`[engine] dibatalkan`). Selama run 22 detik yang memakai seluruh 12 utas, antarmuka juga
terukur tetap **59 frame/detik** dengan interaksi selesai dalam 18 ms.

## 7. Batasan audit

- Pengukuran dilakukan di satu mesin (6 inti fisik / 12 utas logis, Windows, MSVC). Angka
  absolut akan berbeda di mesin lain; **rasio** antar-varian tetap menjadi acuan yang sah
  karena diukur bergantian pada beban yang sama. Karena 12 utas itu 6 inti fisik dengan SMT,
  "5,23x pada 12 utas" setara 87% dari ideal 6 inti — bukan penurunan efisiensi.
- Percepatan 2,55x pada jalur 1 thread adalah gabungan dari penghapusan alokasi, salinan
  tangan, dan kerja sia-sia (tidak dipisah per faktor).
- Profil CPU tingkat fungsi (sampling profiler) tidak tersedia di lingkungan ini, jadi
  penentuan titik panas memakai pengukuran *ablation* (1 thread vs paralel) dan analisis
  jumlah alokasi per simulasi.
- Audit tidak mencakup pengujian penetrasi eksternal maupun fuzzing menyeluruh pada parser
  JSON internal.
