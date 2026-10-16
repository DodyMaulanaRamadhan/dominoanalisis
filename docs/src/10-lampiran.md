# Bagian X — Pemecahan Masalah & Lampiran

## Pemecahan masalah

Masalah dikelompokkan menurut gejala yang Anda lihat. Kolom terakhir adalah perbaikan
yang paling sering benar.

### Saat menjalankan

| Gejala | Kemungkinan penyebab | Perbaikan |
|---|---|---|
| `TIDAK ADA compiler yang bisa dipakai (MSVC/g++/clang++)` | tidak ada compiler C++ terpasang | pasang Visual Studio Build Tools (komponen C++) atau MinGW/`g++` |
| `[start] build engine gagal.` | kesalahan kompilasi atau compiler tidak lengkap | jalankan `python tools/build_engine.py --force` untuk melihat pesan kesalahan penuh |
| `[selftest] ... GAGAL` | mesin terpasang tetapi tidak konsisten (jarang) | bangun ulang dengan `--force`; bila tetap gagal, laporkan keluaran selftest |
| `[start] Port 2024 sudah dipakai — server lain mungkin berjalan.` | sudah ada server domino berjalan | tutup jendela server lama, atau jalankan server manual dengan `DOMINO_PORT` lain |
| Server hidup tetapi halaman kosong | berkas belum termuat atau tembolok lama | muat ulang dengan Ctrl+F5, atau naikkan nama tembolok di `web/sw.js` |
| `Address already in use` saat menjalankan server manual | port sedang dipakai proses lain | pilih port lain: `DOMINO_PORT=8080 python server/domino_server.py` |

### Saat memakai

| Gejala | Kemungkinan penyebab | Perbaikan |
|---|---|---|
| "Tidak bisa menghubungi server" | server mati atau port berbeda | jalankan `python start.py` lagi |
| Analisis menjawab 503 | biner mesin belum dibangun | `python tools/build_engine.py --force` |
| Analisis menjawab 401 | `APP_TOKEN` aktif, antarmuka tidak mengirim token | kosongkan `APP_TOKEN` atau lindungi di lapisan tunnel |
| Bilah kemajuan berhenti di 30% | analisis sangat berat atau komputer sibuk | tunggu, turunkan jumlah simulasi, atau tekan tombol untuk membatalkan |
| Perubahan `web/` tidak muncul | service worker menyajikan versi tembolok | ubah nama tembolok di `web/sw.js`, lalu muat ulang paksa |
| Papan meluber dan perlu digulir | isi papan melebihi batas pengecilan minimum | ini perilaku cadangan yang disengaja; papan tetap bisa digulir agar tidak ada kartu hilang |
| Siluet rekomendasi menghilang tiba-tiba | kartu rekomendasi sudah tidak bisa dimainkan lagi pada keadaan papan sekarang | jalankan analisis ulang (mode hidup biasanya sudah melakukannya) |
| Papan terlihat goyang saat jendela diubah | penataan sedang berlangsung | tunggu sekitar 150 milidetik; penataan ulang ditunda agar tidak berkedip |
| Angka peluang berbeda padahal data sama | jumlah simulasi berbeda, atau pengaturan meja berubah | samakan `numSims` dan pengaturan; hasilnya deterministik pada konfigurasi sama |

## Pertanyaan yang sering diajukan

**Apakah aplikasi ini mengintip kartu lawan?**
Tidak. Aplikasi hanya memakai informasi yang Anda masukkan. Ia menghitung peluang, bukan
mengetahui kartu.

**Mengapa tombol analisis sudah menyala saat aplikasi dibuka?**
Karena mode hidup aktif sejak awal. Teks pada tombol itu adalah perintah untuk menjeda,
bukan untuk memulai.

**Apakah saya harus menekan tombol analisis setiap kali?**
Tidak. Setiap perubahan informasi memicu analisis ulang otomatis. Tombolnya hanya untuk
menjeda.

**Kenapa rekomendasinya jadi #2 padahal peluang menangnya lebih tinggi?**
Itulah gunanya rankScore: langkah yang peluangnya nyaris sama bisa dibedakan oleh jerat,
kunci, blok terjamin, dan risiko. Bagian V memuat contoh nyata dengan angka lengkap.

**Berapa jumlah simulasi yang sebaiknya dipakai?**
2000 untuk pemakaian sehari-hari; 5000 bila Anda ingin memisahkan selisih tipis dan tidak
keberatan menunggu.

**Bisakah saya bermain 2 pemain?**
Bisa. Pilih 2 pemain; jumlah kartu maksimum menjadi 14 per pemain dan sisanya menjadi
cangkul (kecuali Anda mematikannya).

**Apa arti "tereliminasi 12%" di panel lawan?**
Berapa persen kemungkinan kartu lawan itu sudah berhasil dipersempit oleh data PASS dan
atribusi yang Anda catat.

**Apakah data saya dikirim ke internet?**
Tidak. Server hanya berjalan di komputer Anda. Berkas sesi disimpan di penyimpanan lokal
peramban.

**Bisa dipakai di ponsel tanpa memasang apa pun?**
Bisa, asalkan ponsel dapat menjangkau server di komputer Anda (misalnya lewat alamat IP
jaringan lokal). Untuk akses dari luar jaringan, lihat bagian tunnel di Bagian III.

**Bagaimana kalau saya salah mencatat PASS?**
Tekan **Undo** satu kali; PASS terakhir dibatalkan bersama eliminasi angkanya. Perhatikan
tombol Undo di kartu lawan membatalkan PASS lawan itu, sedangkan tombol Undo utama
membatalkan aksi terakhir secara umum.

**Mengapa ada kartu yang ditandai "BALAK"?**
Karena balak bernilai dua kali angkanya dan sering menjadi beban bila permainan berakhir
dengan adu. Penanda itu membantu Anda mendahulukan pembuangannya.

**Apakah hasilnya bisa saya simpan untuk dianalisis ulang?**
Bisa. Tekan **Export** untuk mengunduh berkas JSON sesi, dan **Import** untuk memuatnya
kembali di lain waktu.

**Apa arti "konservasi" yang muncul di keluaran mesin?**
Penanda bahwa jumlah kartu tetap 28 selama simulasi: tidak ada kartu yang muncul atau
hilang. Bila bernilai salah, hasil simulasi itu tidak layak dipercaya.

## Glosarium

| Istilah | Arti |
|---|---|
| **Adu** | akhir permainan karena meja macet; pemenang ditentukan nilai mata |
| **Atribusi** | menandai kartu di papan sebagai milik lawan tertentu |
| **Balak** | kartu dengan angka kembar, misalnya `5-5` |
| **Boneyard** | kartu sisa/cangkul yang belum dibagikan |
| **Cangkul** | menyambar kartu sisa setelah tidak bisa jalan |
| **Constraint-aware dealing** | pembagian kartu dalam simulasi yang menghormati bukti PASS dan atribusi |
| **Deterministik** | masukan sama menghasilkan keluaran sama, berkat seed tetap |
| **Fallback** | kejadian ketika batasan simulasi harus dilepas karena kuota kartu mustahil dipenuhi |
| **Ghost / siluet** | gambar garis putus-putus di papan yang menunjukkan tempat rekomendasi |
| **Interval keyakinan (Wilson)** | rentang tempat nilai sebenarnya kemungkinan besar berada |
| **Invarian** | sifat yang harus selalu benar; diperiksa oleh selftest |
| **Jerat (trap)** | menyisakan angka dominan di ujung agar lawan terpaksa membukanya |
| **Klik** | sebutan lain untuk kartu domino |
| **Kunci (block)** | ujung yang hanya bisa diakses Anda |
| **Mata** | nilai satu sisi kartu |
| **Mode teliti (adversarial)** | simulasi dengan lawan yang bermain ketat tanpa derau |
| **Monte-Carlo** | metode menaksir peluang dengan menjalankan banyak percobaan acak |
| **Nilai mata** | jumlah kedua angka sebuah kartu atau tangan |
| **PASS** | tidak bisa jalan; menjadi bukti bahwa angka ujung tidak dipegang |
| **Peta angka** | panel yang menunjukkan sebaran kartu per angka 0-6 |
| **rankScore** | nilai peringkat gabungan yang dihitung mesin |
| **Siku** | kartu berdiri di tikungan susunan ular |
| **Sisa mati** | kartu sisa yang tidak pernah masuk permainan |
| **Ujung** | angka bebas di kiri atau kanan rantai meja |
| **Ular (boustrophedon)** | susunan baris bergantian arah seperti ular |
| **Win rate** | peluang menang hasil simulasi untuk sebuah langkah |

## Lampiran A — seluruh 28 kartu

| Kartu | Nilai mata | Kartu | Nilai mata | Kartu | Nilai mata | Kartu | Nilai mata |
|---|---|---|---|---|---|---|---|
| 0-0 | 0 | 1-2 | 3 | 2-4 | 6 | 4-5 | 9 |
| 0-1 | 1 | 1-3 | 4 | 2-5 | 7 | 4-6 | 10 |
| 0-2 | 2 | 1-4 | 5 | 2-6 | 8 | 5-5 | 10 |
| 0-3 | 3 | 1-5 | 6 | 3-3 | 6 | 5-6 | 11 |
| 0-4 | 4 | 1-6 | 7 | 3-4 | 7 | 6-6 | 12 |
| 0-5 | 5 | 2-2 | 4 | 3-5 | 8 | — | — |
| 0-6 | 6 | 2-3 | 5 | 3-6 | 9 | — | — |
| 1-1 | 2 | — | — | 4-4 | 8 | — | — |

Balak: `0-0` (0), `1-1` (2), `2-2` (4), `3-3` (6), `4-4` (8), `5-5` (10), `6-6` (12).
Kartu bernilai tertinggi adalah `6-6` (12); kartu bernilai 0 hanyalah `0-0`.

## Lampiran B — pembagian kartu dan sisa

| Pemain | Kartu per pemain | Dibagikan | Sisa/cangkul | Kartu tersembunyi per lawan (perkiraan) |
|---|---|---|---|---|
| 2 | 7 | 14 | 14 | 7 |
| 2 | 10 | 20 | 8 | 10 |
| 3 | 7 | 21 | 7 | 7 |
| 3 | 9 | 27 | 1 | 9 |
| 4 | 5 | 20 | 8 | 5 |
| 4 | 7 | 28 | 0 | 7 |

"Kartu tersembunyi per lawan" adalah jumlah kartu yang tidak Anda lihat di tangan satu
lawan; angka inilah yang dipakai mesin untuk menghitung kuota pembagian.

## Lampiran C — rumus dan bobot penting

**rankScore** (dihitung mesin, dipakai antarmuka untuk mengurutkan):

```text
rankScore = winRate x 100 + domSupportScore x 0,6 + trapScore x 0,8 + blockScore x 0,7
          - selfTrapScore x 0,5 - riskScore x 0,5 + deadlockWinRate x 20
          + |guaranteedBlocks| x 8 + avgOppPasses x 3 + safetyRatio x 30 (kartu pertama)
```

**Interval keyakinan Wilson 95%** (rumus yang dipakai setelah perbaikan):

```text
pusat  = (p + z²/2n) / (1 + z²/n)
margin = z x akar( p(1-p)/n + z²/4n² ) / (1 + z²/n)      z = 1,96
bawah  = max(0, pusat - margin)      atas = min(1, pusat + margin)
```

**Skor risiko:** jumlah lima frekuensi kartu teratas yang dimainkan lawan pada gim yang
Anda kalah, masing-masing dikali 10.

**Keamanan kartu pertama:** jumlah kartu sisa di tangan yang masih bisa dimainkan setelah
kandidat pertama, dibagi jumlah kartu sisa.

**Konservasi:** `kartu di semua tangan + kartu di papan = kartu saat pembagian`.

## Lampiran D — catatan versi dan perbaikan

| Tanggal/periode | Perubahan |
|---|---|
| v1 | analisis domino dasar dalam satu program |
| v2 | pemisahan menjadi mesin C++ + server Python; simulasi, peta angka, konvensi meja |
| v3 | atribusi kartu per lawan, tiga profil lawan, mode teliti, Wilson, rankScore, PWA |
| v3.1 | mode cangkul dan kartu sisa mati, kisi kandidat kartu per lawan, masukan angka |
| v3.2 | mode hidup aktif sejak pembukaan, masukan cepat, indikator status di judul |
| v3.3 | siluet rekomendasi, glow biru kartu pilihan, perbaikan pilihan ujung untuk kartu lawan |
| v3.6 | papan bergaya ular, pengecilan otomatis, pemusatan kartu pertama |
| audit keamanan | perbaikan XSS pada pesan galat, proteksi CSRF/DoS, penanganan badan rusak, kode status HTTP yang benar |
| regresi | perbaikan pemberian kemenangan akhir permainan yang salah |
| **perbaikan rumus interval** | **rumus Wilson dikoreksi: setiap interval keyakinan sebelumnya selalu 0-100% sehingga tidak berguna; kini benar dan menyempit sesuai jumlah simulasi, dengan pemeriksaan mandiri baru untuk menjaganya** |

Perbaikan terakhir itu ditemukan justru saat dokumentasi ini disusun, karena contoh
keluaran nyata diperiksa satu per satu sebelum ditulis ke buku. Kisah lengkapnya ada di
Bagian VII.

## Lampiran E — membangun ulang dokumen ini

Buku yang sedang Anda baca dihasilkan oleh dua skrip, bukan ditulis dua kali:

```bash
pip install fpdf2 python-docx        # dependensi build dokumen
python tools/build_docs.py           # Markdown gabungan + PDF + DOCX
python tools/build_deck.py           # presentasi PPTX
```

| Berkas | Peran |
|---|---|
| `docs/src/*.md` | sumber isi buku (sepuluh bagian) |
| `docs/Domino-Analyzer-Pro-Dokumentasi.md` | buku gabungan dalam Markdown |
| `docs/Domino-Analyzer-Pro-Dokumentasi.pdf` | buku cetak dengan daftar isi bernomor halaman dan diagram vektor |
| `docs/Domino-Analyzer-Pro-Dokumentasi.docx` | versi yang bisa diedit |
| `docs/Domino-Analyzer-Pro-Presentasi.pptx` | presentasi ringkas |

Pembangun PDF memeriksa lebih dulu apakah font yang tersedia bisa menampilkan seluruh
karakter yang dipakai; karakter yang tidak didukung akan diganti padanannya, dan bila
masih ada yang tidak bisa ditampilkan, hal itu dilaporkan alih-alih dibiarkan menjadi
kotak kosong di dokumen. Perintah pemeriksaan saja:

```bash
python tools/build_docs.py --check-fonts
```

## Lisensi dan kontribusi

Proyek ini **belum menyertakan berkas lisensi**. Secara hukum, tanpa lisensi eksplisit
hak cipta tetap berada pada penulisnya dan penggunaan ulang tidak otomatis diizinkan.
Bila Anda ingin membagikan atau memakai ulang proyek ini secara luas, langkah yang
disarankan adalah menambahkan berkas `LICENSE` (misalnya MIT untuk pemakaian bebas, atau
GPL bila Anda ingin turunannya tetap terbuka).

Bagi yang ingin berkontribusi, urutan yang paling berguna untuk diperiksa sebelum
mengirim perubahan:

1. `python tools/selftest.py` — sebelas pemeriksaan mesin harus lulus;
2. `python tools/test_server.py` — 29 uji server harus lulus;
3. `python tools/test_engine_parallel.py` — 8 uji paralel/determinisme harus lulus
   (tambahkan `DOMINO_SLOW_TESTS=1` untuk ikut menguji beban penuh 1,7 juta simulasi);
4. `python tools/test_ui_heavy.py` — 6 uji antarmuka tanpa kepala untuk tier 1,7 juta harus
   lulus (perlu `pip install playwright`; dilewati bila tidak ada peramban);
5. `python tools/build_engine.py --force` — pastikan mesin masih bisa dibangun dari nol.

Perubahan pada tata letak papan sebaiknya disertai pemeriksaan manual pada lebar ponsel dan
desktop, karena tata letak belum punya uji otomatis. Perubahan pada alur tier 1,7 juta
(peringatan, label tombol, pembatalan) sudah punya pengaman otomatis — jalankan
`tools/test_ui_heavy.py`.

## Tentang penulis

**Dody Maulana Ramadhan**

Aplikasi **Domino Analyzer Pro** beserta dokumentasi ini dibuat oleh Dody Maulana
Ramadhan: mesin analisis Monte-Carlo dalam C++20, server API Python, antarmuka web PWA,
serta seluruh perkakas pengujian, integrasi berkelanjutan, dan buku panduan ini.

Buku ini disusun sebagai penjelasan lengkap sekaligus panduan pemakaian, dengan satu
prinsip yang dipegang dari halaman pertama sampai terakhir: **setiap angka yang ditulis di
sini harus bisa dilacak kembali ke kode yang menghasilkannya.** Contoh keluaran di Bagian V
dan Bagian IX diambil dari eksekusi mesin yang sesungguhnya, bukan dari ilustrasi.

## Penutup

Domino adalah permainan informasi yang tidak lengkap. Kita tidak pernah tahu tujuh kartu
lawan, dan justru di situlah letak keseruannya. Yang bisa dilakukan pemain yang disiplin
adalah memastikan **informasi yang tersedia tidak terbuang**: setiap PASS dicatat, setiap
kartu lawan diatribusikan, dan setiap keputusan diambil dengan kesadaran penuh atas
peluang dan ketidakpastiannya.

Alat ini dibuat untuk tujuan itu — bukan untuk menggantikan kepekaan seorang pemain,
melainkan untuk menutup celah yang paling sulit ditutup oleh manusia: menghitung.
Selamat bermain, dan semoga papan Anda selalu memberi jalan.
