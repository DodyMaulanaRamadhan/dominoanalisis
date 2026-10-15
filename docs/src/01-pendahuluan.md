# Bagian I — Pengenalan

Selamat datang. Buku ini menjelaskan **Domino Analyzer Pro** dari dua sisi sekaligus:
sebagai panduan pemakaian sehari-hari, dan sebagai penjelasan teknis isi mesinnya.
Tujuannya satu: setelah membaca, Anda bisa memakai aplikasi ini dengan percaya diri,
tahu **mengapa** angka di layar muncul, dan tahu **apa yang boleh dan tidak boleh**
dipercaya dari angka tersebut.

Buku ini ditulis untuk pembaca yang tidak harus punya latar belakang pemrograman.
Istilah teknis selalu dijelaskan saat pertama muncul, dan semua istilah penting
dikumpulkan kembali di glosarium pada bagian lampiran.

## Apa itu Domino Analyzer Pro

Domino Analyzer Pro adalah alat bantu keputusan untuk permainan **domino 28 kartu**
(kartu dengan sisi angka 0 sampai 6, biasa disebut "klik" atau "gaple" di Indonesia).
Anda memasukkan kartu yang ada di tangan Anda, menandai kartu yang sudah terlihat di
meja, mencatat saat lawan tidak bisa jalan (PASS), lalu aplikasi menghitung kemungkinan
menang untuk setiap langkah yang mungkin Anda ambil.

Perhitungannya bukan tebakan dan bukan kumpulan tips. Aplikasi ini benar-benar
memainkan ribuan gim domino di dalam komputer: setiap gim dibagikan ulang secara acak
dengan batasan yang Anda berikan, dimainkan sampai selesai oleh tiga gaya lawan yang
berbeda, dan hasil akhirnya dihitung. Setelah semua percobaan selesai, aplikasi
menyusun rekomendasi urutan langkah terbaik untuk Anda.

Komponen utamanya tiga:

| Lapisan | Berkas | Peran |
|---|---|---|
| Antarmuka web | `web/index.html`, `web/app.js`, `web/styles.css`, `web/sw.js` | papan, tangan, pencatatan lawan, tampilan hasil |
| Server API | `server/domino_server.py` | menerima permintaan, menormalkan dan memvalidasi, memanggil mesin |
| Mesin analisis | `engine/domino_engine.cpp` → `bin/domino_engine` | simulasi Monte-Carlo, penilaian langkah, peringkat |

Semuanya berjalan lokal di komputer Anda. Tidak ada data permainan yang dikirim ke
layanan pihak ketiga; satu-satunya lalu lintas jaringan adalah antara peramban Anda
dan server lokal di `127.0.0.1:2024`.

## Masalah yang dipecahkan

Domino terlihat sederhana: tujuh kartu di tangan, dua ujung meja, siapa cepat habis dia
menang. Kenyataannya ada tiga sumber kebingungan yang membuat pemain kuat sekalipun
sering salah langkah.

**Pertama, informasi tersembunyi terlalu banyak.** Ada 28 kartu, dan Anda hanya tahu
tujuh di antaranya. Setiap keputusan sebenarnya adalah perjudian terukur: peluang kartu
tertentu ada di tangan lawan. Manusia buruk dalam menimbang banyak peluang sekaligus,
terutama dengan batas waktu beberapa detik.

**Kedua, informasi tersedia tidak dicatat.** Setiap kali lawan menolak jalan (PASS),
mereka membocorkan sesuatu yang sangat berharga: angka di kedua ujung meja saat itu
**tidak ada** di tangan mereka. Satu PASS bisa menghapus belasan kemungkinan. Hampir
semua pemain membuang informasi ini karena tidak mungkin menghafalnya.

**Ketiga, hasil tipis tidak bisa dibedakan dari keberuntungan.** Dua langkah yang
hampir sama bagusnya akan menghasilkan win rate yang mirip. Tanpa alat ukur
ketidakpastian, pemain cenderung menganggap selisih satu-dua persen sebagai alasan
kuat, padahal itu hanya derau statistik.

Domino Analyzer Pro menyerang ketiga hal itu:
mencatat bukti (PASS dan atribusi kartu), menghitung peluang dengan simulasi berskala
besar, dan menampilkan ketidakpastian secara eksplisit dalam bentuk interval keyakinan.

## Fitur utama dalam satu halaman

**Mesin analisis.**
Simulasi Monte-Carlo untuk setiap kandidat langkah; tiga profil lawan AI (Blocker,
Hoarder, Dumper) yang dirotasi sehingga rekomendasi tidak terjebak pada satu gaya main;
mode **teliti** (adversarial) di mana lawan yang bermain tepat setelah Anda membalas
dengan permainan ketat tanpa derau; simulasi **cangkul**; konvensi meja yang bisa diatur
(aturan adu dan aturan seri); interval keyakinan Wilson 95%; peringkat tunggal
`rankScore` yang dihitung di mesin; serta hasil yang **deterministik** — seed yang sama
menghasilkan angka yang sama persis.

**Pelacakan lawan.**
PASS lawan menghapus angka dari kemungkinan kartu mereka; atribusi kartu memastikan satu
kartu milik satu lawan tertentu dan menghapusnya dari lawan lain; profil kekayaan angka
per lawan menaksir angka mana yang kemungkinan besar mereka kuasai; dan urutan giliran
ikut diperhitungkan dalam simulasi.

**Antarmuka.**
Papan bergaya ular yang mengecil otomatis agar semuanya terlihat tanpa menggulir;
siluet rekomendasi yang menempel di kepala atau kaki kartu pertama; mode LIVE yang
menganalisis ulang setiap kali informasi berubah; timeline undo yang konsisten; simpan
otomatis ke penyimpanan peramban; ekspor dan impor sesi; banner kualitas kartu; serta
kemampuan dipasang sebagai aplikasi (PWA) yang tetap membuka antarmuka saat offline.

## Cara memakai dalam 30 detik

Untuk pembaca yang ingin langsung mencoba:

```bash
python start.py
```

Perintah di atas membangun mesin C++ bila perlu, menjalankan pemeriksaan mandiri mesin,
lalu menyalakan server di port 2024. Buka `http://127.0.0.1:2024` di peramban.

Lalu di layar:

1. Pilih jumlah pemain, jumlah kartu per pemain, dan aturan meja di panel **Setup**.
2. Ketuk **+ Pilih Kartu Saya**, lalu isi tujuh kartu tangan Anda (bisa lewat ketikan
   cepat: dua angka lalu Enter).
3. Ketuk kartu di tangan untuk memainkannya. Bila kartu bisa masuk ke dua ujung, muncul
   pilihan ujung kiri atau kanan.
4. Saat giliran lawan: kalau dia bermain, ketuk kartunya di panel **Kartu Sisa** lalu
   pilih lawan yang memainkannya; kalau dia PASS, ketuk tombol **PASS / LEWAT** di kartu
   lawan tersebut.
5. Baca panel **Hasil Analisis**. Kartu peringkat #1 juga ditandai glow biru di tangan
   Anda dan siluet biru di papan.

Mode LIVE aktif sejak aplikasi dibuka, jadi hasil analisis langsung diperbarui setiap
kali Anda menambah informasi — tidak ada tombol "hitung" yang harus ditekan.

> Catatan penting: aplikasi tidak tahu kartu lawan. Yang ia lakukan adalah menghitung
> **peluang** berdasarkan informasi yang Anda berikan. Semakin rajin Anda mencatat PASS
> dan atribusi kartu, semakin tajam hasilnya.

## Cara membaca buku ini

Buku ini disusun sepuluh bagian, dari yang paling praktis sampai yang paling teknis.

| Bagian | Isi | Cocok dibaca oleh |
|---|---|---|
| I | Pengenalan, masalah, fitur, cara pakai cepat | semua pembaca |
| II | Dasar permainan domino dan istilah meja | pemain baru |
| III | Instalasi, menjalankan, konfigurasi, tunnel, PWA | yang memasang aplikasi |
| IV | Panduan antarmuka langkah demi langkah | pemakai harian |
| V | Cara membaca dan memercayai hasil analisis | pemakai serius |
| VI | Arsitektur dan isi mesin (algoritma, server, frontend) | pengembang |
| VII | Pengujian, pemeriksaan mandiri, dan CI | pengembang |
| VIII | Panduan strategi bermain | pemain yang ingin naik level |
| IX | Rujukan API lengkap dengan contoh | integrator/pengembang |
| X | Pemecahan masalah, FAQ, glosarium, lampiran | semua pembaca |

Bila Anda baru pertama kali memakai aplikasi ini, urutan yang disarankan adalah
Bagian II, III, IV, lalu VIII. Bila Anda penasaran dengan angka-angkanya, lanjutkan ke
Bagian V dan VI.

## Pernyataan jujur tentang batasan

Sebuah buku yang baik tidak menjual alatnya secara berlebihan. Berikut hal-hal yang
**tidak** bisa dilakukan aplikasi ini.

- **Aplikasi tidak mengintip kartu lawan.** Semua angka berasal dari simulasi dengan
  batasan yang Anda masukkan sendiri. Bila Anda salah mencatat, hasilnya salah.
- **Hasil simulasi bukan kepastian.** Win rate 62% berarti: dalam model simulasi, Anda
  menang pada sekitar 62 dari 100 gim. Sisa 38% adalah kemungkinan kalah.
- **Kualitas rekomendasi bergantung pada jumlah simulasi.** 200 simulasi per kartu
  memberi gambaran kasar; 2000 sampai 5000 memberi gambaran halus dengan waktu tunggu
  lebih lama.
- **Aplikasi tidak menggantikan keputusan.** Ia menampilkan peluang; keputusan tetap
  milik Anda, dan faktor meja (gaya main lawan nyata, kesepakatan lokal, kebiasaan
  kelompok) tidak seluruhnya bisa dimodelkan.
- **Tidak ada basis data permainan.** Semua data sesi disimpan di peramban Anda sendiri.

Bagian VI dan VII menjelaskan dengan tepat batasan mana yang berasal dari desain dan
mana yang berasal dari sifat statistik Monte-Carlo.
