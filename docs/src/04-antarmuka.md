# Bagian IV — Panduan Antarmuka

Bagian ini menjelaskan setiap bagian layar, apa yang dilakukannya, dan bagaimana
memakainya dalam permainan nyata. Urutannya sengaja mengikuti alur kerja pemain:
menyiapkan meja, mengisi kartu, mencatat apa yang terjadi, lalu membaca hasil.

## Tata letak layar

Antarmuka menyesuaikan diri dengan lebar layar, dan ada tiga susunan yang berbeda.

**Ponsel (lebar di bawah 1024px).** Semua panel ditumpuk dalam satu kolom dengan urutan:
judul, setup, bilah aksi, bilah kemajuan, papan, tangan Anda, hasil analisis, lawan,
peta angka, lalu kartu sisa.

**Desktop (1024px ke atas).** Tampilan berubah menjadi tiga kolom:

| Kolom | Lebar | Isi |
|---|---|---|
| Kiri | 300px | setup, banner kualitas, bilah aksi, bilah kemajuan |
| Tengah | sisa lebar | papan, kartu tangan, hasil analisis |
| Kanan | 380px | lawan, peta angka, kartu sisa |

**Layar lebar (1500px ke atas).** Kolom kiri dan kanan sedikit dilebarkan (320px dan
420px) agar panel lawan dan hasil lebih lega, dengan lebar maksimum keseluruhan 1560px.

Perubahan tata letak ini murni tampilan: semua perhitungan dan data sesi sama sekali
tidak berubah, dan lebar panel dihitung ulang secara otomatis oleh pengamat ukuran
(`ResizeObserver`) sehingga papan tetap tersusun rapi saat jendela diubah ukurannya.

## Bilah judul

Di bagian atas terdapat nama aplikasi, daftar kemampuan singkat, penanda versi, dan
**penanda status analisis**:

| Tampilan | Arti |
|---|---|
| `LIVE` dengan titik merah menyala | mode hidup aktif; analisis berjalan otomatis setiap kali data berubah |
| `LIVE` dengan ikon jeda | mode hidup dijeda; analisis hanya berjalan bila Anda menekan tombolnya |

Mode hidup **aktif sejak aplikasi dibuka**. Banyak pemakai mengira tombolnya rusak
karena tidak perlu ditekan; tidak, memang itulah perilaku yang disengaja sejak versi 3.2.

## Panel Setup: memberi tahu aturan meja

Panel ini adalah tempat Anda menyesuaikan aplikasi dengan permainan yang sedang
berlangsung. Semua pilihan di sini memengaruhi perhitungan, jadi setel dulu sebelum
mencatat kartu.

| Kendali | Pilihan | Bawaan | Pengaruh |
|---|---|---|---|
| **Pemain** | 2, 3, 4 | 4 | menentukan jumlah lawan, pembagian kartu, dan urutan giliran |
| **Kartu/Pemain** | 3 sampai 28 dibagi pemain | maksimum | menentukan jumlah kartu tersembunyi dan kartu sisa |
| **Simulasi/Kartu** | 500 sampai 1.700.000 | 10000 | seberapa banyak gim yang disimulasikan untuk setiap kandidat langkah; 1 jt ≈ 95% ±0,1%, 1,7 jt ≈ 99% ±0,1% (lambat, bisa dibatalkan) |
| **Main Setelah Saya** | Lawan 1 sampai Lawan n | Lawan 1 | siapa yang bermain tepat setelah Anda; juga menentukan lawan mana yang bersikap ketat di mode teliti |
| **Adu: Banding** | Mata terkecil / Rata-rata | Mata terkecil | cara menentukan pemenang saat meja macet |
| **Seri = ?** | Menang / Kalah | Menang | perilaku bila nilai mata Anda sama dengan pembanding |
| **Main Cangkul?** | Ya / Tidak | Ya | apakah kartu sisa boleh disambar atau mati |
| **Lawan respons cerdas** | aktif/tidak | tidak aktif | mengaktifkan mode teliti (lebih akurat, lebih lambat) |

Di bawah kendali-kendali itu ada satu baris keterangan yang menghitung sendiri hasil
pilihan Anda, misalnya:

```text
4 pemain × 7 kartu = 28 dibagikan | Semua kartu terpakai (tanpa sisa) (maks 7/pemain)
3 pemain × 5 kartu = 15 dibagikan | Cangkul: 13 kartu (aktif) (maks 9/pemain)
```

Baris ini sengaja dibuat: kesalahan paling sering terjadi adalah salah mengisi jumlah
kartu per pemain, dan angka sisa yang salah membuat seluruh perhitungan menyimpang.

**Berapa jumlah simulasi yang sebaiknya dipakai?** Tabel berikut berasal dari sifat
statistiknya, bukan dari tebakan:

| Simulasi | Waktu tunggu (perkiraan) | Kapan dipakai |
|---|---|---|
| 500 | paling cepat | saat bermain cepat atau di ponsel lama |
| 1000 | cepat | pemakaian sehari-hari |
| 2000 (bawaan) | sedang | keseimbangan yang baik |
| 5000 | paling lama | keputusan besar, atau saat Anda ingin membaca selisih tipis |

Semakin banyak simulasi, semakin sempit interval keyakinan, sehingga perbedaan kecil
antar langkah bisa Anda percayai. Sebaliknya, pada 500 simulasi, selisih dua persen tidak
berarti apa-apa. Bab tentang interval keyakinan di Bagian V menjelaskan hal ini dengan
angka.

## Bilah aksi

| Tombol | Fungsi |
|---|---|
| **Analisis Live** | menyalakan atau menjeda mode analisis otomatis. Saat berjalan, teksnya berubah menjadi "Jeda Live" |
| **Undo** | membatalkan satu langkah terakhir (kartu, PASS lawan, atau atribusi) |
| **Export** | mengunduh seluruh sesi sebagai satu berkas JSON |
| **Import** | memuat sesi dari berkas JSON |
| **Reset** | mengosongkan tangan, papan, dan seluruh catatan lawan (mode hidup tetap aktif) |

Di bawah bilah aksi terdapat **bilah kemajuan**. Saat analisis berjalan, bilah itu
menampilkan persentase, judul pekerjaan, dan rincian singkat, misalnya:

```text
30%  Menganalisis...
5 kartu x 2000 sim (engine C++ v3) - data PASS - atribusi lawan - mode teliti
```

Rincian ini berguna untuk memastikan permintaan yang Anda kirim benar-benar memuat data
yang Anda harapkan. Bila tertulis "tanpa data PASS" padahal Anda sudah menandai PASS,
berarti penandaan itu belum tersimpan.

## Papan: meja domino

Ini bagian yang paling banyak berubah dibandingkan versi awal aplikasi, dan ada beberapa
hal yang perlu dipahami supaya tidak bingung.

**Penanda ujung.** Di atas papan terdapat dua label: "Kiri: X" dan "Kanan: Y". Bila meja
masih kosong, keduanya menampilkan tanda minus. Label ini adalah rujukan tercepat saat
Anda memutuskan arah.

**Kartu sisa.** Chip kecil di judul papan (ikon kotak diikuti angka) menunjukkan jumlah
kartu sisa/cangkul berdasarkan pembagian yang Anda pilih.

**Kartu pertama selalu berdiri tegak dan berwarna emas.** Kartu pertama yang keluar
adalah pusat rantai, dan justru karena itulah ia diberi penanda khusus. Sesudahnya,
rantai tumbuh dari kartu itu ke dua arah.

**Susunan ular.** Rantai tidak memanjang satu baris sampai keluar layar. Papan menyusun
kartu dalam baris-baris yang saling berganti arah — memanjang ke kanan, lalu baris
berikutnya ke kiri, seperti ular. Baris pertama (kartu paling awal) ada di bawah, dan
rantai tumbuh ke atas. Kartu siku di ujung baris digambar dalam posisi berdiri agar
tikungannya tersambung rapi, dan baris ganjil dibalik urutannya supaya angka yang
bersambung tetap bertumpuk rapat.

```text
   [baris 3]  <-- arah ke kiri
   [baris 2]  --> arah ke kanan
   [baris 1]  [kartu pertama berdiri di sini]
```

<!--DIAGRAM:ular-->

**Papan mengecil otomatis.** Bila kartu di papan sudah banyak, ukuran kartu dikecilkan
secara bertahap (sampai setengah ukuran normal) supaya seluruh rantai tetap terlihat
tanpa perlu menggulir. Aplikasi mencoba lebih dulu baris selebar mungkin (kartu paling
besar); bila isi papan belum muat, ia memakai baris yang lebih pendek agar kartu pertama
bisa kembali ke tengah. Bila isi papan tetap tidak muat bahkan pada ukuran minimum,
papan kembali ke mode gulir seperti cara lama — supaya tidak ada kartu yang hilang.

**Bila papan kosong.** Papan menampilkan pesan "Papan kosong — pilih kartu dari tangan
Anda". Bila analisis sudah punya rekomendasi, pesannya berubah menjadi keterangan bahwa
siluet biru di bawah adalah kartu rekomendasi.

## Tangan Anda

Panel **Kartu Saya** menampilkan hitungan kartu (`5/7 kartu`) dan kepingan kartu Anda.

| Tampilan kartu | Arti |
|---|---|
| Hijau (bisa dimainkan) | ada angka yang cocok dengan salah satu ujung papan sekarang |
| Abu-abu (tidak bisa dimainkan) | tidak ada angka yang cocok; kartu ini belum bisa keluar |
| Cincin biru berdenyut | ini kartu peringkat #1 dari analisis terakhir |
| Semua kartu hijau | papan masih kosong, jadi semua kartu boleh menjadi kartu pertama |

Kelima kepingan itu bisa diketuk. Bila kartu hanya cocok di satu ujung, ia langsung
dimainkan. Bila cocok di kedua ujung, muncul jendela **Pilih Ujung Papan** yang
menampilkan akibat masing-masing pilihan, misalnya "→ Kiri jadi 3" dan "→ Kanan jadi 6".

Di papan, kartu rekomendasi terbaik digambar sebagai **siluet bergaris putus-putus
berwarna biru**, ditempatkan relatif terhadap kartu pertama:

<!--DIAGRAM:ghost-->

Hitungan kartu berubah warna menjadi merah bila jumlah kartu tangan Anda melebihi
batas kartu per pemain — tanda bahwa ada salah isi yang perlu dibetulkan.

## Memasukkan kartu: modal 28 kartu dan masukan cepat

Tombol **+ Pilih Kartu Saya** membuka jendela berisi seluruh 28 kartu, disusun empat
kolom. Kartu yang sudah Anda pilih diberi tanda terpilih, dan kartu yang sudah keluar di
papan ditampilkan pudar serta tidak bisa dipilih. Menekan kartu yang sudah terpilih akan
menghapusnya dari tangan (berfungsi sebagai tombol bolak-balik).

Di atas kisi 28 kartu ada **masukan cepat** berupa dua kotak angka dan tombol "+ Tambah".

| Aturan masukan cepat | Perilaku |
|---|---|
| Isi kotak | satu digit 0 sampai 6; karakter lain dibuang sebelum sempat masuk |
| Angka 7 ke atas | kotak langsung kosong dan berkedip merah (tidak valid) |
| Setelah digit pertama | fokus berpindah otomatis ke kotak kedua |
| Urutan angka | bebas: `5` lalu `4` sama dengan kartu `4-5` |
| Menekan Enter | kartu langsung ditambahkan |
| Kartu sudah ada di tangan | bukan ditambah, tetapi **dihapus** (bolak-balik) |
| Setelah menambahkan | kedua kotak dikosongkan dan fokus kembali ke kotak pertama |

Cara ini jauh lebih cepat daripada mengetuk kisi, terutama karena kedua tangan Anda
sering masih memegang kartu asli saat bermain.

**Batas kartu.** Anda tidak bisa menambahkan lebih dari jumlah kartu per pemain; aplikasi
menampilkan peringatan bila Anda mencoba.

## Mencatat lawan: panel Lawan

Panel ini adalah jantung akurasi aplikasi. Setiap lawan memiliki satu kartu panel dengan
beberapa bagian.

| Bagian | Isi | Kegunaan |
|---|---|---|
| Nama dan jumlah kartu | mis. "Lawan 2 · 5 kartu" | perkiraan jumlah kartu lawan, dihitung dari kartu yang dibagikan dikurangi kartu Anda dan kartu lawan yang sudah terlihat |
| **PASS / LEWAT** | tombol merah | catat bahwa lawan ini tidak bisa jalan |
| **Undo** | tombol kecil | membatalkan PASS terakhir lawan ini |
| **PASTI TIDAK PUNYA angka** | deretan angka | hasil eliminasi dari semua PASS lawan tersebut |
| Riwayat pass | mis. `[3|1] → [6|4]` | ujung meja saat lawan itu lewat, berurutan |
| Kartu yang dipastikan dimainkan | mis. `2|5 4|6` | kartu yang Anda atribusikan ke lawan ini |
| Diduga kuasai | mis. "5 (~1.8 kartu, 35%)" | perkiraan kekayaan angka dari mesin |
| Kemungkinan kartu | kisi kartu | daftar kartu yang mungkin dipegang lawan ini, bisa diketuk |
| Filter PASS | mis. "23 dari 26 kartu unknown (tereliminasi 12%)" | berapa banyak kemungkinan yang sudah berhasil dipersempit |

**Cara mencatat PASS.** Ketuk tombol **PASS / LEWAT** pada lawan yang melewati giliran.
Aplikasi mencatat ujung meja saat itu (`[kiri|kanan]`), lalu menambahkan kedua angka itu
ke daftar "pasti tidak punya" milik lawan tersebut. Tombol ini tidak aktif saat papan
masih kosong, karena di awal permainan belum ada ujung untuk diuji.

**Cara mencatat kartu lawan (atribusi).** Ketuk kartu di panel **Kartu Sisa** atau di
kisi **Kemungkinan kartu** milik lawan. Muncul jendela "Siapa yang memainkan kartu ini?"
berisi tombol untuk setiap lawan, plus tombol "Tidak tahu / lupa". Bila Anda memilih
seorang lawan, kartu itu dinyatakan miliknya dan **dieliminasi dari semua lawan lain**
sekaligus. Bila Anda memilih "tidak tahu", kartu tetap tercatat keluar, tetapi tidak
diatribusikan kepada siapa pun.

**Kisi kemungkinan kartu.** Setiap kartu yang mungkin dipegang lawan ditampilkan, dan
kartu yang **saat ini bisa dimainkan** diberi kilau merah. Kilau itu penting: bila lawan
menolak jalan padahal kartu itu bisa dimainkan, berarti kartu itu tidak ada di tangannya
— dan Anda sebaiknya mencatat PASS untuk mempersempit lebih jauh. Sebaliknya, bila lawan
memainkan kartu berkilau merah, kemungkinan besar Anda bisa menebak sisanya.

> Satu aturan penting: jangan menandai PASS berdasarkan tebakan. Data PASS bersifat
> **bukti keras** dan langsung memaksa simulasi menghormatinya. Satu kesalahan PASS akan
> menyempitkan kemungkinan kartu lawan secara keliru, dan analisis berikutnya menjadi
> yakin pada hal yang salah.

## Peta angka

Panel **Peta Angka** menampilkan tujuh baris (angka 0 sampai 6) dengan tiga informasi:

- **Di tangan saya** (bagian biru): berapa kartu berangka itu yang Anda pegang.
- **Sudah keluar** (bagian kuning): berapa yang sudah terlihat di papan.
- **Belum diketahui** (sisa sampai tujuh): berapa yang masih tersembunyi.

Angka yang Anda kuasai tiga kali atau lebih ditandai sebagai **dominan**. Angka yang
habis dari peredaran (tidak di tangan Anda, tidak terlihat di papan) ditandai sebagai
**exhausted**, artinya angka itu tidak akan pernah muncul lagi. Angka yang sedang berada
di ujung papan diberi penanda lokasi.

Peta ini adalah alat penalaran cepat yang paling sering dipakai pemain berpengalaman:
bila sebuah angka sudah exhausted, meja akan macet di angka itu, dan pembandingnya adalah
nilai mata. Bila angka dominan Anda ada di ujung, Anda sedang mengendalikan permainan.

## Kartu sisa: tiga perilaku berbeda

Panel **Kartu Sisa** berubah perilaku sesuai pengaturan cangkul.

**Mode A — semua kartu dibagikan.** Bila tidak ada sisa (misalnya 4 pemain x 7 kartu),
panel menampilkan keterangan bahwa semua kartu ada di tangan pemain dan Anda diarahkan
ke kolom Lawan.

**Mode B — cangkul aktif.** Judulnya "Kartu Cangkul", dan setiap kepingan bisa diketuk
untuk mencatat bahwa **lawan menyambar kartu itu** — persis alur atribusi yang dijelaskan
di atas.

**Mode C — cangkul mati.** Judulnya "Kartu Sisa Mati", dan panel menampilkan perkiraan
kartu mana yang paling mungkin tidak pernah masuk permainan, lengkap dengan tingkat
kemungkinannya:

| Tampilan | Arti |
|---|---|
| Angka pada chip, mis. "5: ±1.8 mati" | perkiraan berapa kartu berangka 5 yang akan berakhir mati |
| Kartu berwarna merah tua | kemungkinan mati 50% atau lebih |
| Kartu berwarna oranye | kemungkinan mati 25% sampai 49% |
| Kartu biasa | kemungkinan mati di bawah 25% |

Perkiraan ini berasal dari simulasi pembagian kartu berulang yang menghormati data PASS
dan atribusi Anda. Bila belum ada hasil analisis, panel mengingatkan Anda untuk menjalankan
analisis lebih dulu.

## Panel hasil analisis

Panel ini menampilkan seluruh kandidat langkah, diurutkan, beserta alasannya. Strukturnya
dijelaskan satu per satu di Bagian V; di sini hanya pengantarnya:

- **Chip ringkasan** di judul: `PASS`, `Atribusi`, `Teliti`, dan `Cangkul n` —
  menandakan data apa yang benar-benar dipakai oleh hasil yang sedang tampil.
- **Kotak mode kartu pertama** bila papan masih kosong.
- **Panel Dominasi Angka**: hitungan tujuh angka di tangan Anda.
- **Kartu peringkat** untuk setiap kandidat langkah, masing-masing dengan peringkat
  (#1, #2, dan seterusnya), kartu, ujung baru yang dihasilkan, lencana, statistik, dan
  bar.
- **Kotak rekomendasi strategi** di paling bawah, berisi satu paragraf saran.

Bila tidak ada langkah valid, panel menampilkan panduan PASS: apa yang harus Anda lakukan
(menekan tombol PASS pada lawan, atau mencatat PASS Anda sendiri), dan mengapa hal itu
membuat analisis berikutnya jauh lebih akurat.

## Banner kualitas kartu

Setelah kartu tangan Anda terisi, muncul banner yang menilai kekuatan kartu Anda:

| Nilai | Syarat | Saran yang ditampilkan |
|---|---|---|
| **SANGAT BAGUS & BERUNTUNG** | ada angka yang Anda pegang 5 kali atau lebih | kuasai ujung dengan angka itu |
| **KARTU BAGUS** | ada angka yang Anda pegang 4 kali | modal bagus untuk mendominasi |
| **KARTU LUMAYAN** | ada angka yang Anda pegang 3 kali | cukup untuk mengontrol satu ujung |
| **KARTU JELEK (BANYAK BALAK)** | balak 4 buah atau lebih | buang balak secepatnya, siapkan strategi adu |
| **KARTU STANDAR** | selain di atas | buang kartu besar dan balak, siapkan adu |

Banner ini penilaian heuristik cepat berdasarkan kartu Anda sendiri; ia tidak memakai
simulasi. Angka yang lebih dapat dipercaya tetap berasal dari panel hasil analisis.

## Banner menang

Bila tangan Anda habis sementara sudah ada kartu di papan, muncul banner
**TANGAN HABIS — ANDA MENANG**. Ini murni pencatatan pencapaian; aplikasi tidak mengunci
apa pun, dan Anda bisa langsung menekan Reset untuk permainan berikutnya.

## Mode hidup, undo, dan pengelolaan sesi

**Mode hidup (LIVE).** Selama mode hidup aktif, analisis dijalankan ulang secara otomatis
setiap kali ada perubahan informasi: menambah atau menghapus kartu tangan, memainkan
kartu, mencatat PASS, menghapus PASS, dan bahkan membatalkan langkah lewat Undo. Bila
Anda melakukan beberapa aksi berturut-turut sementara analisis sebelumnya masih berjalan,
permintaan terbaru **diantrekan**, bukan ditumpuk sampai membebani komputer. Hasil yang
tampil selalu berasal dari data paling akhir.

Bila ingin menghentikan perhitungan yang sedang berjalan, tekan tombol yang sama sekali
lagi (teksnya "Jeda Live"): analisis yang sedang berjalan dibatalkan, dan bilah kemajuan
menampilkan "Live dijeda".

**Undo.** Setiap aksi yang mengubah keadaan menyimpan salinan keadaan sebelumnya ke
sebuah timeline berisi hingga 100 langkah terakhir. Satu kali tekan Undo memulihkan
salinan terakhir, sehingga:

- kartu yang Anda mainkan kembali ke tangan,
- kartu lawan yang tercatat kembali menjadi kartu sisa,
- PASS lawan yang terakhir dicatat hilang bersama eliminasi angkanya,
- atribusi kartu ikut dibatalkan.

Undo tidak bisa dipakai saat analisis sedang berjalan, supaya keadaan tidak berubah di
tengah perhitungan. Sesudah Undo, analisis dijalankan ulang agar panel hasil tidak
menampilkan angka basi.

<!--DIAGRAM:timeline-->

**Simpan otomatis.** Seluruh sesi disimpan ke penyimpanan lokal peramban setiap kali
keadaan berubah, dengan kunci `domino-analyzer-v3`. Menutup tab atau menyegarkan halaman
tidak menghilangkan data Anda.

**Export dan Import.** Tombol Export mengunduh berkas JSON bernama
`domino-analisis-TANGGAL.json` berisi pengaturan meja dan seluruh keadaan permainan.
Tombol Import membacanya kembali. Ini berguna untuk memindahkan sesi ke perangkat lain
atau menyimpan permainan yang menarik untuk dipelajari ulang.

Berkas impor **divalidasi ketat** sebelum diterima: setiap kartu harus berbentuk
`angka-angka` dengan angka 0 sampai 6, label pemilik kartu harus `me`, `unknown`, atau
`opp1` sampai `opp4`, dan data PASS harus berupa angka yang sah. Berkas yang tidak lolos
validasi ditolak dengan pesan "File bukan sesi Domino Analyzer v3 yang valid." Ini bukan
sekadar kerapian: berkas impor adalah data dari luar, dan aplikasi tidak boleh begitu saja
mempercayainya.

## Pesan kesalahan dan artinya

| Pesan di layar | Sebab | Tindakan |
|---|---|---|
| "Tidak bisa menghubungi server — apakah `python start.py` masih berjalan?" | server mati atau port berubah | jalankan ulang server |
| "Respons server tidak valid (HTTP ...)" | balasan bukan JSON | lihat log server; biasanya kesalahan internal |
| "engine belum di-build. Jalankan: python tools/build_engine.py" | biner mesin tidak ada (HTTP 503) | bangun mesin |
| "Kartu ... tidak dikenali" | kunci kartu tidak sah | pilih kartu dari daftar, jangan mengetik manual |
| "Kartu ... muncul dua kali" | kartu yang sama ada di tangan dan di papan | periksa kembali isian Anda |
| "Data atribusi tidak konsisten" | satu kartu ditandai milik dua lawan | perbaiki penandaan |
| "Kartu di tangan melebihi kartu per pemain!" | jumlah kartu tangan melampaui batas | hapus sebagian kartu atau ubah pengaturan |

Semua pesan kesalahan dirancang menjelaskan **apa yang harus dilakukan**, bukan
menampilkan kode teknis. Bagian IX memuat daftar lengkap kode HTTP yang mungkin muncul
bila Anda memakai API secara langsung.
