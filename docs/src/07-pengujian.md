# Bagian VII — Pengujian & Kualitas

Aplikasi ini adalah alat pengambil keputusan. Kesalahan di dalamnya tidak muncul sebagai
kerusakan yang terlihat, melainkan sebagai **angka yang salah dengan tampilan yang
meyakinkan**. Karena itu pengujiannya tidak berhenti pada "programnya jalan", melainkan
memeriksa sifat-sifat yang harus selalu benar — invarian.

## Sebelas pemeriksaan mandiri mesin

Mesin membawa pemeriksaannya sendiri. Jalankan:

```bash
python tools/selftest.py
```

Mesin menerima perintah `selftest` dan mengembalikan daftar pemeriksaan beserta hasilnya.

| # | Nama pemeriksaan | Yang dijamin |
|---|---|---|
| 1 | `deck_28_kartu` | tepat 28 kartu unik dari `0-0` sampai `6-6` |
| 2 | `parser_json` | parser bawaan membaca objek, larik, angka, boolean, dan null dengan benar |
| 3 | `determinisme_seed` | analisis yang sama dengan seed sama menghasilkan keluaran identik |
| 4 | `deal_konservasi_&_constraint` | pada 400 skenario acak: kartu tidak hilang/berganda, batasan PASS dipatuhi, dan kartu hasil atribusi benar-benar masuk ke tangan yang tepat |
| 5 | `simulasi_invariant` | 500 gim acak selalu berhenti, konservasi kartu terjaga, dan statistik wajar |
| 6 | `boneyard_konservasi` | pada 2 pemain, sisa kartu selalu 14 dan semua kartu tetap terhitung |
| 7 | `ranking_rankScore` | daftar langkah dari mesin benar-benar terurut menurun menurut rankScore |
| 8 | `aturan_adu` | peluang menang dengan "seri = kalah" tidak pernah melebihi "seri = menang" |
| 9 | `cangkul_mode` | bila cangkul dimatikan, tidak ada satu pun sambaran; dengan cangkul, konservasi tetap terjaga |
| 10 | `atribusi_endgame` | permainan akhir dengan 12 kartu lawan yang diatribusikan tetap bisa dianalisis (regresi dari kesalahan lama) |
| 11 | `interval_wilson` | interval keyakinan mengurung peluang terukur, nilainya benar untuk kasus uji, dan menyempit saat simulasi ditambah |

Keluaran nyata dari mesin versi ini:

```text
[selftest] [PASS] deck_28_kartu - 28 tile unik 0-0 .. 6-6
[selftest] [PASS] parser_json - ok
[selftest] [PASS] determinisme_seed - 2 pemain, seed tetap, 2x analisis identik
[selftest] [PASS] deal_konservasi_&_constraint - 400 skenario acak | fallback terjadi di 57 skenario (informasi)
[selftest] [PASS] simulasi_invariant - 500 gim acak berhenti & statistik konsisten
[selftest] [PASS] boneyard_konservasi - 200 gim 2-pemain, semua tile tetap terhitung 28
[selftest] [PASS] ranking_rankScore - moves terurut rankScore desc
[selftest] [PASS] aturan_adu - winRate(lose) <= winRate(win) pada semua langkah
[selftest] [PASS] cangkul_mode - cangkul=false -> 0 nyamber; cangkul=true -> konservasi
[selftest] [PASS] atribusi_endgame - end-game: 12 kartu teratribusi lawan, analisis tetap jalan
[selftest] [PASS] interval_wilson - w=346/500 -> 0.650..0.731, lebar menyempit saat n naik
[selftest] semua check LOLOS
```

Perhatikan baris nomor 4: laporan itu menyebutkan bahwa pada 57 dari 400 skenario, jalur
cadangan terpakai. Itu **bukan kegagalan** — pemeriksaan tetap lulus karena konservasi dan
kepatuhan batasan diverifikasi hanya pada skenario yang tidak memakai jalur cadangan, dan
jumlah fallback dilaporkan sebagai informasi. Prinsipnya: bila batasan yang Anda berikan
secara matematis mustahil dipenuhi (misalnya kuota kartu lebih besar daripada kartu yang
tersedia setelah eliminasi), mesin harus tetap berjalan dan tetap jujur tentang itu.

## Dua puluh tujuh uji server

```bash
python tools/test_server.py
```

Suite ini menjalankan server sungguhan pada port sementara dan menguji tiga kelompok.

**Normalisasi format kartu (4 tes).** Bentuk kanonik (`3-5`, `6-1`), pemisah ramah
(`6|1`, `3:2`, `4 5`, `61`), bentuk tidak sah yang harus ditolak (`7-1`, `a-b`, kosong,
`1-2-3`, angka bukan string), dan satu tes khusus yang memastikan **pesan galat tidak
pernah memantulkan masukan mentah** — termasuk ketika masukan itu berisi skrip HTML.

**Validasi permintaan (6 tes).** Permintaan yang sah diterima; `nextSeat` di luar batas
ditolak; aturan adu dan aturan seri yang tidak dikenal ditolak; panjang `playedBy` dan
label pemain diperiksa; kartu yang muncul di tangan dan papan sekaligus ditolak; serta
batas `numSims` (1 sampai 2000000, nilai aneh seperti `10^12`, bilangan negatif, teks, dan
nilai kosong semuanya ditolak) — pengaman anti pembebanan CPU.

**Uji langsung terhadap server (17 tes).** Endpoint kesehatan, `/api/meta` yang
menormalkan masukan dan hanya mengembalikan kartu yang benar-benar ada, analisis
end-to-end, mode cangkul mati beserta kartu sisa mati, atribusi `playedBy`, kasus
permainan akhir dengan banyak atribusi, dan kontrak keamanan:

| Tes keamanan | Yang dibuktikan |
|---|---|
| `security_headers_present` | header `nosniff`, `no-referrer`, dan CSP ada di berkas statis maupun balasan API |
| `reject_non_json_content_type` | `text/plain` dan `application/x-www-form-urlencoded` ditolak (vektor CSRF peramban) |
| `reject_cross_origin` | `Origin` yang berbeda dari `Host` ditolak, sementara `Origin` yang sama diterima |
| `numSims_out_of_range_rejected` | permintaan berat ditolak dengan status 400 |
| `malformed_bodies_clean_400` | badan non-objek dan JSON bersarang 5000 tingkat dijawab 400 dengan rapi, bukan memutus koneksi |
| `error_over_http_never_echoes_input` | masukan berisi skrip tidak muncul di pesan galat |
| `error_never_returns_http_200` | lima kasus galat, termasuk yang lolos validasi server tetapi ditolak mesin, semuanya bukan 200 |
| `ok_false_body_always_paired_with_non_200` | aturan umum: setiap balasan `ok:false` selalu disertai status 4xx atau 5xx |
| `unknown_endpoint_and_method_still_4xx` | endpoint tidak dikenal menjawab 404 |
| `meta_only_real_tiles` | `/api/meta` tidak lagi mengembalikan kartu mustahil seperti `0-7` (regresi lama) |

Dua tes terakhir pada kelompok pertama dan beberapa tes di atas adalah contoh tes yang
**lahir dari kesalahan nyata**: setiap kali sebuah cacat ditemukan, tesnya ditambahkan
supaya cacat itu tidak bisa kembali tanpa ketahuan.

Hasil menjalankan suite di mesin ini:

```text
Ran 27 tests in 0.781s
OK
```

## Integrasi berkelanjutan (CI)

Setiap kali perubahan dikirim ke cabang `main`, tiga pekerjaan berjalan di GitHub Actions:

| Pekerjaan | Sistem | Yang dijalankan |
|---|---|---|
| `engine-linux` | Ubuntu, g++ | bangun mesin, selftest, uji server |
| `engine-windows` | Windows, MSVC | bangun mesin, selftest, uji server |
| `server-linux` | Ubuntu, tanpa mesin | uji server saja (tes yang butuh mesin dilewati dengan rapi) |

Tiga pekerjaan ini menjawab tiga pertanyaan berbeda:

1. **Apakah mesin masih bisa dibangun oleh dua kompiler berbeda?** Ini menangkap
   penggunaan fitur bahasa yang tidak portabel.
2. **Apakah invarian mesin masih berlaku?** Ini yang menjalankan sebelas pemeriksaan.
3. **Apakah server tetap benar tanpa mesin?** Ini memastikan validasi, normalisasi, dan
   kontrak status HTTP tidak bergantung pada biner yang ada.

Perhatikan pekerjaan ketiga: uji server dirancang agar tes yang membutuhkan mesin
**dilewati secara sadar** (`skipTest`) bila biner belum dibangun, bukan gagal. Prinsipnya
sama seperti jalur cadangan pada pembagian kartu: kekurangan prasyarat dilaporkan, bukan
disamarkan.

## Bagaimana membuktikan hasil analisis bisa dipercaya

Ada prosedur tiga langkah yang bisa Anda jalankan sendiri, tanpa membaca kode:

**Langkah 1 — buktikan determinisme.** Jalankan permintaan yang sama dua kali dan
bandingkan keluarannya:

```bash
python - <<'PY'
import json, subprocess
req = json.dumps({"cmd":"analyze","numPlayers":4,"cardsPerPlayer":7,"numSims":300,
                  "seed":123,"leftEnd":-1,"rightEnd":-1,
                  "myHand":["0-0","1-2","3-4"],"played":[],
                  "opponents":[{},{},{}]})
run = lambda: subprocess.run(["./bin/domino_engine.exe"],
                             input=req.encode(), capture_output=True).stdout
print("identik:", run() == run())
PY
```

Bila keluaran `identik: True`, mesin Anda bersikap deterministik.

**Langkah 2 — periksa konservasi kartu.** Setiap langkah pada balasan analisis memuat
bidang `conserved`. Nilai `true` berarti tidak ada kartu yang muncul atau hilang selama
simulasi untuk kandidat itu.

**Langkah 3 — periksa kewajaran interval keyakinan.** Untuk 500 simulasi dan peluang
sekitar 70%, selang seharusnya berkisar sekitar 4 sampai 5 poin ke kiri dan ke kanan
(misalnya 65-73%). Bila Anda melihat selang yang menempel ke 0% atau 100%, ada yang salah
pada perhitungannya.

## Sebuah cacat nyata: rumus interval keyakinan

Karena dokumentasi ini menyertakan contoh keluaran yang benar-benar dihitung mesin,
penulisnya menemukan sesuatu saat menyusun Bagian V: **setiap interval keyakinan tampil
sebagai 0,0% sampai 100,0%.** Peluang menangnya benar, tetapi rentang keyakinannya tidak
berguna sama sekali.

Penyebabnya rumus Wilson yang ditulis salah: suku `p(1-p)` tidak dibagi jumlah simulasi,
dan pembagi akhirnya dipasang di tempat yang salah, sehingga marginnya terlalu besar dan
selalu terpotong ke batas 0-1. Perhatikan mengapa cacat ini bisa lolos: uji yang ada hanya
memeriksa bahwa interval **mengurung** peluang terukur — dan `[0,1]` memang mengurung
semuanya. Uji itu benar secara logika, tetapi terlalu longgar untuk menangkap kesalahannya.

Perbaikannya tiga hal sekaligus:

1. rumus Wilson dikoreksi di mesin (dan diberi komentar agar tidak terulang);
2. pemeriksaan mandiri nomor 11 ditambahkan ke mesin, yang memeriksa nilai interval pada
   kasus uji yang diketahui **dan** memastikan interval menyempit saat simulasi ditambah;
3. uji end-to-end server diperketat: untuk 200 simulasi, lebar interval kini harus di
   bawah 30 poin, sehingga interval yang menempel ke 0-100% akan gagal.

Pelajaran yang bisa dibawa ke pekerjaan apa pun: **uji yang hanya memeriksa batas lemah
memberi rasa aman yang keliru.** Uji yang baik memeriksa sifat yang bermakna — di sini,
bahwa intervalnya benar-benar menyempit ketika data bertambah.

## Yang belum tercakup oleh pengujian otomatis

Kejujuran tentang cakupan sama pentingnya dengan hasil tesnya sendiri.

- **Tata letak antarmuka tidak punya uji otomatis.** Susunan ular, pengecilan papan,
  pemusatan kartu pertama, dan posisi siluet rekomendasi diverifikasi secara manual di
  peramban (termasuk pada lebar ponsel 390 piksel). Perubahan CSS atau JavaScript pada
  bagian itu tidak akan tertangkap oleh tes.
- **Interaksi pengguna belum diuji otomatis.** Modal, masukan cepat, dan alur Undo diuji
  manual.
- **Belum ada tolok ukur kinerja di CI.** Waktu tunggu analisis bergantung pada perangkat;
  angka waktu di Bagian IV adalah perkiraan, bukan hasil pengukuran otomatis.
- **Akurasi heuristik tidak diverifikasi terhadap permainan manusia.** Mesin memverifikasi
  konsistensi internal dan konservasi, bukan "apakah langkah yang disarankan benar-benar
  menang di meja nyata".
- **Pemeriksaan mandiri memakai pembangkit acak bersemai**, jadi hasilnya dapat diulang,
  tetapi cakupan skenarionya tetap terbatas pada skenario yang ditulis di kode.

Bila Anda ingin menambah pengujian, sasaran yang paling berharga saat ini adalah uji
otomatis untuk tata letak papan (misalnya dengan peramban tanpa kepala) dan uji
interaksi dasar untuk alur kartu → PASS → atribusi → Undo.
