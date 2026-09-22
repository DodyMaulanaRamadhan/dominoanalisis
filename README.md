# 🎲 Domino Analyzer Pro

Analisis langkah domino dengan **tracking lawan** (jerat • blok • adu • dominasi),
kini dengan mesin perhitungan **C++20** yang akurat & deterministik, disajikan
oleh **server Python** (tanpa dependensi eksternal).

## Arsitektur

```
web/index.html + app.js + styles.css   → UI (tanpa dependensi eksternal)
            │  fetch JSON
            ▼
server/domino_server.py  (port 2024)   → validasi input + static file server
            │  stdin/stdout JSON
            ▼
engine/domino_engine.cpp  → Monte-Carlo 2000+ sims per langkah, skoring jerat/
                            blok/dominasi, deal dengan constraint PASS lawan
```

## Menjalankan

```bash
python start.py            # build engine (bila perlu) + buka http://127.0.0.1:2024
python start.py --check    # hanya build + self-test engine
python tools/build_engine.py --force   # build ulang engine secara paksa
```

Compiler yang didukung: **MSVC** (Visual Studio 2022, terdeteksi via vswhere),
atau g++/clang++ bila tersedia.

## Akurasi (perbaikan dari versi JS asli)

1. **Bug peta angka diperbaiki** — kartu yang baru dimainkan kini ikut dihitung
   sebagai "keluar", sehingga jumlah kartu unknown lawan tidak lagi dibesar-besarkan.
2. **Constraint PASS dihormati** — saat deal simulasi, kartu dengan angka yang
   sudah di-PASS lawan tidak dibagikan ke lawan tersebut selama masih ada
   solusi yang layak (fallback tercatat & dilaporkan).
3. **Deterministik** — RNG `xoshiro256**` ber-seed: input sama → hasil sama,
   jadi rekomendasi tidak berubah-ubah hanya karena kebetulan acak.
4. **Konservasi kartu** — setiap deal diverifikasi (self-test) bahwa
   kartu lawan + boneyard persis sama dengan pool kartu yang tidak diketahui.

## Endpoint API

| Method | Path            | Fungsi                                   |
|--------|-----------------|------------------------------------------|
| GET    | `/api/health`   | status server + engine                   |
| POST   | `/api/analyze`  | analisis langkah (JSON `cmd:"analyze"`)  |
| POST   | `/api/selftest` | self-test engine                         |
| POST   | `/api/meta`     | kartu sisa dari `myHand` + `played`      |
