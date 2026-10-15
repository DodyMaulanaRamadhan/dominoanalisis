# Bagian VI — Arsitektur & Isi Mesin

Bagian ini menjelaskan bagaimana aplikasi dibangun dan mengapa keputusan desainnya
diambil. Cocok untuk pembaca yang ingin mengubah kode, memverifikasi perhitungan, atau
sekadar tidak ingin memakai alat yang tidak dipahaminya.

## Tiga lapisan

<!--DIAGRAM:arsitektur-->

Pemisahan menjadi tiga lapisan memiliki alasan praktis, bukan sekadar kerapian:

| Keputusan | Alasan |
|---|---|
| Mesin ditulis dalam C++ | simulasi Monte-Carlo berjalan milyaran operasi; bahasa terkompilasi memberi kecepatan yang membuat ribuan gim per langkah menjadi layak |
| Mesin dibuat sebagai program CLI | mesin bisa diuji langsung dari terminal tanpa server, tanpa peramban, dan tanpa jaringan — mempermudah penelusuran dan pengujian otomatis |
| Server ditulis dengan pustaka bawaan Python | tidak ada dependensi yang perlu dipasang; pemasangan hanya butuh Python |
| Antarmuka tanpa kerangka kerja | memuat instan di ponsel, bisa dibaca seluruhnya dalam satu berkas `app.js`, dan tidak butuh proses build |

Yang menarik: mesin tidak menghitung apa pun yang berhubungan dengan tampilan. Ia tidak
tahu apa itu "glow", "siluet", atau "kolom lawan". Ia menerima JSON, menjalankan simulasi,
dan mengembalikan JSON. Semua keputusan visual terjadi di antarmuka.

## Alur satu permintaan

<!--DIAGRAM:alur-data-->

Bentuk data yang berpindah antar lapisan:

```json
{
  "cmd": "analyze", "numPlayers": 4, "cardsPerPlayer": 7, "numSims": 2000,
  "seed": 20240922, "leftEnd": 3, "rightEnd": 1,
  "myHand": ["6-6", "3-6", "2-3", "1-5", "4-4"],
  "played": ["0-3", "0-2", "1-2"],
  "playedBy": ["opp1", "opp2", "opp1"],
  "nextSeat": 1, "deadlockRule": "lowest", "tieRule": "win",
  "cangkul": true, "adversarial": false,
  "opponents": [{"passes": 1, "eliminated": [3, 1]}, {"passes": 0, "eliminated": []},
                {"passes": 0, "eliminated": []}]
}
```

Balasannya berisi ringkasan permintaan, daftar lawan, daftar langkah berserta seluruh
statistiknya, dan (bila ada sisa) daftar kartu yang mungkin mati. Bagian IX memuat tabel
lengkap setiap bidang.

**Pembagian tanggung jawab** — siapa melakukan apa — sengaja dibuat tegas:

| Tugas | Dikerjakan oleh | Alasan |
|---|---|---|
| Normalisasi format kartu (`6-3` → `3-6`) | server | masukan pengguna boleh longgar; mesin sebaiknya ketat |
| Validasi permintaan (batas, duplikat, aturan) | server **dan** mesin | pertahanan berlapis: server menolak lebih awal, mesin menolak sebagai jaring terakhir |
| Pembatasan beban CPU (`numSims` maksimum) | server **dan** mesin | mencegah penyalahgunaan walau salah satu lapisan diubah |
| Perhitungan peluang, statistik, dan peringkat | mesin | satu sumber kebenaran; antarmuka hanya menggambar |
| Penentuan urutan tampilan akhir | antarmuka | hanya urutan tampil; nilai peringkat tetap milik mesin |

## Mesin: satu berkas C++20 tanpa dependensi

Mesin berada di `engine/domino_engine.cpp` — sekitar 1.700 baris, satu berkas, tanpa satu
pun pustaka pihak ketiga. Ia membaca **satu** permintaan JSON dari masukan standar dan
menulis **satu** balasan JSON ke keluaran standar, lalu berhenti.

```bash
echo '{"cmd":"selftest"}' | ./bin/domino_engine.exe
```

### Parser JSON sendiri

Mesin membawa parser JSON kecil (`JValue` + `JParser`). Alasannya sederhana: menambah
dependensi JSON hanya untuk membaca satu objek akan mengorbankan sifat paling berharga
dari mesin ini — bisa dibangun di mana saja dengan satu perintah.

Parser itu menangani tipe dasar (objek, larik, string, angka, boolean, null), escape
`\uXXXX` dengan pengkodean UTF-8, dan **menolak** masukan yang tidak rapi (karakter sisa
setelah nilai JSON, string tanpa penutup, angka tidak sah). String sumber disimpan sebagai
nilai, bukan rujukan, supaya tidak ada rujukan menggantung saat data berasal dari
sementara.

### Kartu dan kunci kanonik

Kumpulan kartu dibuat sekali di awal: `0-0`, `0-1`, … `6-6`, 28 buah, dengan kunci
berbentuk `lo-hi` (angka kecil lebih dulu). Karena itu mesin **hanya menerima** kunci
kanonik:

```text
diterima mesin   : "3-6", "0-0", "1-5"
ditolak mesin    : "6-3"   -> invalid tile key: 6-3
```

Normalisasi `6-3` menjadi `3-6` adalah tugas server. Ini contoh nyata pembagian
tanggung jawab di atas: pengguna boleh mengetik apa saja, mesin tetap ketat.

### Angka acak yang bisa diulang

Mesin memakai pembangkit acak **xoshiro256\*\*** yang disemai lewat `splitmix64`. Sifat
yang penting: dengan seed yang sama, urutan angka yang dihasilkan identik, sehingga
seluruh hasil analisis dapat direproduksi persis. Antarmuka selalu mengirim seed tetap
`20240922`, jadi sesi yang sama akan menghasilkan angka yang sama pula — kecuali jumlah
simulasi diubah.

Ini bukan kemewahan teknis. Determinisme membuat hasil bisa diperiksa: bila ada yang
mencurigakan, jalankan permintaan yang sama dua kali di terminal dan bandingkan keluarannya
huruf demi huruf.

### Peta angka dan dominasi

Dua struktur data kecil dipakai berulang kali: **Dominance** (berapa kali setiap angka 0-6
muncul di sebuah tangan, dengan ambang "dominan" pada 3 dan "kuat" pada 2) dan **NumMap**
(berapa kartu setiap angka ada di tangan saya, sudah keluar, dan belum diketahui). NumMap
selalu memenuhi `milik saya + sudah keluar + belum diketahui = 7`, yang sekaligus menjadi
pemeriksaan konsistensi.

### Pembagian kartu yang sadar batasan

Ini bagian yang membuat "data PASS" dan "atribusi kartu" benar-benar berguna. Setiap
simulasi harus membagikan kartu yang belum diketahui ke tangan lawan-lawannya. Aturannya
bertingkat:

<!--DIAGRAM:dealing-->

| Prioritas | Sumber data | Perlakuan |
|---|---|---|
| 0 (terkuat) | atribusi kartu Anda | kartu **dipaksa** masuk ke tangan lawan pemiliknya |
| 1 | PASS lawan | kartu yang mengandung angka yang di-PASS **dibuang** dari undian untuk lawan itu |
| 2 (cadangan) | — | bila kuota lawan belum terpenuhi, batasan dilepas dan kejadian itu dihitung sebagai *fallback* |

Lawan dengan batasan paling ketat dilayani lebih dulu, supaya kartu yang paling
terbatas tidak "terpakai" oleh pembagian yang lebih longgar. Jumlah *fallback* dilaporkan
oleh pemeriksaan mandiri: pada 400 skenario acak, sekitar 57 skenario terpaksa memakai
jalur cadangan — angka yang wajar, bukan tanda kerusakan.

Perhatikan konsekuensi pentingnya: bila atribusi Anda bertentangan dengan PASS lawan yang
sama (misalnya lawan itu sudah ditandai tidak punya angka 3, tetapi Anda menandainya
sebagai pemain kartu `3-5`), mesin **mengabaikan atribusi yang bertentangan** dan memakai
bukti PASS. Bukti keras menang atas dugaan.

## Mesin: satu langkah dianalisis bagaimana

<!--DIAGRAM:monte-carlo-->

Untuk **setiap** kandidat langkah, mesin melakukan rangkaian berikut:

1. **Hasilkan langkah yang sah.** Sebuah kartu menghasilkan langkah "ke kiri", "ke kanan",
   atau keduanya; pada papan kosong hanya satu langkah "pertama". Kartu yang bisa masuk ke
   dua ujung dihitung sebagai dua kandidat terpisah, karena akibatnya berbeda.
2. **Terapkan langkah secara maya** untuk mendapatkan ujung baru dan sisa tangan, lalu
   susun peta angka baru untuk keadaan setelah langkah itu.
3. **Hitung heuristik tanpa simulasi** (di bawah).
4. **Jalankan N simulasi.** Setiap simulasi: bagi kartu dengan menghormati batasan →
   mainkan gim sampai selesai → catat hasilnya (menang/kalah, sisa mata, jumlah PASS
   lawan, konservasi kartu, kartu yang dimainkan lawan pada gim yang kalah).
5. **Agregasi**: peluang menang, selang Wilson, peluang menang lewat adu, rata-rata sisa
   mata, rata-rata PASS lawan, skor risiko.
6. **Susun rankScore** dan kirimkan seluruh statistiknya ke antarmuka.

### Heuristik tanpa simulasi

Empat penilaian dihitung hanya dari keadaan papan dan peta angka:

| Penilaian | Pemicu | Poin |
|---|---|---|
| Dukungan dominasi | ujung cocok dengan angka dominan Anda | +20 |
| Dukungan dominasi | **kedua ujung** adalah angka dominan Anda | +30 |
| Dukungan angka kuat | ujung cocok dengan angka yang Anda pegang dua kali | +8 |
| Jerat | angka dominan Anda terpasang di ujung dan masih ada kartu di luar | +15 |
| Jerat ganda | kedua ujung adalah angka dominan yang sama | +20 |
| Kunci | ujung dengan angka yang tidak ada di luar, dan Anda masih memegangnya | +25 |
| Kunci hampir | angka ujung tinggal satu di luar dan Anda pegang dua | +12 |
| Jebakan diri | ujung mati untuk semua orang dan bukan milik Anda | +10 (pengurang) |
| Jebakan diri | Anda tidak punya kartu berangka ujung sementara masih ada di luar | +6 (pengurang) |
| Blok terjamin | lawan yang **pasti** tidak bisa menyambung menurut data PASS | +8 per lawan |

### Tiga gaya lawan

Simulasi tidak bermain melawan satu jenis lawan. Tiga profil disimulasikan dan **dirotasi**
antar simulasi, sehingga tiap kandidat langkah diuji menghadapi campuran gaya:

| Gaya | Perilaku (bobot penilaiannya) |
|---|---|
| **Blocker** | menghukum ujung yang masih banyak jawabannya, menghargai keluwesan dan nilai mata; sangat menghindari membuat kedua ujung sama |
| **Hoarder** | menghargai ujung dari angka kuatnya dan menghukum pemborosan kartu angka dominan (kartu dominan bernilai -25, balak dominan -40) |
| **Dumper** | cepat membuang: nilai mata besar dan balak diberi bobot positif besar |
| **Campuran (pemain)** | gaya yang Anda pakai sendiri di simulasi: menghargai balak, ujung berangka dominan, ujung yang hanya bisa dijawab Anda, dan keluwesan |

Pada mode biasa, setiap pilihan diberi derau kecil (nilai acak sampai 5) agar variasinya
hidup dan tidak menghasilkan permainan yang sama terus. Pada **mode teliti**, lawan yang
bermain tepat setelah Anda dimainkan sebagai **Blocker tanpa derau** — permainan yang
ketat dan deterministik. Efeknya: estimasi menjadi lebih konservatif, seperti bermain
melawan lawan yang tidak pernah melakukan kesalahan bodoh.

## Mesin: satu gim simulasi

Satu gim berjalan seperti permainan sungguhan:

- Giliran dimulai dari pemain yang bermain setelah Anda (atau lawan pertama bila papan
  kosong), lalu berputar.
- Pemain yang tidak punya langkah sah **PASS**. Bila mode cangkul aktif dan masih ada
  sisa, ia menarik kartu sisa **satu per satu** sampai menemukan kartu yang bisa
  dimainkan atau sisa habis.
- Gim berakhir pada salah satu dari tiga kemungkinan: tangan Anda habis (**menang**),
  tangan lawan habis (**kalah**), atau semua pemain PASS dalam satu putaran penuh
  (**macet** → dinilai dari adu).
- Ada batas keselamatan 300 giliran; bila tercapai, gim dinilai seperti keadaan macet.
  Batas ini praktis tidak pernah tercapai, tetapi menjamin simulasi selalu berhenti.

Setiap gim memverifikasi **konservasi kartu**: jumlah kartu di semua tangan ditambah kartu
yang sudah masuk papan harus sama dengan jumlah kartu saat pembagian. Bila tidak sama,
hasil itu ditandai `conserved: false` dan pemeriksaan mandiri akan menangkapnya. Ini
pertahanan terhadap kelas kesalahan yang paling berbahaya dalam simulasi: kartu yang
"muncul dari udara" akan menghasilkan peluang menang yang salah tanpa gejala apa pun.

Penentuan pemenang saat macet memakai konvensi meja Anda: nilai mata Anda dibandingkan
dengan nilai mata **terkecil** lawan atau **rata-rata** lawan, dengan perilaku seri sesuai
pilihan Anda.

## Mesin: dari hasil ke rekomendasi

Setelah semua simulasi untuk semua kandidat selesai, mesin menghitung tiga hal lagi.

**Skor risiko.** Untuk setiap gim yang Anda kalahi, mesin mencatat kartu-kartu yang
dimainkan lawan. Lima kartu yang paling sering muncul dihitung frekuensinya terhadap
jumlah kekalahan; jumlah kontribusinya (frekuensi x 10) menjadi `riskScore`. Inilah dasar
kotak "Kartu Berbahaya" di antarmuka.

**Keamanan kartu pertama.** Hanya untuk papan kosong: dari sisa kartu di tangan Anda,
berapa yang bisa dimainkan setelah kandidat pertama dipakai.

**Peringkat.** Semua komponen digabung menjadi satu nilai:

<!--DIAGRAM:rankscore-->

Contoh perbandingan nyata dari Bagian V: kartu `2-3` memiliki peluang menang 71,2%
(lebih tinggi 2 poin daripada `3-6`), tetapi kalah peringkat karena `3-6` memasang jerat
(+15 x 0,8 = +12) dan tidak memiliki jebakan diri, sementara `2-3` memiliki jebakan diri
(-6 x 0,5 = -3) dan tidak memasang jerat. Selisih akhir: 84,2 berbanding 60,4.

**Kartu yang mungkin mati.** Bila masih ada sisa kartu, mesin menjalankan simulasi
pembagian tambahan (tanpa memainkan gim) untuk menghitung peluang setiap kartu berakhir di
sisa, serta perkiraan jumlah kartu mati per angka. Jumlah simulasi tambahan ini dibatasi
2.000 agar tidak menambah waktu tunggu secara berlebihan.

## Server: tipis, tetapi tidak bodoh

Server sengaja tipis: ia menormalkan, memvalidasi, memanggil mesin, dan menyajikan berkas.
Dua hal yang membuatnya tidak sekadar "pipa":

**Kode status HTTP yang jujur.** Kesalahan tidak pernah menyamar sebagai keberhasilan.

| Keadaan | Status | Alasan |
|---|---|---|
| berhasil | 200 | — |
| validasi permintaan gagal | 400 | kesalahan pengirim, bukan server |
| mesin menolak permintaan (logika) | 400 | `ok:false` dari mesin tidak boleh jadi 200 |
| token salah atau hilang | 401 | hanya saat `APP_TOKEN` diisi |
| endpoint tidak dikenal | 404 | — |
| metode salah (misalnya GET ke `/api/meta`) | 405 | — |
| mesin gagal dijalankan (exit != 0) | 500 | detail hanya masuk log server |
| balasan mesin bukan JSON | 502 | mesin berjalan tetapi keluarannya rusak |
| biner mesin belum ada | 503 | pemasangan belum lengkap |
| mesin melebihi 300 detik | 504 | permintaan terlalu berat |

Prinsip desainnya: klien luar (skrip, monitor, `curl`) harus bisa menyimpulkan berhasil
atau gagal **hanya dari kode status**, tanpa perlu membaca isi balasan.

**Keamanan bawaan.** Karena aplikasi ini sering dijalankan di komputer pribadi dan kadang
dibuka lewat tunnel, servernya memasang pengaman dasar:

| Pengaman | Cara kerja |
|---|---|
| Mencegah sniffing tipe berkas | header `X-Content-Type-Options: nosniff` |
| Mencegah pembingkaian (clickjacking) | `Content-Security-Policy` dengan `frame-ancestors 'none'` |
| Membatasi sumber skrip | `default-src 'self'; script-src 'self'` — tidak ada skrip pihak ketiga |
| Mencegah kebocoran rujukan | `Referrer-Policy: no-referrer` |
| Mencegah pembacaan berkas di luar `web/` | setiap jalur di-resolve dan diperiksa berada di dalam `web/` |
| Mencegah CSRF dari situs lain | isi permintaan hanya diterima bila `Content-Type: application/json`, dan `Origin` (bila ada) harus sama dengan `Host` |
| Membatasi ukuran permintaan | maksimum 1 MiB; badan kosong atau lebih besar ditolak |
| Mencegah pesan galat memantulkan masukan | pesan galat menyebutkan posisi elemen, bukan isi yang dikirim |
| Token pembanding waktu-konstan | `hmac.compare_digest` — membandingkan token dengan waktu yang selalu sama |

Dua pengaman terakhir layak dijelaskan lebih dalam. Yang pertama menutup celah XSS: pesan
galat dikirim ke antarmuka dan pernah dirender sebagai HTML, jadi masukan pengguna tidak
boleh dipantulkan mentah-mentah. Yang kedua menutup celah CSRF yang khas untuk aplikasi
lokal: peramban mengirim permintaan "sederhana" lintas situs tanpa pemeriksaan awal, jadi
halaman web lain di komputer Anda bisa saja memicu `POST /api/analyze` ke localhost.
Pemeriksaan `Content-Type` dan `Origin` menutup jalan itu.

## Antarmuka: satu berkas, satu sumber keadaan

`web/app.js` memuat seluruh logika antarmuka dalam satu objek keadaan:

| Bidang keadaan | Isi |
|---|---|
| `myHand` | daftar kartu di tangan Anda, dalam bentuk kunci kanonik |
| `boardTiles` | daftar kartu di papan, berisi kartu yang sudah diorientasikan, pemilik, dan penanda kartu pertama |
| `allPlayed` | daftar kronologis semua kartu yang pernah masuk papan |
| `playedBy` | label pemilik untuk setiap kartu di `allPlayed` (`me`, `unknown`, `opp1`…`opp4`) |
| `opponents` | untuk setiap lawan: riwayat PASS dan daftar angka yang tereliminasi |
| `pending` | kartu yang sedang menunggu pilihan ujung |
| `pendingAttrib` | kartu yang sedang menunggu atribusi pemain |
| `isAnalyzing`, `pendingRun`, `abortCtl` | penanda analisis berjalan, antrean, dan pembatal |
| `liveMode` | apakah mode hidup aktif |
| `lastAnalysis`, `recommended` | hasil terakhir dan rekomendasi #1 |
| `timeline` | salinan keadaan untuk Undo (maksimum 100 langkah) |

Dua bidang yang perlu diperhatikan: `boardTiles` **bukan** daftar kronologis (kartu yang
dimainkan ke kiri disisipkan di depan larik), sehingga penanda `first: true` dipakai
khusus untuk menandai kartu pertama; sedangkan `allPlayed` tetap kronologis dan dipakai
untuk menghitung kartu yang sudah keluar. Perbedaan ini adalah sumber kebingungan yang
sering muncul saat memodifikasi kode, dan sudah diatasi dengan penanda eksplisit.

**Keamanan tampilan.** Semua nilai dinamis yang masuk ke HTML dilewatkan fungsi pengaman
`esc()` yang mengubah karakter `&`, `<`, `>`, `"`, dan `'` menjadi bentuk aman. Ini penting
karena data sesi bisa berasal dari berkas impor.

**Validasi berkas impor.** Sebelum diterima, sesi yang diimpor diperiksa berlapis: setiap
kartu harus cocok dengan pola `angka-angka`, label pemain harus sah, dan data PASS harus
berupa angka 0-6. Data yang tidak lolos ditolak seluruhnya, bukan sebagian.

**Ketahanan Undo.** Setiap aksi yang mengubah keadaan menyimpan salinan lengkap (termasuk
PASS lawan dan atribusi), sehingga Undo tidak pernah meninggalkan data setengah jalan.

## Tata letak papan: mengapa ada "pengecilan otomatis"

Menampilkan rantai domino hingga puluhan kartu di layar ponsel adalah masalah nyata.
Pendekatan naif (satu baris panjang yang digulir) membuat pemain kehilangan gambaran
besar. Karena itu papan memakai tiga teknik bertingkat:

1. **Baris ular (boustrophedon).** Kartu disusun dalam baris-baris yang bergantian arah.
   Baris ganjil dibalik urutannya **dan** tiap kartunya dicerminkan, sehingga angka yang
   bersambung tetap bertemu rapat di tikungan. Tikungan dibentuk oleh kartu "siku" yang
   digambar berdiri.
2. **Pengecilan bertahap.** Ukuran kartu diturunkan sampai seluruh isi papan muat
   (batas bawah setengah ukuran normal). Skala ini diterapkan lewat satu variabel CSS
   (`--tw`), dan semua ukuran turunan (kartu berdiri, pips, garis pemisah) ikut mengecil
   secara proporsional.
3. **Pemusatan kartu pertama.** Kartu pertama diusahakan selalu berada di tengah area
   papan. Bila isi papan muat, seluruh baris digeser (tanpa menggulir). Bila isi papan
   lebih besar dari papan bahkan setelah pengecilan, aplikasi kembali ke mode gulir dan
   memakai tambahan lebar/padding untuk mencapai posisi tengah.

Ada satu detail yang tampak sepele tetapi krusial: aplikasi mencoba dua gaya pembagian
baris — **baris penuh** (kartu paling besar, tetapi kartu pertama belum tentu di tengah)
dan **baris lebih pendek sekitar 60%** (kartu sedikit lebih kecil, tetapi kartu pertama
bisa tepat di tengah). Pemenangnya dipilih dengan urutan prioritas: muat dulu, baru paling
dekat ke tengah, baru ukuran kartu paling besar.

**Pemantauan ukuran.** Lebar kolom papan bisa berubah tanpa perubahan ukuran jendela
(misalnya saat panel hasil selesai digambar dan mengubah tata letak). Karena itu papan
memantau kontainernya sendiri lewat `ResizeObserver`, dengan penyaring penting: perubahan
lebar kecil (di bawah 4 piksel) diabaikan bila berasal dari muncul-hilangnya bilah gulir
papan itu sendiri — tanpa penyaring itu, tata letak bisa berbalas-balasan selamanya.

## Siluet rekomendasi (ghost)

Siluet kartu rekomendasi digambar sebagai **lapisan di atas** papan, bukan sebagai kartu
di dalam baris. Alasannya: menambahkan kartu maya ke dalam baris akan mengubah panjang
baris dan bisa menggeser susunan kartu asli — efek yang menyesatkan. Sebagai lapisan, ia
diposisikan relatif terhadap kotak kartu pertama:

| Arah rekomendasi | Posisi siluet | Orientasi |
|---|---|---|
| Ke kanan | di atas kepala kartu pertama | berdiri; separuh yang cocok di atas |
| Ke kiri | di kaki kartu pertama | berdiri; separuh yang cocok di bawah |
| Papan kosong | di dalam alur baris | berdiri (dia calon kartu pertama) |

Label (misalnya "TARUH DI KANAN") ditulis di samping siluet, karena bila diletakkan di
atasnya label itu keluar dari area papan dan tidak terbaca. Siluet digambar **setelah**
pengecilan dan pemusatan selesai, supaya koordinatnya mengikuti kotak kartu pertama yang
sudah final.

## Mode hidup, antrean, dan pembatalan

Tiga mekanisme kecil yang membuat mode hidup terasa mulus:

- **Antrean (`pendingRun`).** Bila analisis sedang berjalan dan Anda melakukan aksi lain,
  permintaan baru tidak dijalankan bersamaan (bisa menghabiskan CPU), tetapi ditandai. Saat
  analisis berjalan selesai, permintaan terbaru dijalankan sekali lagi.
- **Pembatalan (`AbortController`).** Menekan tombol saat analisis berjalan membatalkan
  permintaan yang sedang berjalan, sehingga komputer tidak terus bekerja untuk hasil yang
  sudah tidak Anda butuhkan.
- **Penjagaan keadaan.** Undo dan penekanan kartu dinonaktifkan saat analisis berjalan,
  supaya keadaan tidak berubah di tengah perhitungan dan hasil yang tampil selalu cocok
  dengan data yang ada di layar.

## Service worker: dua strategi berbeda

| Jenis permintaan | Strategi | Alasan |
|---|---|---|
| Berkas antarmuka (HTML, CSS, JS, ikon) | ambil dari tembolok, perbarui di latar belakang | aplikasi terbuka instan dan tetap bisa dibuka tanpa koneksi |
| Permintaan `/api/*` | selalu ke jaringan | hasil analisis tidak boleh diambil dari tembolok |

Karena berkas statis diambil dari tembolok lebih dulu, versi terbaru hanya terlihat
setelah nama tembolok di `sw.js` diubah. Ini konsekuensi yang disengaja dari strategi
tersebut, dan bagian pemecahan masalah akan mengingatkan Anda bila perubahan kode tidak
kunjung tampil.

## Riwayat versi

| Versi | Perubahan besar |
|---|---|
| v1 | analisis dasar satu lapisan (sebelum pemisahan mesin) |
| v2 | pemisahan mesin C++ + server Python; simulasi, peta angka, konvensi meja |
| v3 | atribusi kartu per lawan, tiga profil lawan, mode teliti, Wilson, rankScore, PWA |
| v3.1 | mode cangkul & kartu sisa mati, kisi kandidat kartu per lawan, masukan angka |
| v3.2 | mode hidup aktif sejak awal, masukan cepat dua kotak, indikator status di judul |
| v3.3 | siluet rekomendasi (ghost), glow biru pada kartu pilihan, perbaikan arah ujung lawan |
| v3.6 | tata letak papan bergaya ular dengan pengecilan otomatis dan pemusatan kartu pertama |
| perbaikan terakhir | rumus interval Wilson diperbaiki (sebelumnya selalu menghasilkan 0-100%) |

Nomor versi mesin berdiri sendiri: mesin melaporkan dirinya sebagai `domino-cpp/3.0.0`
pada setiap balasan, sehingga Anda selalu bisa memastikan versi mesin yang sedang dipakai.
