# Bagian VIII — Panduan Strategi

Bagian ini adalah sisi manusiawi dari aplikasi: bagaimana memakai informasi yang
dihitung mesin untuk benar-benar memenangkan permainan. Semua saran di sini sejalan
dengan apa yang dihitung mesin, tetapi disampaikan sebagai prinsip yang bisa Anda bawa ke
meja tanpa membuka layar.

## Empat prinsip dasar

**Prinsip 1: kuasai satu angka, bukan tujuh kartu.** Kemenangan domino jarang datang dari
kartu besar. Ia datang dari **angka** yang Anda kuasai. Bila Anda memegang empat kartu
berangka 5, maka setiap kali ujung meja 5, Anda punya jalan keluar dan lawan sangat
mungkin tidak. Karena itu: hitung angka, bukan nilai mata — kecuali permainan mendekati
adu.

**Prinsip 2: ujung adalah alat, bukan sekadar tempat menaruh kartu.** Dua angka di ujung
meja adalah satu-satunya kendali yang Anda punya atas langkah lawan. Setiap kali Anda
memilih ujung, Anda sedang memilih **soal** yang harus dijawab lawan.

**Prinsip 3: informasi adalah mata uang.** Satu PASS lawan bernilai lebih dari satu kartu
bagus. Karena itu, disiplin mencatat PASS dan atribusi kartu memberi keuntungan lebih
besar daripada menambah jumlah simulasi.

**Prinsip 4: jangan mengadu kecuali Anda ringan.** Bila permainan macet, pemenangnya
ditentukan nilai mata. Tangan berat harus berusaha membuka permainan; tangan ringan justru
diuntungkan oleh kemacetan.

## Mendominasi ujung

Angka yang Anda pegang tiga kali atau lebih disebut **dominan** (aplikasi menandainya di
banner kualitas dan di panel dominasi). Dengan angka dominan, tujuan Anda adalah membuat
angka itu muncul di ujung meja dan **mempertahankannya** di sana.

Mengapa? Karena lawan yang menyambung ke angka dominan Anda justru membantu Anda: rantai
kembali ke angka Anda, dan Anda punya kartu untuk melanjutkannya. Sebaliknya, lawan yang
tidak bisa menyambung harus PASS — dan itu bukti tambahan bahwa angka itu milik Anda.

Situasi terbaik yang bisa Anda capai: **kedua ujung meja adalah angka dominan Anda**.
Mesin menghitung ini secara khusus dan memberi bonus besar (`domSupportScore` bernilai 30
untuk kondisi "kedua ujung"), karena lawan kini harus menjawab dengan angka yang Anda
kendalikan dari dua arah. Bila panel hasil menampilkan lencana dominasi dengan kalimat
"KEDUA UJUNG dikuasai angka X", itu lencana yang layak diperjuangkan.

## Jerat: membuat lawan membuka jalan Anda

Jerat adalah langkah yang menyisakan angka **dominan Anda** di ujung sementara masih ada
kartu berangka itu di luar (di tangan lawan atau sisa). Logikanya: siapa pun yang
menyambung ke angka itu terpaksa mengeluarkan kartu berangka tersebut, sehingga
persediaan lawan berkurang dan Anda semakin menguasai angka itu.

Mesin menandai jerat dengan `trapScore` dan alasan seperti
"JERAT angka 6 terpasang! 4 kartu 6 masih di luar." Jerat bernilai tinggi bila kartu di
luar banyak, karena setiap kartu yang keluar memperkecil peluang lawan bertahan.

Perhatikan bedanya dengan kesalahan yang mirip: menyisakan angka di ujung yang **bukan**
milik Anda. Mesin memakai `selfTrapScore` untuk memperingatkan kondisi itu — contoh nyata
di Bagian V menunjukkan kartu dengan win rate lebih tinggi justru kalah peringkat karena
menyisakan ujung yang berbahaya bagi diri sendiri.

## Kunci: menutup jalan lawan

Bila peta angka menunjukkan sebuah angka sudah **tidak ada lagi** di luar (tidak di tangan
Anda dan tidak di papan), maka angka itu mati: tidak ada yang bisa menyambungnya. Membuat
angka mati itu menjadi ujung berarti meja macet di sisi tersebut.

Kondisi paling kuat muncul ketika angka itu habis dari peredaran **tetapi Anda masih
memegang kartunya**. Mesin menyebut ini "KUNCI" (`blockScore` 25) karena hanya Anda yang
punya akses. Bagi lawan, ujung itu adalah jalan buntu.

```text
Peta angka:
  3:  di tangan saya 2, sudah keluar 5, sisa 0
      -> angka 3 habis dari peredaran
Meja : ujung kiri = 3
Anda : punya kartu 3-6
Artinya: Anda memegang satu-satunya akses ke ujung kiri.
```

**Blok terjamin.** Bila Anda sudah mencatat PASS lawan, mesin bisa menyatakan lebih tegas
lagi: "Lawan 2 PASTI tidak bisa main (tidak punya 3 maupun 1)". Ini berlaku keras karena
didasarkan pada bukti, bukan perkiraan. Langkah seperti ini biasanya menjadi alasan
peringkat #1 meskipun win rate-nya bukan yang tertinggi, karena lawan yang mati berarti
giliran kembali ke Anda.

## Adu: bermain dengan sisa mata

Adu bukan kegagalan permainan; ia adalah akhir permainan yang berbeda, dengan aturan
penilaian yang berbeda. Tiga hal yang perlu Anda ingat:

1. **Setel konvensi meja lebih dulu.** "Mata terkecil" dan "rata-rata" memberi hasil
   berbeda, dan pilihan "seri = menang/kalah" juga berpengaruh. Aplikasi memakai pilihan
   Anda secara konsisten.
2. **Nilai mata terkecil menang.** Karena itu, bila permainan mengarah ke adu, kartu besar
   adalah beban. Membuang balak besar lebih awal adalah investasi.
3. **Paksa macet bila Anda ringan.** Bila nilai mata tangan Anda kecil, permainan macet
   menguntungkan Anda. Mesin menampilkan bar "Menang lewat ADU" untuk setiap langkah
   sehingga Anda bisa melihat langkah mana yang paling mendorong skenario itu.

Balak punya peran khusus di sini: balak bernilai dua kali angkanya (`6-6` = 12, yang
terbesar di set), jadi banyak balak berarti adu yang buruk. Penilaian kualitas kartu di
antarmuka secara eksplisit menandai tangan dengan empat balak atau lebih sebagai "KARTU
JELEK (BANYAK BALAK)" dengan saran membuang balak cepat-cepat.

## Cangkul: menyambar dengan sadar biaya

Cangkul mengubah perhitungan secara mendasar, karena kartu sisa bisa berpindah tangan.
Dua hal yang sering dilupakan:

- **Kartu sisa memperpanjang permainan.** Setiap kali seseorang menyambar, jumlah kartu
  tersembunyi berkurang dan informasi Anda bisa berubah. Catat atribusi setiap sambaran
  yang Anda lihat; itu menghapus kartu dari kolam kemungkinan lawan.
- **Bila cangkul mati, kartu sisa justru aset strategis.** Kartu di sisa tidak akan pernah
  keluar. Bila sisa memuat banyak kartu berangka tertentu, angka itu menjadi langka di
  permainan nyata — dan itu berarti meja lebih mudah macet, sehingga peluang adu lebih
  tinggi. Panel "Kartu Sisa Mati" menampilkan perkiraan ini per angka.

## Menyesuaikan diri dengan gaya lawan

Mesin mensimulasikan tiga gaya lawan supaya rekomendasinya tidak bergantung pada satu
pola main. Anda bisa memakai ketiga gaya itu sebagai kacamata membaca manusia di meja.

| Gaya | Ciri di meja | Yang harus Anda lakukan |
|---|---|---|
| **Blocker** (penahan) | sering menyisakan ujung yang sepi, suka membuat orang PASS | buka jalur alternatif; jangan bergantung pada satu ujung |
| **Hoarder** (penimbun) | menyimpan kartu dari angka kuatnya, lambat membuang | jangan menyerahkan ujung ke angka kuatnya; paksa dia membuang |
| **Dumper** (pembuang) | cepat membuang kartu besar dan balak | dia akan habis cepat, jadi percepat jalur Anda sendiri; siapkan adu bila ragu |

Bila salah satu lawan bermain persis seperti **penahan**, aktifkan mode **teliti**. Mode
itu membuat lawan yang bermain tepat setelah Anda membalas dengan permainan ketat, bukan
dengan pilihan acak, sehingga estimasi Anda lebih konservatif dan lebih dekat kenyataan.

## Rutinitas satu langkah

Inilah kebiasaan yang membuat pemakaian aplikasi benar-benar menguntungkan. Lakukan empat
langkah ini setiap giliran; total waktunya di bawah sepuluh detik setelah terbiasa.

1. **Perbarui data dulu, jangan langsung lihat hasil.** Sebelum memutuskan, pastikan semua
   yang sudah terjadi sudah tercatat: kartu lawan yang Anda lihat, dan PASS lawan. Analisis
   yang dihitung dari data lama adalah analisis yang salah.
2. **Baca tiga hal di panel hasil:** peringkat #1, rentang keyakinannya, dan alasan yang
   tertulis. Bila #1 dan #2 punya selang yang saling menumpuk, anggap keduanya sama baik.
3. **Periksa bar "Keamanan Putaran 2"** (muncul di mode kartu pertama). Langkah dengan
   win rate tinggi tetapi keamanan nol akan membuat Anda PASS di putaran kedua.
4. **Cocokkan dengan akal sehat.** Bila rekomendasi bertentangan dengan pengamatan meja
   Anda (misalnya leluhur lawan selalu menyimpan angka tertentu), percayai meja — lalu
   perbaiki data yang Anda masukkan, karena hampir selalu penyebabnya adalah data yang
   kurang lengkap.

## Kesalahan umum dan cara menghindarinya

| Kesalahan | Akibat | Perbaikan |
|---|---|---|
| Menandai PASS "untuk berjaga-jaga" | simulasi menghormati bukti palsu; rekomendasi menyimpang | tandai PASS hanya bila benar-benar terlihat |
| Lupa mencatat kartu lawan | profil lawan menyesatkan, kemungkinan kartu tidak menyempit | catat setiap kartu lawan yang bisa Anda atribusikan |
| Salah jumlah kartu per pemain | jumlah kartu tersembunyi dan sisa tidak sinkron | cek baris keterangan di panel Setup |
| Memakai 1000 simulasi lalu memercayai selisih 2% | derau statistik dianggap sinyal | naikkan ke 10.000, atau lihat interval keyakinan |
| Mengubah pengaturan meja di tengah permainan | hasil sebelum dan sesudah tidak bisa dibandingkan | setel aturan sebelum mencatat |
| Mengabaikan mode kartu pertama | kartu buka yang buruk membuat putaran kedua macet | baca bar keamanan putaran 2 sebelum membuka |
| Menimpa sesi berharga dengan Reset | data hilang | tekan Export dulu sebelum Reset |

## Membaca situasi dengan cepat

Tiga pertanyaan yang bisa Anda ajukan ke peta angka dalam hitungan detik:

1. **Apakah angka di ujung masih hidup?** Bila "sisa 0" dan tidak ada di tangan Anda,
   ujung itu mati untuk semua orang — permainan akan macet.
2. **Apakah saya memegang angka yang sudah langka?** Semakin kecil "sisa", semakin besar
   nilai kartu Anda di angka itu.
3. **Apakah lawan kehabisan kartu berangka tertentu?** Lihat panel lawan: angka yang
   tertulis "pasti tidak punya" tidak akan pernah muncul dari lawan itu. Bila angka itu
   adalah satu-satunya penghubung, arahkan permainan ke sana.

Dengan tiga pertanyaan itu saja, Anda sudah memakai kekuatan utama aplikasi ini tanpa
harus membaca satu pun angka statistik. Sisanya adalah memperhalus keputusan, dan itu
tugas Bagian V.
