# Bagian II — Dasar Permainan Domino

Bagian ini menjelaskan aturan domino 28 kartu sebagaimana dipahami oleh aplikasi.
Tujuannya bukan menggantikan aturan rumah Anda, melainkan menyamakan istilah: apa yang
dimaksud "klik", "balak", "ujung", "PASS", "cangkul", dan "adu" di dalam seluruh buku
ini dan di seluruh antarmuka aplikasi.

## Kartu: 28 klik dari 0 sampai 6

Satu set domino yang dipakai aplikasi berisi 28 kartu. Setiap kartu punya dua sisi, dan
setiap sisi bernilai salah satu angka 0 sampai 6. Setiap pasangan angka muncul tepat
sekali, termasuk kartu yang kedua sisinya sama:

- kartu dengan dua angka berbeda: 21 buah, misalnya `2-5`, `0-6`, `3-4`;
- kartu dengan dua angka sama (disebut **balak**): 7 buah, yaitu `0-0`, `1-1`, `2-2`,
  `3-3`, `4-4`, `5-5`, `6-6`.

Totalnya 21 + 7 = 28 kartu. Karena itulah permainan ini disebut domino 28 kartu.

**Nilai mata** sebuah kartu adalah jumlah kedua angkanya: `6-6` bernilai 12, `2-5`
bernilai 7, `0-0` bernilai 0. Nilai mata dipakai untuk menentukan pemenang ketika
permainan berhenti sebelum ada yang habis kartunya (lihat bagian Adu di bawah).

Setiap angka 0 sampai 6 muncul tepat **tujuh kali** di seluruh set. Fakta sederhana ini
adalah dasar dari peta angka di aplikasi, dan alasan mengapa panel peta angka selalu
menjumlahkan angka yang di tangan Anda, angka yang sudah keluar, dan angka yang belum
diketahui menjadi tepat tujuh.

| Angka | Kartu yang mengandungnya | Jumlah |
|---|---|---|
| 0 | 0-0, 0-1, 0-2, 0-3, 0-4, 0-5, 0-6 | 7 |
| 1 | 0-1, 1-1, 1-2, 1-3, 1-4, 1-5, 1-6 | 7 |
| 2 | 0-2, 1-2, 2-2, 2-3, 2-4, 2-5, 2-6 | 7 |
| 3 | 0-3, 1-3, 2-3, 3-3, 3-4, 3-5, 3-6 | 7 |
| 4 | 0-4, 1-4, 2-4, 3-4, 4-4, 4-5, 4-6 | 7 |
| 5 | 0-5, 1-5, 2-5, 3-5, 4-5, 5-5, 5-6 | 7 |
| 6 | 0-6, 1-6, 2-6, 3-6, 4-6, 5-6, 6-6 | 7 |

Lebih dari setengah kartu (4 dari 7) mengandung angka 4, 5, atau 6. Ini sebabnya angka
besar cenderung "berat" dan mengapa membuang balak besar lebih awal sering merupakan
langkah yang baik.

## Meja: rantai dua ujung

Kartu yang sudah dimainkan membentuk **rantai** di meja. Rantai itu punya dua ujung: ujung
kiri dan ujung kanan. Sebuah kartu hanya boleh dimainkan bila salah satu angkanya sama
dengan salah satu angka di ujung rantai. Setelah dimainkan, angka yang tidak dipakai
untuk menyambung menjadi ujung baru di sisi itu.

Contoh sederhana. Misalkan rantai saat ini:

```text
[4|2] [2|6]        ujung kiri = 4, ujung kanan = 6
```

Kartu `6-1`, `6-3`, atau `6-6` bisa dimainkan ke ujung kanan (menyambung angka 6).
Kartu `4-0` atau `4-3` bisa dimainkan ke ujung kiri (menyambung angka 4). Balak `2-2`
tidak bisa dimainkan sekarang, karena angka 2 tidak ada di ujung mana pun.

Bila sebuah kartu cocok di **kedua** ujung sekaligus (misalnya di rantai di atas kartu
`4-6`), aplikasi tidak memilih sendiri. Muncul jendela **Pilih Ujung Papan** yang
menampilkan akibat masing-masing pilihan: "Kiri jadi X" dan "Kanan jadi Y". Ini penting,
karena arah penyambungan sering menjadi inti strategi.

**Kartu pertama.** Pada giliran pertama, meja masih kosong. Kartu apa pun boleh
dimainkan; kartu itu menjadi pusat rantai, dan kedua angkanya menjadi ujung kiri dan
ujung kanan sekaligus. Di papan aplikasi, kartu pertama ini diberi penanda emas dan
digambar **berdiri tegak** agar mudah ditemukan.

## PASS: ketika tidak bisa jalan

Bila tidak ada kartu di tangan yang bisa menyambung ke salah satu ujung, pemain harus
**PASS** (lewat). Bila semua pemain dalam satu putaran penuh PASS, permainan berhenti
karena **macet** (adu). Bila tidak ada yang habis dan permainan berhenti, pemenangnya
ditentukan dengan membandingkan nilai mata (lihat bagian Adu).

Untuk aplikasi, PASS lawan bukan sekadar catatan administratif — ini **bukti**. Bila
lawan melewati giliran saat ujung meja adalah angka 3 dan 1, maka dipastikan lawan
tersebut tidak memegang kartu berangka 3 **dan** tidak memegang kartu berangka 1. Karena
setiap angka hanya ada tujuh kartu, satu kejadian PASS bisa menghapus banyak kemungkinan
dari perhitungan. Bab tersendiri di Bagian IV menjelaskan cara mencatatnya.

## Cangkul: menyambar dari sisa

Pada banyak kelompok, kartu yang tidak dibagikan tetap tersedia di tengah meja dan boleh
disambar ketika pemain tidak bisa jalan. Mekanik ini disebut **cangkul**. Pemain yang
PASS mengambil kartu dari sisa sampai menemukan kartu yang bisa dimainkan, atau sampai
sisanya habis.

Jumlah kartu sisa ditentukan oleh pembagian: 28 kartu dikurangi (jumlah pemain x jumlah
kartu per pemain).

| Pemain | Kartu/pemain | Dibagikan | Sisa (cangkul) |
|---|---|---|---|
| 2 | 7 | 14 | 14 |
| 3 | 7 | 21 | 7 |
| 4 | 7 | 28 | 0 |
| 4 | 6 | 24 | 4 |
| 3 | 5 | 15 | 13 |

Bila tidak ada sisa (misalnya 4 pemain x 7 kartu), permainan berjalan tanpa cangkul.
Aplikasi mendukung dua perilaku yang bisa dipilih di panel Setup:

- **Ya — sisa bisa disambar**: pemain yang PASS menarik kartu sisa dan kartu itu masuk
  kembali ke perhitungan.
- **Tidak — sisa mati**: kartu sisa tidak pernah masuk permainan. Aplikasi lalu
  menghitung **kartu sisa mana yang paling mungkin mati** dan menampilkannya di panel
  Kartu Sisa, dengan warna berbeda sesuai tingkat kemungkinannya.

## Adu: ketika meja macet

**Adu** (deadlock) terjadi ketika permainan berhenti karena tidak ada lagi langkah yang
bisa diambil semua pemain, dan tidak ada kartu sisa untuk disambar. Tidak ada yang habis
kartunya, sehingga pemenang ditentukan dari nilai mata.

Aplikasi menyediakan dua konvensi pembandingan, dan keduanya umum dipakai berbeda-beda
di lapangan:

| Konvensi | Aturan | Catatan pemakaian |
|---|---|---|
| **Mata terkecil** | nilai mata Anda dibandingkan dengan nilai mata **terkecil** di antara lawan; lebih kecil menang | umum di banyak kelompok gaple; hukuman untuk tangan berat |
| **Rata-rata** | nilai mata Anda dibandingkan dengan **rata-rata** nilai mata semua lawan | lebih toleran bila ada satu lawan yang tersisa sangat berat |

Selain itu ada pilihan perilaku saat **seri** (nilai mata sama dengan pembanding):
dihitung **menang** atau **kalah**. Pilihan ini terlihat sepele, tetapi mengubah
perhitungan secara nyata, dan aplikasi memakainya secara konsisten di dalam simulasi
maupun di laporan "menang lewat adu" pada panel hasil.

> Mengapa konvensi ini penting? Bila aturan meja Anda adalah "terkecil menang" tetapi
> aplikasi disetel "rata-rata", seluruh angka peluang menang akan menyimpang, dan
> rekomendasi kartu bisa berubah urutan. Setel konvensi meja **sebelum** mulai mencatat.

## Jumlah pemain dan arah giliran

Aplikasi mendukung 2, 3, dan 4 pemain. Aturan kartu per pemain mengikuti pembagian yang
wajar: maksimum 14 kartu untuk 2 pemain, 9 kartu untuk 3 pemain, dan 7 kartu untuk
4 pemain (aplikasi membulatkan ke bawah: 28 dibagi jumlah pemain).

Yang sering dilupakan: **urutan giliran memengaruhi hasil**. Bila Anda bermain dan lawan
yang bermain tepat setelah Anda adalah lawan yang menahan angka tertentu, hasilnya
berbeda dibandingkan bila yang bermain setelah Anda adalah lawan yang lemah di angka
itu. Karena itu aplikasi punya pilihan **Main Setelah Saya** di panel Setup. Pilihan ini
dipakai dua kali oleh mesin:

1. di dalam simulasi, urutan giliran disusun sesuai pilihan tersebut;
2. pada mode **teliti**, lawan yang bermain tepat setelah Anda-lah yang diberi permainan
   ketat (tanpa derau), karena dialah yang paling menentukan kelanjutan langkah Anda.

## Istilah ringkas

| Istilah | Arti di aplikasi ini |
|---|---|
| Klik / kartu | satu keping domino dengan dua angka, ditulis `a-b` |
| Balak | kartu dengan dua angka sama, misalnya `5-5` |
| Nilai mata | jumlah kedua angka sebuah kartu atau sebuah tangan |
| Ujung | angka bebas di kiri dan/atau kanan rantai meja |
| PASS / lewat | tidak ada kartu yang bisa dimainkan |
| Cangkul | menyambar kartu sisa setelah PASS |
| Sisa mati | kartu sisa yang tidak pernah masuk permainan |
| Adu | permainan berhenti, pemenang ditentukan nilai mata |
| Dominasi | angka yang Anda kuasai (muncul 3 kali atau lebih di tangan) |
| Jerat | menyisakan angka dominan di ujung agar lawan terpaksa membuka jalan Anda |
| Kunci | meninggalkan ujung yang hanya Anda miliki aksesnya |
| Atribusi | menandai kartu di papan sebagai milik lawan tertentu |
| Win rate | persentase kemenangan dari simulasi untuk sebuah langkah |
| Interval keyakinan | rentang tempat nilai sebenarnya kemungkinan besar berada |

Bagian III akan menuntun Anda memasang dan menjalankan aplikasi.
