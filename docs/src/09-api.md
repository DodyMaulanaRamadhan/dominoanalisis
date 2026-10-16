# Bagian IX — Rujukan API

Bagian ini ditujukan untuk siapa pun yang ingin memakai aplikasi ini dari skrip, alat
monitoring, atau integrasi lain. Seluruh API berbasis JSON sederhana: kirim objek,
terima objek.

## Aturan dasar

| Aspek | Ketentuan |
|---|---|
| Alamat dasar | `http://127.0.0.1:2024` (bawaan) |
| Format isi | `application/json` — **wajib**; tipe isi lain ditolak dengan 400 |
| Asal permintaan | bila header `Origin` dikirim, harus sama dengan `Host`; selain itu ditolak 400 |
| Ukuran maksimum isi | 1 MiB |
| Autentikasi | hanya bila `APP_TOKEN` diisi: header `X-App-Token` pada semua `POST /api/*` |
| Token pembanding | waktu-konstan (`hmac.compare_digest`) |
| Batas beban | `numSims` antara 1 dan 1700000; mesin dihentikan bila melewati 300 detik |
| Header balasan | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, CSP ketat |
| Tempat singgahan | balasan API `Cache-Control: no-store`; berkas statis `no-cache` |

## Daftar endpoint

| Metode | Jalur | Kegunaan |
|---|---|---|
| GET | `/` atau `/index.html` | antarmuka web |
| GET | `/<berkas>` | berkas statis dari folder `web/` |
| GET | `/api/health` | status server dan kesiapan mesin |
| POST | `/api/analyze` | analisis Monte-Carlo untuk seluruh kandidat langkah |
| POST | `/api/selftest` | menjalankan sebelas pemeriksaan mandiri mesin |
| POST | `/api/meta` | daftar kartu yang belum terlihat (tidak di tangan, tidak di papan) |
| — | `/api/...` lain | 404, `{"ok": false, "error": "endpoint tidak dikenal"}` |
| GET | `/api/meta` | 405, karena endpoint ini hanya menerima POST |

## GET /api/health

Tidak butuh isi. Berguna untuk memeriksa kesiapan sebelum mengirim permintaan berat.

```bash
curl -s http://127.0.0.1:2024/api/health
```

```json
{
  "ok": true,
  "server": "python",
  "version": 3,
  "engine": "domino_engine.exe",
  "engineReady": true,
  "tokenRequired": false
}
```

| Bidang | Arti |
|---|---|
| `engine` | nama berkas mesin, atau `null` bila belum dibangun |
| `engineReady` | `false` berarti analisis akan dijawab 503 |
| `tokenRequired` | `true` berarti `APP_TOKEN` aktif dan header token wajib |

## POST /api/meta

Menghitung kartu yang belum diketahui: 28 kartu dikurangi kartu di tangan Anda dan kartu
yang sudah di papan. Kunci kartu pada masukan akan dinormalkan seperti biasa.

```bash
curl -s -X POST http://127.0.0.1:2024/api/meta \
  -H 'Content-Type: application/json' \
  -d '{"myHand":["6-1","0|0"],"played":[]}'
```

```json
{"ok": true, "remaining": ["0-1","0-2","0-3","...","6-6"]}
```

Endpoint ini selalu mengembalikan 28 kartu bila tangan dan papan kosong. Balasannya tidak
pernah memuat kartu mustahil (seperti `0-7`) — hal itu pernah menjadi cacat dan sudah
diperbaiki serta dijaga oleh uji `meta_only_real_tiles`.

## POST /api/analyze — permintaan

### Bidang yang wajib

| Bidang | Tipe | Batasan | Arti |
|---|---|---|---|
| `numPlayers` | angka | 2, 3, atau 4 | jumlah pemain di meja, termasuk Anda |
| `cardsPerPlayer` | angka | 1 sampai 14, dan `numPlayers x cardsPerPlayer` tidak boleh melebihi 28 | kartu yang dibagikan ke setiap pemain |
| `myHand` | larik kunci kartu | tidak boleh berisi duplikat, tidak boleh tumpang tindih dengan `played` | kartu di tangan Anda |
| `played` | larik kunci kartu | idem | kartu yang sudah masuk papan, urut kronologis |

### Bidang opsional

| Bidang | Tipe | Bawaan | Arti |
|---|---|---|---|
| `numSims` | angka | 10000 | jumlah simulasi per kandidat langkah (1 sampai 1700000) |
| `seed` | angka | 42 | seed pembangkit acak; aplikasi web memakai 20240922 |
| `leftEnd` / `rightEnd` | angka | −1 | angka di ujung kiri dan kanan papan; −1 berarti papan kosong |
| `playedBy` | larik label | semua `"unknown"` | pemilik setiap kartu di `played`; panjangnya **harus sama**; nilai sah: `"me"`, `"unknown"`, `"opp1"` sampai `"opp4"` |
| `nextSeat` | angka | 1 | indeks pemain yang bermain setelah Anda (0 berarti Anda sendiri) |
| `deadlockRule` | teks | `"lowest"` | `"lowest"` (mata terkecil) atau `"average"` (rata-rata) |
| `tieRule` | teks | `"win"` | `"win"` atau `"lose"` untuk nilai mata yang seri |
| `cangkul` | boolean | `true` | apakah kartu sisa boleh disambar |
| `adversarial` | boolean | `false` | mode teliti: lawan yang bermain setelah Anda bermain tanpa derau |
| `opponents` | larik objek | kosong | satu objek per lawan, berurutan; lihat di bawah |

### Tier akurasi `numSims` (varians maksimum, p = 0,5)

| Tingkat kepercayaan | Margin of error | Jumlah simulasi minimal | Tier di aplikasi |
|---|---|---|---|
| 95% | ±3,1% | ~1.000 | 1.000 (cepat) |
| 95% | ±1,4% | ~5.000 | 5.000 |
| 95% | ±1,0% | 9.604 (≈10 ribu) | 10.000 (bawaan) |
| 95% | ±0,44% | ~50.000 | 50.000 |
| 95% | ±0,1% | 960.400 (≈1 juta) | dicakup oleh tier 1.700.000 |
| 99% | ±0,1% | 1.664.100 (≈1,7 juta) | 1.700.000 (dengan peringatan; lihat bab antarmuka) |
| 99% | ±0,01% | 166.410.000 (≈166 juta) | tidak ditawarkan — berjam-jam per permintaan |

Rumus: N = Z² × p(1−p) / E², dengan Z = 1,96 (95%) atau 2,58 (99%).
Pada mesin uji (6 inti fisik / 12 utas logis) mesin mengerjakan ~0,6–1,4 juta
simulasi-langkah per detik (lihat `tools/bench_engine.py`), sehingga tier 1.700.000
memakan **7 detik** untuk 3 kandidat langkah dan **~30 detik** untuk 12 kandidat
langkah; efisiensi paralelnya 87% dari 6 inti fisik. Karena itu tier
ini tidak berjalan otomatis: antarmuka meminta konfirmasi, mematikan mode Live,
dan menyediakan tombol Batal yang benar-benar menghentikan proses mesin.

### Bentuk objek lawan

```json
{"passes": 1, "eliminated": [3, 1]}
```

| Bidang | Arti |
|---|---|
| `passes` | jumlah PASS yang tercatat untuk lawan ini (dipakai antarmuka untuk menampilkan riwayat) |
| `eliminated` | daftar angka 0-6 yang **dipastikan tidak dipegang** lawan ini, hasil pencatatan PASS |

Angka pada `eliminated` menjadi batasan keras di dalam simulasi: kartu yang mengandung
angka tersebut tidak akan pernah dibagikan ke lawan itu, kecuali kuota kartunya mustahil
dipenuhi tanpa melanggar (dalam hal itu batasannya dilepas dan kejadiannya dihitung
sebagai *fallback*).

### Format kunci kartu

| Ditulis | Diterima menjadi |
|---|---|
| `3-5`, `3|5`, `3:5`, `3.5`, `3 5`, `35` | `3-5` |
| `6-1`, `6|1`, `61` | `1-6` (selalu angka kecil lebih dulu) |
| `7-1`, `a-b`, `1-2-3`, kosong, angka bukan teks | ditolak: 400 dengan pesan yang menyebut posisi elemen |

> Bila Anda memanggil **mesin** secara langsung (bukan lewat server), normalisasi ini tidak
> terjadi: mesin hanya menerima bentuk kanonik. `"6-3"` akan ditolak dengan
> `invalid tile key: 6-3`.

## POST /api/analyze — balasan

Balasan berisi dua bagian: **ringkasan permintaan** (supaya Anda bisa memastikan mesin
memahami apa yang Anda maksud) dan **daftar langkah**.

```json
{
  "ok": true,
  "engine": "domino-cpp/3.0.0",
  "numPlayers": 4, "cardsPerPlayer": 7, "numSims": 500, "seed": 20240922,
  "leftEnd": 3, "rightEnd": 1, "nextSeat": 1,
  "adversarial": false, "deadlockRule": "lowest", "tieRule": "win", "cangkul": true,
  "isFirstMove": false, "hasPassData": true, "hasAttribution": true,
  "unknownCount": 20, "totalOppCards": 20, "boneyardCount": 0, "validMoveCount": 3,
  "opponents": [ ... ],
  "moves": [ ... ],
  "deadTiles": [ ... ],
  "deadByNumber": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
}
```

| Bidang ringkasan | Arti |
|---|---|
| `engine` | versi mesin yang menjawab |
| `isFirstMove` | `true` bila papan masih kosong (mode kartu pertama) |
| `hasPassData` | `true` bila ada data PASS yang dipakai |
| `hasAttribution` | `true` bila ada kartu yang diatribusikan ke lawan |
| `unknownCount` | jumlah kartu yang belum diketahui (belum di tangan, belum di papan) |
| `totalOppCards` | perkiraan jumlah kartu yang ada di tangan semua lawan |
| `boneyardCount` | jumlah kartu sisa/cangkul menurut pembagian |
| `validMoveCount` | jumlah kandidat langkah yang sah |

### Bidang setiap langkah (`moves[]`)

| Bidang | Arti |
|---|---|
| `key`, `a`, `b` | kartu kandidat |
| `side` | `"left"`, `"right"`, atau `"first"` |
| `newLeft`, `newRight` | ujung papan setelah langkah ini dimainkan |
| `wins`, `losses`, `numSims` | jumlah menang, kalah, dan total simulasi |
| `winRate` | peluang menang (0 sampai 1) |
| `winLo`, `winHi` | batas bawah dan atas interval keyakinan Wilson 95% |
| `rankScore` | nilai peringkat gabungan (lihat Bagian V) |
| `avgMyVal` | rata-rata nilai mata di tangan Anda saat gim berakhir |
| `avgOppMinVal` | rata-rata nilai mata lawan terendah saat gim berakhir |
| `flexibility` | berapa kartu sisa yang masih bisa disambungkan setelah langkah ini |
| `blockedGames`, `blockRate` | berapa sering gim berakhir macet |
| `deadlockWins`, `deadlockWinRate` | kemenangan yang diperoleh lewat adu |
| `winByEmpty`, `winByValue`, `winByEmptyRate` | menang karena kartu habis vs menang karena nilai mata |
| `riskScore` | seberapa sering kartu berbahaya muncul pada gim yang kalah |
| `topDanger` | lima kartu berbahaya: `[{"key": "3-5", "freq": 0.96}]` |
| `avgOppPasses` | rata-rata berapa kali lawan PASS per gim |
| `avgDraws` | rata-rata jumlah sambaran cangkul per gim |
| `avgDomControl` | rata-rata berapa kali angka dominan Anda berada di ujung |
| `conserved` | `true` bila konservasi kartu terjaga selama simulasi langkah ini |
| `domSupportScore`, `domSupportReasons` | penilaian dan alasan dukungan dominasi |
| `trapScore`, `trapReasons` | penilaian dan alasan jerat |
| `blockScore`, `blockReasons` | penilaian dan alasan kunci |
| `selfTrapScore` | penilaian jebakan untuk diri sendiri |
| `guaranteedBlocks` | blok terjamin: `[{"opp": 2, "reason": "Lawan 2 PASTI tidak bisa main (...)"}]` |
| `firstMoveSafety` | hanya pada mode kartu pertama; berisi `canPlayNext`, `totalRemaining`, `safetyRatio`, `canPlayKeys`, `cannotPlayKeys` |

Daftar `moves[]` sudah terurut menurun menurut `rankScore`, dan sifat ini dijaga oleh
pemeriksaan mandiri nomor 7.

### Bidang setiap lawan (`opponents[]`)

| Bidang | Arti |
|---|---|
| `handSize` | perkiraan jumlah kartu tersembunyi di tangan lawan itu |
| `poolSize` | jumlah kartu yang masih mungkin ia pegang setelah semua batasan |
| `passElimCount` | berapa angka yang tereliminasi dari PASS lawan ini |
| `heldKnown` | berapa kartu yang sudah dipastikan miliknya lewat atribusi Anda |
| `doublesExpected` | perkiraan jumlah balak di tangannya |
| `dominant` | dua angka teratas: `[{"num": 5, "expected": 6.0, "pct": 100.0}]` |

### Kartu sisa mati

`deadTiles` dan `deadByNumber` **hanya ada** bila masih ada kartu tersembunyi. Bila semua
kartu sudah diketahui, kedua bidang itu tidak dikirim.

| Bidang | Arti |
|---|---|
| `deadTiles` | daftar kartu beserta peluang berakhir di sisa: `[{"key":"5-6","a":5,"b":6,"prob":0.42}]`, terurut menurun |
| `deadByNumber` | larik tujuh angka: perkiraan jumlah kartu mati untuk angka 0 sampai 6 |

## POST /api/selftest

Menjalankan pemeriksaan mandiri mesin. Isi boleh objek kosong.

```bash
curl -s -X POST http://127.0.0.1:2024/api/selftest \
  -H 'Content-Type: application/json' -d '{}'
```

```json
{
  "ok": true,
  "engine": "domino-cpp/3.0.0",
  "allPass": true,
  "checks": [
    {"name": "deck_28_kartu", "pass": true, "detail": "28 tile unik 0-0 .. 6-6"},
    {"name": "interval_wilson", "pass": true, "detail": "w=346/500 -> 0.650..0.731, lebar menyempit saat n naik"}
  ]
}
```

Bila `allPass` bernilai `false`, status HTTP yang dikirim adalah **500** — kegagalan
pemeriksaan mandiri adalah masalah mesin, bukan kesalahan permintaan.

## Contoh lengkap dengan curl

Contoh ini mereproduksi persis contoh di Bagian V.

```bash
curl -s -X POST http://127.0.0.1:2024/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "numPlayers": 4, "cardsPerPlayer": 7, "numSims": 500, "seed": 20240922,
    "leftEnd": 3, "rightEnd": 1,
    "myHand": ["6-6", "3-6", "2-3", "1-5", "4-4"],
    "played": ["0-3", "0-2", "1-2"],
    "playedBy": ["opp1", "opp2", "opp1"],
    "nextSeat": 1, "deadlockRule": "lowest", "tieRule": "win", "cangkul": true,
    "opponents": [{"passes": 1, "eliminated": [3, 1]}, {"passes": 0, "eliminated": []},
                  {"passes": 0, "eliminated": []}]
  }' | python -c "import json,sys; d=json.load(sys.stdin);
print([[m['key'], round(m['winRate']*100,1), round(m['winLo']*100,1), round(m['winHi']*100,1), m['rankScore']] for m in d['moves']])"
```

Keluaran yang diharapkan (persis seperti contoh di Bagian V):

```text
[['3-6', 69.2, 65.0, 73.1, 84.155], ['2-3', 71.2, 67.1, 75.0, 60.444], ['1-5', 60.0, 55.6, 64.2, 51.285]]
```

Contoh dengan token:

```bash
APP_TOKEN=rahasia python server/domino_server.py     # jendela server
curl -s -X POST http://127.0.0.1:2024/api/analyze \
  -H 'Content-Type: application/json' -H 'X-App-Token: rahasia' \
  -d '{"numPlayers":2,"cardsPerPlayer":7,"myHand":["0-0"],"played":[]}'
```

## Kode kesalahan

Setiap kesalahan dikirim sebagai objek JSON dengan `ok: false` dan pesan `error` dalam
bahasa Indonesia yang bisa dibaca manusia.

| Status | Pesan contoh | Penyebab |
|---|---|---|
| 400 | `body JSON tidak valid` | tipe isi bukan JSON, isi kosong, terlalu besar, atau JSON rusak |
| 400 | `myHand/played: format kartu tidak dikenal (elemen ke-2)` | kunci kartu tidak sah |
| 400 | `ada kartu duplikat di myHand` | kartu yang sama dua kali |
| 400 | `kartu tidak bisa di tangan dan di papan sekaligus` | tumpang tindih antara `myHand` dan `played` |
| 400 | `numSims harus angka 1..1700000` | batas beban dilanggar |
| 400 | `nextSeat harus angka 0..3` | indeks pemain di luar batas |
| 400 | `playedBy hanya boleh 'me', 'unknown', atau 'opp1'..'opp4'` | label pemain tidak dikenal |
| 400 | `tieRule harus 'win' atau 'lose'` | nilai aturan tidak dikenal (ditolak mesin) |
| 401 | `token tidak valid atau hilang (header X-App-Token)` | `APP_TOKEN` aktif dan token salah |
| 404 | `endpoint tidak dikenal` | jalur `/api/...` tidak ada |
| 405 | `gunakan POST untuk /api/meta` | metode salah |
| 500 | `engine error (exit 3) — detail ada di log server` | mesin gagal berjalan; detail hanya di log |
| 502 | `engine menghasilkan output tidak valid` | mesin berjalan tetapi keluarannya bukan JSON |
| 503 | `engine belum di-build. Jalankan: python tools/build_engine.py` | biner mesin tidak ada |
| 504 | `engine timeout (>300s)` | permintaan melebihi 300 detik |

Prinsip yang dijaga oleh pengujian: **`ok: false` selalu berpasangan dengan status bukan
200.** Klien boleh memutuskan berdasarkan kode status saja.

## Memanggil mesin langsung

Mesin bisa dipakai tanpa server sama sekali — berguna untuk pengujian dan skrip batch.

```bash
echo '{"cmd":"analyze","numPlayers":2,"cardsPerPlayer":7,"numSims":200,"seed":1,
       "leftEnd":-1,"rightEnd":-1,"myHand":["0-0","1-2"],"played":[],
       "opponents":[{}]}' | ./bin/domino_engine          # Linux/macOS
```

```powershell
'{"cmd":"selftest"}' | .\bin\domino_engine.exe            # Windows PowerShell
```

| Aspek | Perilaku |
|---|---|
| Perintah | `"cmd": "analyze"` (bawaan) atau `"cmd": "selftest"` |
| Masukan | satu objek JSON dari masukan standar |
| Keluaran | satu objek JSON ke keluaran standar, diakhiri baris baru |
| Kode keluar | selalu 0; kesalahan dilaporkan sebagai `ok:false` di dalam JSON |
| Normalisasi kartu | **tidak ada** — kunci harus sudah kanonik (`3-6`, bukan `6-3`) |
| Validasi | tetap ketat; `numSims` dibatasi 1 sampai 1700000 di dalam mesin |
| Batas waktu | tidak ada; pemanggil yang menentukan (server memakai 300 detik) |

Karena kode keluarnya selalu 0, **jangan** menyimpulkan keberhasilan dari kode keluar saja.
Periksa bidang `ok` di dalam balasan. Server sudah melakukan hal itu: ia memetakan
`ok:false` dari mesin menjadi status HTTP 400, bukan 200.
