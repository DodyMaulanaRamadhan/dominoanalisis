# Bagian V — Membaca & Memercayai Hasil

Inilah bagian yang membedakan pemakai biasa dari pemakai yang benar-benar diuntungkan
aplikasi ini. Angka yang tampil di panel hasil bukan satu nilai tunggal, melainkan lima
jenis informasi berbeda yang harus dibaca bersama-sama: peringkat, peluang, selang
keyakinan, alasan strategis, dan peringatan.

## Urutan kartu ditentukan mesin, bukan tampilan

Setiap kandidat langkah diberi satu nilai bernama **rankScore** oleh mesin, dan daftar
kartu dari mesin sudah dalam urutan menurun berdasarkan nilai itu. Tampilan menambahkan
satu penyaringan di atasnya: kartu dengan peluang menang 50% atau lebih dipindahkan ke
kelompok **aman** di atas, lalu di dalam tiap kelompok urutannya tetap menurut rankScore.

Praktisnya:

1. Semua kartu dengan win rate 50% atau lebih tampil lebih dulu, diurutkan menurun
   berdasarkan rankScore.
2. Setelah itu barulah kartu dengan win rate di bawah 50%, juga diurutkan menurun.

Penyaringan ini tidak mengubah peringkat #1 kecuali pada keadaan yang jarang (kartu
dengan rankScore tinggi tetapi win rate di bawah 50%). Yang penting bagi Anda: **urutan
tampilan adalah rekomendasi akhir aplikasi**, dan angka rankScore ditampilkan agar Anda
bisa melihat dasar keputusannya.

```text
rankScore = winRate x 100
          + domSupportScore x 0,6
          + trapScore x 0,8
          + blockScore x 0,7
          - selfTrapScore x 0,5
          - riskScore x 0,5
          + deadlockWinRate x 20
          + jumlah blok terjamin x 8
          + rata-rata lawan PASS x 3
          + safetyRatio x 30   (hanya pada mode kartu pertama)
```

Rumus ini bukan skor rahasia; ia empat baris kode di dalam mesin. Yang perlu Anda pahami
adalah **bobotnya**, karena bobot itulah yang menjelaskan mengapa suatu langkah menang
peringkat.

| Komponen | Bobot | Artinya |
|---|---|---|
| Peluang menang | 100 per 1,0 | dasar utama; 1% peluang sama dengan 1 poin |
| Dukungan dominasi | 0,6 | ujung cocok dengan angka yang Anda kuasai |
| Jerat | 0,8 | menyisakan angka dominan dengan kartu masih di luar |
| Kunci | 0,7 | ujung yang tidak bisa diakses lawan |
| Jebakan diri sendiri | -0,5 | menyisakan ujung yang berbahaya bagi Anda |
| Risiko | -0,5 | kartu berbahaya yang sering muncul di simulasi kalah |
| Menang lewat adu | 20 per 1,0 | dorongan ke skenario adu |
| Blok terjamin | 8 per lawan | lawan yang **pasti** mati menurut data PASS |
| Lawan dipaksa PASS | 3 | berapa sering lawan lewat setelah langkah ini |

Perhatikan bahwa 1 poin rankScore dari peluang menang jauh lebih besar daripada dari
komponen mana pun. Mesin tidak membiarkan pertimbangan taktis mengalahkan peluang nyata;
komponen lain hanya berfungsi memisahkan langkah-langkah yang peluangnya berdekatan.

## Contoh nyata dengan angka asli

Berikut contoh yang benar-benar dihitung oleh mesin (mesin `domino-cpp/3.0.0`, seed
`20240922`, 500 simulasi per kandidat). Situasinya: 4 pemain, 7 kartu per pemain, semua
kartu dibagikan habis (tidak ada sisa).

**Yang diketahui mesin:**

```text
tangan saya : 6-6, 3-6, 2-3, 1-5, 4-4
di papan    : 0-3, 0-2, 1-2
milik siapa : 0-3 -> Lawan 1 ; 0-2 -> Lawan 2 ; 1-2 -> Lawan 1
ujung meja  : kiri 3, kanan 1
PASS tercatat: Lawan 1 lewat saat ujung 3 dan 1
giliran     : Lawan 1 bermain setelah saya
aturan      : adu banding mata terkecil, seri dihitung menang, cangkul aktif
```

**Hasilnya:**

| # | Kartu | Ujung baru | Peluang menang | Selang 95% | rankScore | Jerat | Jebakan diri | Lawan PASS |
|---|---|---|---|---|---|---|---|---|
| 1 | `3-6` ke kiri | 6 \| 1 | **69,2%** | 65,0 - 73,1% | **84,2** | 15 | 0 | 3,08 |
| 2 | `2-3` ke kiri | 2 \| 1 | 71,2% | 67,1 - 75,0% | 60,4 | 0 | 6 | 3,47 |
| 3 | `1-5` ke kanan | 3 \| 5 | 60,0% | 55,6 - 64,2% | 51,3 | 0 | 6 | 2,88 |

**Ini pelajaran paling penting di seluruh buku.** Kartu `2-3` punya peluang menang lebih
tinggi (71,2% berbanding 69,2%), tetapi aplikasi menempatkan `3-6` di peringkat #1. Alasannya
terbaca dari tabel:

- `3-6` memasang ujung 6, dan angka 6 adalah **dominasi** Anda (tangan Anda memuat `6-6`,
  `3-6`, dan ujung 6 baru terbentuk). Mesin mencatatnya: "Ujung cocok angka dominan 6
  (3 kartu)" dan memberi bonus dukungan dominasi.
- `3-6` sekaligus memasang **jerat**: "JERAT angka 6 terpasang! 4 kartu 6 masih di luar."
  Mesin menilai 15 poin untuk jerat itu.
- `2-3` tidak memasang jerat apa pun, dan sebaliknya menyisakan ujung berbahaya bagi diri
  sendiri (`selfTrapScore` 6).
- Kedua kartu sama-sama memaksa lawan PASS dengan frekuensi tinggi (3,08 dan 3,47 kali per
  simulasi) — keduanya langkah kuat.

Apakah perbedaan 2 poin persen peluang itu nyata? **Tidak.** Perhatikan selang
keyakinannya: 65,0-73,1% dan 67,1-75,0% saling menumpuk hampir seluruhnya. Secara
statistik, kedua kartu ini hampir tidak bisa dibedakan dari peluang menangnya saja. Yang
membedakan adalah **bentuk permainannya setelah kartu itu dimainkan**: satu memasang jerat
dominan, satu menyisakan ujung yang tidak menguntungkan. Inilah alasan rankScore ada, dan
alasan Anda sebaiknya membaca alasan strategis, bukan hanya angka peluang.

**Cara membaca "4 kartu 6 masih di luar":** dari 7 kartu berangka 6 di seluruh set, 3 ada
di tangan Anda (`6-6`, `3-6`, dan satu lagi dari kombinasi tangan) dan 4 masih belum
terlihat. Selama kartu-kartu itu masih di luar, ujung 6 akan terus "memakan" kartu lawan
setiap kali mereka menyambung.

## Kunjungi satu kartu secara lengkap

Bila Anda membuka uraian kartu peringkat #1 pada contoh di atas, inilah isinya.

**Lencana:** `TERBAIK` (peringkat #1 dengan peluang di atas 50%).

**Kotak statistik:**

| Kotak | Nilai | Arti |
|---|---|---|
| Win | 69,2% | peluang menang dari simulasi |
| Jerat | 15 | kekuatan jerat yang Anda pasang |
| Kunci | 0 | tidak ada ujung yang terkunci oleh langkah ini |
| Lawan Pass | 3,1 | rata-rata berapa kali lawan lewat dalam satu gim setelah langkah ini |
| Sisa Mata | 6,1 | rata-rata nilai mata di tangan Anda saat gim berakhir |
| Risk | 46,6 | seberapa sering kartu berbahaya muncul pada gim yang Anda kalahkan |

**Bar:**

- *Peluang Menang* — batang berwarna sesuai tingkat (hijau di atas 50%, kuning 35-50%,
  merah di bawah 35%), dengan catatan "interval 95%: 65,0-73,1%".
- *Menang lewat ADU* — 25,0% pada contoh ini: seperempat dari kemenangan datang dari
  skenario meja macet, bukan dari menghabiskan kartu.
- *Kekuatan Jerat* — 15 poin (batang merah muda).

**Kotak strategi.** Berisi `trapReasons` dan `blockReasons`, yaitu kalimat alasan yang
sama seperti yang dipakai mesin untuk menilai langkah. Contohnya pada langkah ini:
"JERAT angka 6 terpasang! 4 kartu 6 masih di luar."

**Kotak blok terjamin.** Muncul hanya bila langkah itu mematikan lawan menurut **bukti**
PASS. Kalimatnya berbentuk "Lawan 1 PASTI tidak bisa main (tidak punya 6 maupun 1)!".
Pada contoh ini kotak itu kosong, karena lawan yang sudah lewat (Lawan 1) masih punya
angka 6 — bukti yang ada hanya menghapus angka 3 dan 1.

**Kotak kartu berbahaya.** Lima kartu yang paling sering muncul di tangan lawan pada gim
yang Anda kalahkan, beserta frekuensinya:

| Kartu | Frekuensi | Tafsiran praktis |
|---|---|---|
| `3-5` | 96% | hampir selalu ada di tangan lawan saat Anda kalah |
| `5-6` | 95% | idem |
| `2-5` | 92% | idem |
| `4-6` | 92% | idem |
| `2-6` | 91% | idem |

Angka-angka ini jangan dibaca sebagai "kartu itu ada di tangan lawan" — itu tidak benar.
Bacalah sebagai: **kartu-kartu inilah yang paling sering menjadi alat kekalahan Anda**, dan
itu karena semuanya mengandung angka 5 atau 6, yang memang sedang hidup di meja. Bila
frekuensi sebuah kartu mendekati 100% sementara kartu itu masih mungkin dipegang lawan,
Anda sebaiknya waspada: kartu itu kemungkinan besar akan keluar.

## Interval keyakinan: alat ukur keraguan

Setiap peluang menang disertai **interval keyakinan Wilson 95%** — rentang yang, secara
statistik, memuat nilai sebenarnya dengan keyakinan 95% bila simulasi diulang tanpa batas.
Rumusnya dihitung mesin:

```text
pusat  = (p + z²/2n) / (1 + z²/n)
margin = z x akar( p(1-p)/n + z²/4n² ) / (1 + z²/n)          z = 1,96
selang = pusat ± margin
```

dengan `p` peluang yang terukur dan `n` jumlah simulasi. Lebar interval menyempit mengikuti
akar jumlah simulasi — inilah alasan menambah simulasi memberi manfaat yang mengecil:

| Simulasi | Selang 95% untuk peluang 50% | Lebar |
|---|---|---|
| 200 | 43,1% - 56,9% | 13,7 poin |
| 500 | 45,6% - 54,4% | 8,7 poin |
| 1000 | 46,9% - 53,1% | 6,2 poin |
| 2000 | 47,8% - 52,2% | 4,4 poin |
| 5000 | 48,6% - 51,4% | 2,8 poin |
| 10000 | 49,0% - 51,0% | 2,0 poin |

<!--DIAGRAM:wilson-->

**Cara memakainya:** dua kartu hanya benar-benar berbeda bila selangnya tidak saling
menumpuk. Pada contoh di atas, 65,0-73,1% dan 67,1-75,0% menumpuk, jadi jangan
memperlakukan #1 dan #2 sebagai "yang satu jauh lebih baik". Sebaliknya, kartu ketiga
(55,6-64,2%) tidak menumpuk dengan kartu pertama, jadi perbedaan antara #1 dan #3 memang
nyata.

## Peringkat mana yang boleh diabaikan

Beberapa keadaan yang sering menyesatkan pemakai baru:

**Peluang tinggi tetapi keamanan nol.** Di mode kartu pertama, selalu periksa bar
**Keamanan Putaran 2**. Bila tertulis 0 kartu bisa dimainkan di putaran kedua, langkah
itu berbahaya apa pun peluangnya. Mesin menampilkan peringatan merah tegas untuk kondisi
ini, misalnya: "BAHAYA! Tidak ada kartu yang bisa dimainkan di putaran ke-2!"

**Kunci melawan peluang.** Kadang langkah dengan peluang sedikit lebih rendah tetapi
mematikan seorang lawan menurut data PASS akan muncul di #1. Itu bukan kesalahan; itu
memang strategi terbaik karena giliran akan kembali ke Anda tanpa lawan bisa mencegahnya.

**Ujung yang "mengubah permainan".** Bila langkah #1 dan #2 punya selang bertumpuk dan
tidak ada jerat atau kunci, pilih yang paling **aman untuk langkah berikutnya** — yaitu
yang menyisakan ujung masih hidup untuk Anda sendiri. Bar keamanan putaran kedua bisa Anda
pakai sebagai pembanding cepat pada mode kartu pertama; pada mode biasa, perhatikan angka
"Jebakan diri" di kotak statistik.

**Rekomendasi yang basi.** Setiap siluet dan glow rekomendasi divalidasi ulang terhadap
keadaan papan saat ini: bila kartu rekomendasi sudah keluar dari tangan Anda atau ujung
meja sudah berubah sehingga kartu itu tidak bisa disambungkan, tanda rekomendasi
dihilangkan sampai analisis berikutnya selesai. Jadi, glow yang hilang bukan kerusakan —
itu pertanda data sudah berubah.

## Profil kekayaan angka lawan

Untuk setiap lawan, mesin menaksir angka mana yang kemungkinan besar ia kuasai, dan
seberapa percaya diri taksiran itu. Contoh nyata dari perhitungan di atas:

| Lawan | Kartu tersembunyi | Kolam kemungkinan | Angka tersangka | Balak diperkirakan |
|---|---|---|---|---|
| Lawan 1 | 6 | 4 kartu | 5 (±6,0 kartu, 100%) dan 4 (±3,0, 50%) | ≈ 1,5 |
| Lawan 2 | 5 | 20 kartu | 5 (±1,8 kartu, 35%) dan 0 (±1,5, 30%) | ≈ 1,3 |
| Lawan 3 | 8 | 11 kartu | 1 (±3,6 kartu, 45%) dan 3 (±3,6, 45%) | ≈ 2,2 |

Cara membacanya: **"kartu tersembunyi"** adalah berapa kartu yang belum terlihat yang
diperkirakan ada di tangan lawan itu. **"Kolam kemungkinan"** adalah berapa kartu yang
masih mungkin ia pegang sesuai semua batasan (PASS dan atribusi). **Angka tersangka**
adalah dua angka teratas dengan perkiraan jumlah kartu dan persentasenya terhadap
perkiraan jumlah kartu lawan itu.

Perhatikan Lawan 1 pada tabel: kolamnya hanya 4 kartu, dan taksirannya mencapai 100% untuk
angka 5. Ini bukan berarti pasti, tetapi kolamnya memang sudah sangat sempit karena PASS
lawan itu menghapus angka 3 dan 1, dan kartu-kartu yang tersisa hampir semuanya berangka
4 atau 5. Semakin banyak PASS yang Anda catat, semakin sempit kolamnya, dan semakin
tajam taksiran ini.

## Kartu sisa yang paling mungkin mati

Pada mode cangkul mati, mesin menjalankan simulasi pembagian kartu khusus untuk menghitung
**peluang setiap kartu berakhir di sisa** dan **perkiraan jumlah kartu mati per angka**.
Contoh keluaran yang bentuknya bisa Anda lihat di panel:

```text
Kartu Sisa Mati (4)
  3: ±1,2 mati     5: ±1,8 mati     6: ±1,0 mati
  [kartu berwarna sesuai tingkat: >=50% merah, 25-49% oranye, <25% normal]
```

Manfaat praktisnya: angka yang banyak "mati" di sisa menjadi langka di permainan nyata.
Bila 2 dari 7 kartu berangka 5 akan mati, artinya hanya 5 kartu berangka 5 yang beredar —
dan permainan lebih muda macet di angka itu.

## Mode kartu pertama: membaca keamanan putaran kedua

Pada giliran pertama, peluang menang saja tidak cukup, karena kartu pertama menentukan
bentuk dua putaran berikutnya. Mesin menghitung **rasio keamanan**: dari sisa kartu di
tangan Anda, berapa yang bisa disambungkan setelah kartu pertama itu dimainkan.

| Nilai | Arti | Tindakan |
|---|---|---|
| Rasio 50% atau lebih | aman; banyak pilihan di putaran kedua | boleh diandalkan |
| Rasio 25-49% | cukup; pilihan terbatas | pertimbangkan alternatif |
| Rasio di bawah 25% | berbahaya; bisa PASS dini | hindari kecuali terpaksa |
| Rasio 0% | tidak ada kartu yang bisa dimainkan di putaran kedua | hampir selalu salah |

Mesin juga memberi bonus 30 poin rankScore untuk rasio keamanan ini, dan menampilkan
daftar kartu mana saja yang bisa dimainkan di putaran kedua — supaya Anda bisa memeriksa
perhitungannya dengan mata sendiri.

## Apa yang tidak bisa diberitahu oleh angka ini

Bagian ini penting agar Anda tidak menaruh kepercayaan berlebih.

- **Lawan di simulasi bukan manusia.** Mesin memakai tiga gaya heuristik (penahan,
  penimbun, pembuang) yang dirotasi. Lawan nyata bisa bermain jauh berbeda, khususnya
  lawan yang bermain tidak rasional.
- **Pembagian kartu mengasumsikan keacakan.** Setiap simulasi membagikan kartu secara
  acak di antara lawan, hanya dibatasi oleh PASS dan atribusi Anda. Bila cara mengocok di
  meja Anda tidak acak (kartu dikocok kurang, kartu menempel), asumsi ini tidak berlaku.
- **Mode cepat memakai derau.** Pada mode biasa (bukan teliti), lawan memilih langkah
  dengan sedikit keacakan agar variasinya hidup. Mode teliti menghilangkan derau untuk
  lawan yang bermain tepat setelah Anda.
- **Konvensi meja harus benar.** Bila aturan adu di meja Anda berbeda dari yang disetel,
  seluruh angka peluang menang dan bar "menang lewat adu" akan menyimpang.
- **Angka tidak pernah menggantikan pengamatan.** Aplikasi ini membutuhkan Anda untuk
  memasukkan apa yang terjadi; ia tidak melihat meja. Data yang lebih lengkap selalu
  mengalahkan jumlah simulasi yang lebih besar.

Satu jaminan yang bisa Anda andalkan sepenuhnya: **kejujuran aritmetika**. Hasilnya
deterministik (seed tetap), konservasi kartu diverifikasi pada setiap simulasi
(penanda `conserved` bernilai benar), dan seluruh angka yang tampil berasal dari
perhitungan mesin yang sama yang bisa Anda jalankan sendiri dari terminal.
