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

## Dua puluh sembilan uji server

```bash
python tools/test_server.py
```

Suite ini menjalankan server sungguhan pada port sementara dan menguji tiga kelompok.

**Normalisasi format kartu (4 tes).** Bentuk kanonik (`3-5`, `6-1`), pemisah ramah
(`6|1`, `3:2`, `4 5`, `61`), bentuk tidak sah yang harus ditolak (`7-1`, `a-b`, kosong,
`1-2-3`, angka bukan string), dan satu tes khusus yang memastikan **pesan galat tidak
pernah memantulkan masukan mentah** — termasuk ketika masukan itu berisi skrip HTML.

**Validasi permintaan (8 tes).** Permintaan yang sah diterima; `nextSeat` di luar batas
ditolak; aturan adu dan aturan seri yang tidak dikenal ditolak; panjang `playedBy` dan
label pemain diperiksa; kartu yang muncul di tangan dan papan sekaligus ditolak; serta
batas `numSims` (1 sampai 1700000, nilai aneh seperti `10^12`, bilangan negatif, teks, dan
nilai kosong semuanya ditolak) — pengaman anti pembebanan CPU.

Dua tes terakhir kelompok ini menguji **pembatalan**, karena pada tier 1.700.000 tombol
Batal bukan sekadar kenyamanan: tanpa itu seluruh inti CPU tetap terpakai puluhan detik.

| Tes | Yang dibuktikan |
|---|---|
| `client_gone_detects_disconnect` | `client_gone` benar-benar membedakan koneksi yang masih hidup dari yang sudah ditutup klien, dan tidak memakan data yang masih antre |
| `run_engine_cancel_kills_process` | proses mesin yang sedang menghitung 400.000 simulasi berhenti < 5 detik setelah pembatalan diminta, dan tidak menghasilkan JSON utuh |

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
Ran 29 tests in 1.093s
OK
```

## Paralelisasi: output harus tidak berubah (4 tes)

Mesin menjalankan simulasi Monte-Carlo dengan beberapa thread sekaligus
(`DOMINO_THREADS`, bawaan semua inti logis). Satu hal yang tidak boleh terjadi adalah
jumlah thread mengubah hasil: pembagian blok kerja memakai snapshot stream bilangan
acak yang sama, sehingga urutan undian tiap simulasi tetap identik.

Jalankan `python tools/test_engine_parallel.py`:

| Tes | Yang dibuktikan |
|---|---|
| `parallel_equals_sequential` | output 1 thread **sama persis** dengan 2 dan 8 thread pada empat skenario (4 pemain, adversarial, 2 pemain, batas 2000 sim) |
| `default_threads_matches_sequential` | mode bawaan (semua inti) sama dengan mode sekuensial |
| `threads_zero_or_negative_means_sequential` | `DOMINO_THREADS=0` dan angka negatif tidak membuat mesin gagal, dan tetap sekuensial |
| `empty_unknown_pool_does_not_crash` | permintaan dengan pool kartu tak diketahui **kosong** (2 pemain x 14 kartu) tidak lagi mematikan proses |

Ditambah suite beban penuh (dijalankan dengan `DOMINO_SLOW_TESTS=1`, ≈1 menit) untuk tier
1.700.000 simulasi — beban maksimum yang ditawarkan aplikasi:

| Tes | Yang dibuktikan |
|---|---|
| `test_no_crash_and_ok` | mesin tidak jatuh dan tidak memangkas `numSims` pada beban penuh |
| `test_counts_and_conservation_at_full_load` | `wins + losses == numSims`, rincian kemenangan konsisten, konservasi kartu terjaga, dan lebar interval < 0,2 poin (janji ±0,1%) |
| `test_rankScore_sorted` | urutan peringkat tetap benar pada beban penuh |
| `test_full_load_parallel_equals_sequential` | output 1 thread, 4 thread, dan 12 thread **sama persis** pada 1,7 juta simulasi |

Hanya dua jalur pembatalan yang diuji di suite ini (level soket): pembatalan yang benar
saat pengguna menekan Batal juga sudah diverifikasi dari sisi antarmuka (lihat akhir bab
ini). Bukti nyata dari jalur browser: log server mencatat `[engine] dibatalkan: klien
menutup koneksi`, dan tidak ada satu pun proses `domino_engine` yang tertinggal.

Dua tes terakhir adalah pengaman regresi untuk cacat nyata: `shuffle` pada vector kosong
dulu memakai indeks `SIZE_MAX` lalu `nextInt(0)` (modulo nol) — proses mati dengan
`0xC0000094`/`0xC0000005`.

## Verifikasi identik terhadap build sebelumnya

Perubahan pada jalur perhitungan tidak boleh dinilai hanya dari "masih jalan".
`tools/audit_golden.py` membandingkan keluaran mesin **byte-per-byte**:

```bash
python tools/build_baseline.py                       # bangun mesin dari git HEAD + rekam golden
python tools/audit_golden.py verify "$TEMP/domino_audit_head"
```

Sembilan skenario diuji: 2/3/4 pemain, mode adversarial, cangkul mati, kartu pertama,
atribusi `playedBy`, 5000 simulasi (jalur paralel), batas 2000 simulasi, dan pool kartu
kosong. Semuanya harus melaporkan `IDENTIK`. Skrip mencatat juga bila mesin lama
**crash** pada suatu skenario, lalu memeriksa bahwa crash itu sudah hilang.

## Mengukur kecepatan

```bash
python tools/bench_engine.py     # mesin HEAD vs optimasi 1 thread vs optimasi paralel
```

Contoh keluaran di mesin uji pada beban 50.000 simulasi x jumlah kandidat langkah
(AMD Ryzen 5 5625U — **6 inti fisik / 12 utas logis**; "12 thread" di bawah berarti 12 utas):

| Versi | Waktu | Laju | Relatif |
|---|---|---|---|
| build HEAD | 2,62 s | 57.344 sim/detik | 1,00x |
| optimasi 1 thread | 1,03 s | 146.042 sim/detik | 2,55x |
| optimasi paralel (12 thread) | 0,20 s | 770.762 sim/detik | 13,44x |

### Beban penuh (tier 1.700.000) yang terukur

Tier tertinggi bukan sekadar angka di dokumen; ia diukur, dan invariannya diperiksa pada
skala itu. Semua angka di bawah berasal dari mesin uji di atas, 4 pemain, cangkul aktif,
7 kandidat langkah (papan kosong, 7 kartu di tangan):

| Yang diukur | Hasil | Arti |
|---|---|---|
| Waktu satu analisis penuh | **22,0 s** (11,9 juta simulasi-langkah) | jauh di bawah batas 300 detik, jadi tidak ada hasil yang terpotong |
| Laju | **602.081 simulasi-langkah/detik** (12 utas) | "1,7 juta simulasi" per kartu selesai dalam ~3 detik |
| Efisiensi paralel | **5,23x** pada 12 utas = **87,2%** dari 6 inti fisik (6 utas memberi 3,79x) | sisa ~13% adalah bagian yang memang sekuensial (perakitan hasil, simulasi sisa kartu) |
| Hasil 1 vs 6 vs 12 utas | **identik byte-per-byte** | jumlah utas tidak pernah mengubah angka |
| Dua run beban penuh | **identik byte-per-byte** | deterministik sampai skala maksimum |
| Setengah-lebar interval terlebar | **0,0752 poin** (janji: ≤ 0,1) | klaim ±0,1% pada tier ini terbukti, bukan perkiraan |
| Konservasi | `wins + losses == 1.700.000` dan `conserved: true` pada semua 7 langkah | tidak ada kartu atau gim yang hilang karena bebannya besar |

Beban besar juga diuji dari sisi yang paling mudah dilupakan: **apakah aplikasinya masih
enak dipakai selagi mesin bekerja?** Selama run 22 detik yang memakai seluruh 12 utas,
antarmuka diukur langsung: **59 frame/detik** (frame terburuk 30 ms) dan satu interaksi
nyata (mengganti jumlah pemain, termasuk menggambar ulang) selesai dalam **18 ms**.
Server tetap melayani endpoint ringan seperti `/api/meta` tanpa masuk ke antrean mesin,
karena endpoint itu memang tidak memanggil mesin. Yang berat tetap dibatasi: `numSims`
ditangani berurutan (`DOMINO_MAX_ENGINE`, bawaan 1) dan permintaan yang menunggu lebih dari
60 detik dijawab 503, bukan menggantung selamanya.

Terakhir, jalur yang benar-benar dipakai pengguna: memilih tier 1.700.000 memunculkan
peringatan (dan peringatan itu muncul kembali setiap kali pengguna menaikkan tier dari yang
lebih ringan), analisis berjalan dengan indikator waktu, tombol Batal mematikan proses
dalam ~0,4 detik, dan hasilnya tampil: **7 langkah, interval ±0,03 poin, selesai 15,4 detik**
dari perkiraan yang ditampilkan (~19 detik) — perkiraan yang sengaja dibuat sedikit
pesimistis.

## Uji antarmuka tanpa kepala (6 tes)

Peramban sungguhan tapi tanpa jendela (Playwright) menjalankan aplikasi yang utuh — server
Python, `web/`, dan mesin C++ — supaya perilaku yang hidup di JavaScript tidak lagi hanya
diuji manual:

```bash
pip install playwright
python tools/test_ui_heavy.py
```

Paket `playwright` memakai peramban yang sudah terpasang di komputer (Edge/Chrome), jadi
tidak perlu mengunduh Chromium; bila tidak ada peramban sama sekali, uji ini **dilewati**
(skip), bukan gagal. Di CI, Chromium dipasang eksplisit pada pekerjaan `ui-headless`.

| Tes | Yang dibuktikan |
|---|---|
| `test_heavy_option_exists_and_warns_before_use` | opsi 1.700.000 ada; memilihnya memunculkan dialog berisi jumlah simulasi, perkiraan waktu, dan cara membatalkan; banner serta label sekali-jalan menyala; mode Live padam |
| `test_declining_warning_reverts_to_previous_tier` | menolak dialog mengembalikan tier sebelumnya tanpa mengubah mode Live; menyetujui dialog tetap membuka tier berat |
| `test_button_label_always_matches_tier` | label tombol selalu cocok dengan tier pada kenaikan/penurunan berturut-turut, dan peringatan muncul lagi di setiap kenaikan |
| `test_manual_pause_survives_tier_change` | jeda Live yang dilakukan pengguna sendiri tidak dinyalakan kembali saat tier diturunkan |
| `test_heavy_tier_still_warned_after_reload` | sesi tersimpan pada tier berat tetap menampilkan banner setelah halaman dimuat ulang, tanpa dialog yang menghadang |
| `test_cancel_button_stops_engine_process` | menekan Batal: proses `domino_engine` benar-benar hilang (**~0,4 detik** pada mesin uji), server mencatat `[engine] dibatalkan`, label pulih ke mode sekali-jalan, dan tidak ada hasil yang tampil |

Tes terakhir berjalan dari posisi dengan 5 kandidat langkah (≈10–20 detik pada 1,7 juta
simulasi) dan memeriksa bahwa analisis **masih berjalan** tepat sebelum Batal ditekan.
Tanpa pemeriksaan itu, uji hanya akan membuktikan analisis yang kebetulan sudah selesai.
Dengan uji ini, jalur soket yang sesungguhnya (klien menutup koneksi → server mematikan
mesin) ikut terjaga, bukan hanya fungsi internalnya lewat uji unit.

### Uji ini bergigi — dan itu diperiksa

Uji yang selalu hijau tidak membuktikan apa pun, jadi tiap klaim utama diuji dengan
**mutasi**: satu aturan dicabut dari kode, dan uji harus gagal dengan gejala yang tepat.

| Mutasi (cacat yang disuntikkan) | Gejala yang tertangkap |
|---|---|
| label tidak lagi mengikuti tier | `label harus menandai analisis sekali-jalan, dapat: '▶️ Analisis Live'` |
| penolakan dialog tidak mengembalikan tier | `'1700000' != '50000'` |
| tier berat tidak lagi mematikan Live | `label harus menandai analisis sekali-jalan, dapat: '⏸ Jeda Live'` |
| server mengabaikan koneksi yang ditutup klien | `proses mesin masih hidup > 8 detik setelah Batal` |

Setelah kode dipulihkan, keenam uji kembali lulus.

## Integrasi berkelanjutan (CI)

Setiap kali perubahan dikirim ke cabang `main`, empat pekerjaan berjalan di GitHub Actions:

| Pekerjaan | Sistem | Yang dijalankan |
|---|---|---|
| `engine-linux` | Ubuntu, g++ | bangun mesin, selftest, uji server |
| `engine-windows` | Windows, MSVC | bangun mesin, selftest, uji server |
| `server-linux` | Ubuntu, tanpa mesin | uji server saja (tes yang butuh mesin dilewati dengan rapi) |
| `ui-headless` | Ubuntu + Chromium | uji antarmuka tanpa kepala untuk tier 1,7 juta |

Empat pekerjaan ini menjawab empat pertanyaan berbeda:

1. **Apakah mesin masih bisa dibangun oleh dua kompiler berbeda?** Ini menangkap
   penggunaan fitur bahasa yang tidak portabel.
2. **Apakah invarian mesin masih berlaku?** Ini yang menjalankan sebelas pemeriksaan.
3. **Apakah server tetap benar tanpa mesin?** Ini memastikan validasi, normalisasi, dan
   kontrak status HTTP tidak bergantung pada biner yang ada.
4. **Apakah alur tier berat tetap benar dari sisi pengguna?** Ini menjalankan peramban
   sungguhan yang menekan tombol-tombolnya: peringatan, penolakan, label, dan Batal yang
   mematikan proses mesin.

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
- **Sebagian interaksi pengguna kini dijaga otomatis, sebagian belum.** Alur tier
  1,7 juta (peringatan, penolakan, label, Batal yang mematikan mesin) dijaga uji peramban
  tanpa kepala; modal, masukan cepat, dan alur Undo masih diuji manual.
- **Belum ada tolok ukur kinerja di CI.** Waktu tunggu analisis bergantung pada perangkat;
  angka waktu di Bagian IV adalah perkiraan, bukan hasil pengukuran otomatis.
- **Akurasi heuristik tidak diverifikasi terhadap permainan manusia.** Mesin memverifikasi
  konsistensi internal dan konservasi, bukan "apakah langkah yang disarankan benar-benar
  menang di meja nyata".
- **Pemeriksaan mandiri memakai pembangkit acak bersemai**, jadi hasilnya dapat diulang,
  tetapi cakupan skenarionya tetap terbatas pada skenario yang ditulis di kode.

Bila Anda ingin menambah pengujian, sasaran yang paling berharga saat ini adalah uji
otomatis untuk tata letak papan dan uji interaksi dasar untuk alur kartu → PASS → atribusi
→ Undo (fondasi peramban tanpa kepala untuk itu sudah ada di `tools/test_ui_heavy.py`).
