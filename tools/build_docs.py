#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Domino Analyzer Pro documentation book.

Source  : docs/src/*.md  (digabung sesuai urutan nama file)
Output  : docs/Domino-Analyzer-Pro-Dokumentasi.md    (buku gabungan, Markdown)
          docs/Domino-Analyzer-Pro-Dokumentasi.pdf   (buku cetak, fpdf2)
          docs/Domino-Analyzer-Pro-Dokumentasi.docx  (versi bisa diedit)

Dependensi pihak ketiga (hanya untuk build dokumen, bukan untuk aplikasi):
    pip install fpdf2 python-docx fontTools     # Pillow ikut terpasang bersama fpdf2

Font & sampul:
    - Teks memakai Times New Roman (cadangan: Liberation Serif, Georgia, DejaVu Serif).
    - Sampul memakai gambar latar yang digambar Pillow saat build (kotak gradasi +
      motif kartu domino) dan disimpan di direktori sementara, bukan di dalam repo.
    - Nomor halaman daftar isi diukur pada lintasan pertama lalu dicetak pada
      lintasan kedua; build gagal berisik bila kedua lintasan berpaginasi beda.

Contoh:
    python tools/build_docs.py
    python tools/build_docs.py --check-fonts      # cek glyph saja
    python tools/build_docs.py --no-docx          # PDF + Markdown saja

Dialek Markdown yang didukung: H1..H4, paragraf, daftar berpoin/bernomor,
tabel pipe, blok kode (```), kutipan (>), garis pemisah (---), penekanan
**tebal** / *miring* / `kode`, plus dua direktif khusus:
    <!--DIAGRAM:nama-->   -> gambar diagram vektor (lihat DIAGRAMS)
    [[NEWPAGE]]           -> paksa halaman baru
"""
from __future__ import annotations

import argparse
import datetime
import functools
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "docs" / "src"
OUT_DIR = ROOT / "docs"
BOOK_STEM = "Domino-Analyzer-Pro-Dokumentasi"

TITLE = "Domino Analyzer Pro"
SUBTITLE = "Buku Penjelasan & Panduan Lengkap"
AUTHOR = "Dody Maulana Ramadhan"
APP_VERSION = "v3.3 · engine 3.0.0"
BUILD_DATE = datetime.date.today().isoformat()

# ---------------------------------------------------------------------------
# Warna & ukuran (tema terang untuk cetak, senada dengan UI aplikasi)
# ---------------------------------------------------------------------------
INK = (23, 28, 36)
MUTED = (95, 105, 120)
ACCENT = (31, 111, 235)      # biru
GREEN = (26, 127, 55)
RED = (199, 32, 45)
ORANGE = (188, 108, 0)
PURPLE = (110, 60, 190)
RULE = (205, 212, 220)
CODE_BG = (243, 245, 248)
TB_HEAD = (235, 239, 244)
TB_ZEBRA = (249, 250, 252)
PANEL = (246, 248, 251)
PANEL_BORDER = (206, 215, 226)

PAGE_W, PAGE_H = 210.0, 297.0            # A4 portrait (mm)
M_LEFT, M_RIGHT, M_TOP, M_BOTTOM = 25.0, 25.0, 20.0, 18.0   # margin simetris
BODY_SIZE = 11.0                          # Times New Roman 11pt ~ sans 10pt
LINE_H = 5.35


def lead(pt: float, factor: float = 1.2) -> float:
    """Tinggi baris (mm) untuk ukuran font (pt): 1pt = 0,3528mm."""
    return round(pt * 0.3528 * factor, 2)

# ---------------------------------------------------------------------------
# Sanitasi karakter: peta simbol -> padanan ASCII, sisanya dibuang
# ---------------------------------------------------------------------------
SYMBOL_MAP = {
    "\u2192": "\u2192",   # panah kanan (dipertahankan bila font punya)
    "\u2022": "\u2022",   # bulet
    "\u2013": "\u2013", "\u2014": "\u2014",
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2026": "...", "\u00b1": "+/-", "\u00d7": "x",
    "\u2264": "<=", "\u2265": ">=", "\u2248": "~", "\u00b0": " derajat",
    "\u25aa": "-", "\u25cf": "*", "\u2713": "OK", "\u2717": "X",
    "\u26a0": "!", "\u274c": "X", "\u2705": "OK", "\u20ac": "EUR",
}


def sanitize_text(text: str, allowed: set[str] | None = None) -> str:
    """Map known symbols, drop characters the target font cannot render."""
    out = []
    for ch in text:
        if ord(ch) < 128:
            out.append(ch)
            continue
        if allowed is not None and ch in allowed:
            out.append(ch)
            continue
        repl = SYMBOL_MAP.get(ch)
        if repl is None:
            continue                      # emoji / karakter tak didukung
        if allowed is not None and any(c not in allowed and ord(c) >= 128 for c in repl):
            continue
        out.append(repl)
    return "".join(out)


# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------
FONT_CANDIDATES = [
    # (family, regular, bold, italic, bold-italic)
    # Serif didahulukan: buku ini memakai Times New Roman. Liberation Serif
    # metrik-kompatibel dengannya, jadi hasil di Linux hampir identik.
    ("Times New Roman", "times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    ("Liberation Serif", "LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf",
     "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf"),
    ("Georgia", "georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    ("DejaVu Serif", "DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf",
     "DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf"),
    ("Segoe UI", "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    ("Calibri", "calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    ("DejaVu Sans", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
     "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"),
    ("Noto Sans", "NotoSans-Regular.ttf", "NotoSans-Bold.ttf",
     "NotoSans-Italic.ttf", "NotoSans-BoldItalic.ttf"),
    ("Arial", "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
]
MONO_CANDIDATES = [
    ("Consolas", "consola.ttf", "consolab.ttf"),
    ("DejaVu Sans Mono", "DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"),
    ("Courier New", "cour.ttf", "courbd.ttf"),
]

FONT_DIRS = [
    pathlib.Path(r"C:\Windows\Fonts"),
    pathlib.Path("/usr/share/fonts/truetype/dejavu"),
    pathlib.Path("/usr/share/fonts/truetype/liberation"),
    pathlib.Path("/Library/Fonts"),
    pathlib.Path.home() / ".fonts",
]


def find_font(candidates: list[tuple]) -> tuple[str, list[pathlib.Path]] | None:
    for names in candidates:
        family, files = names[0], names[1:]
        paths = []
        for fname in files:
            hit = None
            for d in FONT_DIRS:
                p = d / fname
                if p.exists():
                    hit = p
                    break
            paths.append(hit)
        if paths[0] is not None:
            return family, [p if p is not None else paths[0] for p in paths]
    return None


def font_charset(path: pathlib.Path) -> set[str]:
    """Set every Unicode character the font file can render (via fontTools)."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:                                    # pragma: no cover
        return set()
    font = TTFont(str(path), fontNumber=0, lazy=True)
    cmap: set[str] = set()
    for table in font["cmap"].tables:
        for code in table.cmap.keys():
            cmap.add(chr(code))
    font.close()
    return cmap


# ---------------------------------------------------------------------------
# Parser Markdown (subset)
# ---------------------------------------------------------------------------
RE_TABLE_SEP = re.compile(r"^\|?[\s:-]*\|[\s|:-]*$")
RE_DIAGRAM = re.compile(r"^<!--\s*DIAGRAM:([a-z0-9_-]+)\s*-->$", re.I)


def split_row(line: str) -> list[str]:
    """Pecah baris tabel pada '|' yang TIDAK di-escape; '\\|' tetap literal."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def parse_table(lines: list[str], i: int) -> tuple[dict, int]:
    header = split_row(lines[i])
    rows = []
    j = i + 2
    while j < len(lines) and lines[j].strip().startswith("|"):
        rows.append(split_row(lines[j]))
        j += 1
    return {"t": "table", "header": header, "rows": rows}, j


def parse_markdown(text: str) -> list[dict]:
    lines = text.splitlines()
    blocks: list[dict] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue
        if stripped == "[[NEWPAGE]]":
            blocks.append({"t": "newpage"})
            i += 1
            continue
        m = RE_DIAGRAM.match(stripped)
        if m:
            blocks.append({"t": "diagram", "key": m.group(1).lower()})
            i += 1
            continue
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i].rstrip())
                i += 1
            i += 1
            blocks.append({"t": "code", "lang": lang, "lines": body})
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and RE_TABLE_SEP.match(
                lines[i + 1].strip()):
            block, i = parse_table(lines, i)
            blocks.append(block)
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            blocks.append({"t": f"h{len(m.group(1))}", "text": m.group(2).strip()})
            i += 1
            continue
        if stripped in ("---", "***", "___"):
            blocks.append({"t": "hr"})
            i += 1
            continue
        if stripped.startswith(">"):
            body = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                body.append(lines[i].strip().lstrip(">").strip())
                i += 1
            blocks.append({"t": "quote", "text": " ".join(body)})
            continue
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]).strip())
                i += 1
            blocks.append({"t": "ul", "items": items})
            continue
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip())
                i += 1
            blocks.append({"t": "ol", "items": items})
            continue
        # paragraf: gabungkan baris berurutan sampai baris kosong / blok lain
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", ">", "```", "|", "[[NEWPAGE]]"))
                    or RE_DIAGRAM.match(nxt) or re.match(r"^[-*]\s+", nxt)
                    or re.match(r"^\d+\.\s+", nxt) or nxt in ("---", "***", "___")):
                break
            para.append(nxt)
            i += 1
        blocks.append({"t": "p", "text": " ".join(para)})
    return blocks


# ---------------------------------------------------------------------------
# Inline formatting: **tebal**, *miring*, `kode`
# ---------------------------------------------------------------------------
RE_INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)")


def tokenize_inline(text: str) -> list[tuple[str, str]]:
    """-> [(style, text)] dengan style in {'', 'b', 'i', 'c'}."""
    out = []
    for part in RE_INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append(("b", part[2:-2]))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append(("c", part[1:-1]))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append(("i", part[1:-1]))
        else:
            out.append(("", part))
    return out


def strip_markup(text: str) -> str:
    return "".join(t for _, t in tokenize_inline(text))


# ---------------------------------------------------------------------------
# Judul Bagian & kerangka daftar isi
# ---------------------------------------------------------------------------
RE_PART = re.compile(r"^Bagian\s+([IVXLCDM]+)\s*[\u2014\u2013-]\s*(.+)$")


def part_headings(text: str, part_no: int) -> tuple[str, str, str]:
    """-> (label "BAGIAN n", angka romawi, judul) untuk judul H1."""
    clean = strip_markup(text)
    m = RE_PART.match(clean)
    if m:
        return f"BAGIAN {m.group(1)}", m.group(1), m.group(2).strip()
    return f"BAGIAN {part_no}", str(part_no), clean


def outline_names(blocks: list[dict]) -> list[tuple[int, str]]:
    """Kerangka daftar isi: [(level, judul)] tanpa nomor halaman.

    Dipakai lintasan pertama supaya halaman daftar isi digambar dengan tata
    letak yang SAMA seperti lintasan kedua (kalau tidak, perpindahan halaman
    di kedua lintasan berbeda satu halaman dan nomor halaman jadi meleset).
    """
    out: list[tuple[int, str]] = []
    part = sec = 0
    for b in blocks:
        if b["t"] == "h1":
            part += 1
            sec = 0
            eyebrow, _, title = part_headings(b["text"], part)
            out.append((0, f"{eyebrow} \u2014 {title}"))
        elif b["t"] == "h2":
            sec += 1
            out.append((1, f"{part}.{sec}  {strip_markup(b['text'])}"))
    return out


# ---------------------------------------------------------------------------
# Sampul: gambar latar (dibuat dengan Pillow, di-cache di direktori sementara)
# ---------------------------------------------------------------------------
COVER_ART_VERSION = 3      # naikkan bila desain sampul berubah (cache ikut invalid)


def _tile_image(w: int, h: int, a: int, b: int, radius: int, pip_r: int):
    """Satu kartu domino: muka terang, garis pemisah, dan mata sesuai nilai."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=(243, 246, 251, 255),
                        outline=(206, 214, 226, 255), width=max(1, int(w * 0.012)))
    d.line([(int(w * 0.08), h / 2), (int(w * 0.92), h / 2)],
           fill=(18, 24, 34, 255), width=max(2, int(w * 0.035)))

    def lattice(y0: float, y1: float, value: int):
        inset_x = w * 0.25          # mata harus masuk ke dalam kartu, bukan di tepi
        inset_y = (y1 - y0) * 0.25
        xs = [inset_x, w / 2, w - inset_x]
        ys = [y0 + inset_y, (y0 + y1) / 2, y1 - inset_y]
        idx = {0: [], 1: [(1, 1)], 2: [(0, 0), (2, 2)], 3: [(0, 0), (1, 1), (2, 2)],
               4: [(0, 0), (2, 0), (0, 2), (2, 2)],
               5: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)],
               6: [(0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)]}[value]
        for i, j in idx:
            cx, cy = xs[i], ys[j]
            d.ellipse([cx - pip_r, cy - pip_r, cx + pip_r, cy + pip_r],
                      fill=(20, 26, 38, 255))

    lattice(0, h / 2, a)
    lattice(h / 2, h, b)
    return img


@functools.lru_cache(maxsize=1)
def cover_art_path():
    """Gambar latar sampul: gradasi gelap, cahaya biru, garis cetak biru, dan
    tiga kartu domino. Ditulis ke direktori sementara karena ini aset build,
    bukan berkas proyek. Mengembalikan None bila Pillow tidak tersedia."""
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
    except Exception:                                     # pragma: no cover
        return None

    out = pathlib.Path(tempfile.gettempdir()) / f"domino-cover-v{COVER_ART_VERSION}.jpg"
    if out.exists() and out.stat().st_size > 10000:
        return out
    return _render_cover_art(out)


def _render_cover_art(out: pathlib.Path):
    """Gambar latar sampul: gradasi gelap, cahaya biru, garis cetak biru,
    dan kipas tiga kartu domino dengan bayangan lembut."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    resample = getattr(Image, "Resampling", Image)
    W, H = 1654, 2339                                    # 210x297mm @ 200dpi

    def px(v: float) -> int:
        return int(round(v * W / 210.0))

    # 1. gradasi dasar: biru malam di atas, hampir hitam di bawah
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), (int(16 - 11 * t), int(23 - 16 * t), int(36 - 24 * t)))
    base = grad.resize((W, H), Image.BILINEAR)

    # 2. cahaya biru lembut di belakang kipas kartu
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([W * -0.10, H * 0.01, W * 1.10, H * 0.62], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(px(26))).point(lambda v: int(v * 0.34))
    tint = ImageChops.multiply(Image.merge("RGB", (glow, glow, glow)),
                               Image.new("RGB", (W, H), (64, 124, 240)))
    base = ImageChops.screen(base, tint)

    # 3. garis cetak biru yang memudar ke bawah
    grid = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(grid)
    for x in range(px(6), W, px(9)):
        gd.line([(x, 0), (x, H)], fill=14)
    for y in range(px(6), int(H * 0.66), px(9)):
        gd.line([(0, y), (W, y)], fill=11)
    fade = Image.new("L", (1, H))
    for y in range(H):
        t = y / (H * 0.62)
        fade.putpixel((0, y), 255 if t <= 1 else max(0, int(255 * (1.7 - t))))
    grid = ImageChops.multiply(grid, fade.resize((W, H), Image.BILINEAR))
    base = ImageChops.screen(base, Image.merge("RGB", (grid, grid, grid)))
    # 4. kipas tiga kartu domino dengan bayangan lembut
    layers = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tw, th = px(26), px(52)
    cy = H * 0.27
    fan = [(-0.92, -9, (3, 6)), (0.92, 9, (5, 2)), (0.0, 0, (6, 6))]
    for off, ang, (a, b) in fan:
        tile = _tile_image(tw, th, a, b, radius=px(2.4), pip_r=px(1.35))
        rot = tile.rotate(ang, resample=resample.BICUBIC, expand=True)
        x = int(W / 2 + off * tw * 1.02 - rot.width / 2)
        y = int(cy - rot.height / 2)
        mask = rot.split()[3].filter(ImageFilter.GaussianBlur(px(2.6)))
        layers.paste((0, 0, 0, 165), (x + px(1.6), y + px(2.4)), mask)
        layers.paste(rot, (x, y), rot)
    base = Image.alpha_composite(base.convert("RGBA"), layers).convert("RGB")

    # 5. tirai gelap di paruh bawah supaya teks sampul tetap kontras
    scrim = Image.new("L", (1, H))
    for y in range(H):
        t = (y / H - 0.40) / 0.34
        scrim.putpixel((0, y), int(190 * min(1.0, max(0.0, t))))
    base = Image.composite(Image.new("RGB", (W, H), (4, 6, 10)), base,
                           scrim.resize((W, H), Image.BILINEAR))

    # 6. vignette: tepi digelapkan tipis
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.22, -H * 0.10, W * 1.22, H * 1.10], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(px(34)))
    vig = Image.eval(vig, lambda v: int((255 - v) * 0.8))
    base = Image.composite(Image.new("RGB", (W, H), (2, 3, 5)), base, vig)

    out.parent.mkdir(parents=True, exist_ok=True)
    base.save(out, "JPEG", quality=88, optimize=True)
    return out


# ---------------------------------------------------------------------------
class BookPDF:
    def __init__(self):
        from fpdf import FPDF
        self.pdf = FPDF(orientation="P", unit="mm", format="A4")
        self.pdf.set_auto_page_break(True, margin=M_BOTTOM)
        self.pdf.set_margins(M_LEFT, M_TOP, M_RIGHT)
        self._setup_fonts()
        self.chapter = ""
        self.suppress_marks = False       # true pada sampul & halaman TOC
        self.figure_no = 0                # penomoran gambar otomatis
        self.part_no = 0                  # nomor Bagian (untuk penomoran sub-bab)
        self.sec_no = 0
        self.sub_no = 0
        self.lead_pending = False         # paragraf pertama tiap Bagian = paragraf pembuka
        self.blocks: list[dict] = []      # blok yang sedang dirender (untuk lihat ke depan)
        self.block_idx = 0
        self.outline: list[tuple[int, str, int]] = []   # (level, judul, halaman)

    # -- font ---------------------------------------------------------------
    def _setup_fonts(self):
        pdf = self.pdf
        choice = find_font(FONT_CANDIDATES)
        mono = find_font(MONO_CANDIDATES)
        if choice is None:
            raise SystemExit(
                "[docs] Tidak menemukan font TrueType. Pasang DejaVu Sans atau "
                "jalankan di sistem yang punya font sistem."
            )
        family, paths = choice
        styles = ["", "B", "I", "BI"]
        for style, path in zip(styles, paths):
            pdf.add_font("body", style, str(path))
        self.family = family
        self.charset = font_charset(paths[0])
        if mono is not None:
            mfamily, mpaths = mono
            pdf.add_font("mono", "", str(mpaths[0]))
            pdf.add_font("mono", "B", str(mpaths[1]))
            self.mono_family = mfamily
            self.mono_charset = font_charset(mpaths[0])
        else:                                              # pragma: no cover
            self.mono_family = None
            self.mono_charset = set()

    def san(self, text: str, mono: bool = False) -> str:
        out = sanitize_text(text, allowed=self.mono_charset if mono else self.charset)
        if not mono:
            # emoji yang dibuang tidak boleh meninggalkan jarak ganda di tengah teks
            out = re.sub(r"(?<=\S)  +", " ", out)
        return out

    def use(self, style: str = "", size: float = BODY_SIZE, color=INK,
            mono: bool = False):
        pdf = self.pdf
        if mono and self.mono_family:
            pdf.set_font("mono", "B" if "B" in style else "", size)
        else:
            pdf.set_font("body", style, size)
        pdf.set_text_color(*color)

    # -- halaman ------------------------------------------------------------
    def header(self):
        pdf = self.pdf
        if pdf.page_no() == 1 or self.suppress_marks:
            return
        pdf.set_y(10)
        self.use("", 8.0, MUTED)
        pdf.cell(0, 4, self.san(f"{TITLE} \u00b7 {SUBTITLE}"), align="L")
        pdf.set_y(10)
        self.use("I", 8.0, MUTED)
        pdf.cell(0, 4, self.san(self.chapter[:58]), align="R")
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.25)
        pdf.line(M_LEFT, 16.5, PAGE_W - M_RIGHT, 16.5)
        pdf.set_y(M_TOP)

    def footer(self):
        pdf = self.pdf
        if pdf.page_no() == 1 or self.suppress_marks:
            return
        pdf.set_y(-14)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.25)
        pdf.line(M_LEFT, PAGE_H - 15, PAGE_W - M_RIGHT, PAGE_H - 15)
        self.use("", 7.8, MUTED)
        pdf.cell(0, 5, self.san(f"by {AUTHOR}"), align="L")
        pdf.set_y(-14)
        pdf.cell(0, 5, f"Halaman {pdf.page_no()} dari {{nb}}", align="R")

    # -- utilitas ruang -----------------------------------------------------
    def space_left(self) -> float:
        return PAGE_H - M_BOTTOM - self.pdf.get_y()

    def need(self, mm: float):
        if self.space_left() < mm:
            self.pdf.add_page()

    def hr(self, gap_before=1.6, gap_after=2.4):
        pdf = self.pdf
        pdf.ln(gap_before)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        pdf.line(M_LEFT, pdf.get_y(), PAGE_W - M_RIGHT, pdf.get_y())
        pdf.ln(gap_after)

    # -- blok ---------------------------------------------------------------
    def write_runs(self, text: str, size: float = BODY_SIZE, h: float = LINE_H,
                   color=INK, first_indent: float = 0.0, force_italic: bool = False):
        pdf = self.pdf
        if first_indent:
            pdf.set_x(M_LEFT + first_indent)
        same_line = bool(first_indent)
        for style, chunk in tokenize_inline(text):
            chunk = self.san(chunk)
            if not chunk:
                continue
            if style == "b":
                self.use("B", size, color)
            elif style == "i":
                self.use("I", size, color)
            elif style == "c":
                self.use("", size - 0.6, ACCENT, mono=True)
            else:
                self.use("I" if force_italic else "", size, color)
            pdf.write(h, chunk)
            same_line = True
        pdf.ln(h)
        if not same_line:
            pass

    def paragraph(self, text: str, size: float = BODY_SIZE, lead_style: bool = False):
        if lead_style:
            # Paragraf pembuka Bagian: sedikit lebih besar, miring, menjorok.
            pdf = self.pdf
            self.need(22)
            pdf.ln(0.4)
            pdf.set_left_margin(M_LEFT + 4.5)
            pdf.set_x(M_LEFT + 4.5)
            self.write_runs(text, size=size + 0.7, h=LINE_H + 0.2,
                            color=(44, 52, 66), force_italic=True)
            pdf.set_left_margin(M_LEFT)
            pdf.ln(2.4)
            return
        self.need(14)
        self.write_runs(text, size=size)
        self.pdf.ln(1.5)

    def bullet_list(self, items: list[str], ordered: bool = False):
        pdf = self.pdf
        for idx, item in enumerate(items, 1):
            marker = f"{idx}." if ordered else "\u2022"
            self.need(8)
            y0 = pdf.get_y()
            self.use("B", BODY_SIZE, ACCENT if ordered else MUTED)
            pdf.set_x(M_LEFT)
            pdf.write(LINE_H, marker)
            pdf.set_x(M_LEFT + (7.5 if ordered else 4.6))
            self.write_runs(item)
            if pdf.get_y() <= y0 + 0.2:            # jaga-jaga
                pdf.ln(LINE_H)
        pdf.ln(1.2)

    def quote(self, text: str):
        pdf = self.pdf
        self.need(14)
        y0 = pdf.get_y()
        pdf.set_x(M_LEFT + 4)
        self.write_runs(text, size=BODY_SIZE - 0.4, color=(70, 78, 92))
        y1 = pdf.get_y()
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.9)
        pdf.line(M_LEFT + 1.2, y0 + 0.5, M_LEFT + 1.2, y1 - 1.2)
        pdf.ln(1.4)

    def code_block(self, lines: list[str]):
        pdf = self.pdf
        size = 8.0
        lh = 3.9
        inner_w = PAGE_W - M_LEFT - M_RIGHT - 6
        # Bungkus baris kode dengan MENGUKUR lebar nyata di font mono, bukan
        # menaksir jumlah karakter — hasilnya tidak pernah meluber keluar kotak.
        self.use("", size, (40, 46, 56), mono=True)
        wrapped: list[str] = []
        for raw in lines:
            line = self.san(raw.replace("\t", "    "), mono=True)
            if not line:
                wrapped.append("")
                continue
            indent = len(line) - len(line.lstrip(" "))
            room = inner_w - pdf.get_string_width(" " * indent)
            cur = ""
            for ch in line[indent:]:
                if cur and pdf.get_string_width(cur + ch) > room:
                    wrapped.append(" " * indent + cur)
                    cur = ch
                else:
                    cur += ch
            wrapped.append(" " * indent + cur)
        height = lh * len(wrapped) + 4.4
        self.need(min(height, 120) + 2)
        if height > self.space_left():
            # blok kode panjang: pecah antar halaman
            remaining = wrapped[:]
            while remaining:
                room = int((self.space_left() - 5) / lh)
                if room < 3:
                    pdf.add_page()
                    continue
                chunk, remaining = remaining[:room], remaining[room:]
                self._draw_code_chunk(chunk, size, lh)
            pdf.ln(2.4)
            return
        self._draw_code_chunk(wrapped, size, lh)
        pdf.ln(2.4)

    def _draw_code_chunk(self, chunk: list[str], size: float, lh: float):
        pdf = self.pdf
        height = lh * len(chunk) + 4.0
        y = pdf.get_y()
        pdf.set_fill_color(*CODE_BG)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        pdf.rect(M_LEFT, y, PAGE_W - M_LEFT - M_RIGHT, height, style="DF")
        pdf.set_xy(M_LEFT + 3, y + 2.1)
        self.use("", size, (40, 46, 56), mono=True)
        for line in chunk:
            pdf.set_x(M_LEFT + 3)
            pdf.cell(0, lh, line, new_x="LMARGIN", new_y="NEXT")
        pdf.set_y(y + height)

    def table(self, header: list[str], rows: list[list[str]]):
        pdf = self.pdf
        size = 8.9
        pad = 2.0
        lh = 4.15
        n = len(header)
        avail = PAGE_W - M_LEFT - M_RIGHT
        # lebar kolom: proporsional terhadap panjang konten, dengan batas
        weights = []
        for c in range(n):
            longest = len(strip_markup(header[c]))
            for r in rows:
                if c < len(r):
                    longest = max(longest, min(len(strip_markup(r[c])), 60))
            weights.append(max(8, min(longest, 60)))
        total = sum(weights)

        # Lebar minimum tiap kolom = kata terpanjang di kolom itu. Tanpa ini
        # fpdf2 memotong kata di tengah (mis. "Antarmu|ka") karena kolomnya
        # dihitung hanya dari panjang teks.
        self.use("", size, INK)
        min_widths = []
        for c in range(n):
            longest_word = 0.0
            cells_all = [header[c]] + [r[c] if c < len(r) else "" for r in rows]
            for txt in cells_all:
                for word in strip_markup(txt).split():
                    longest_word = max(longest_word, pdf.get_string_width(self.san(word)))
            min_widths.append(min(avail * 0.5, longest_word + 2 * pad + 1.2))
        if sum(min_widths) > avail:                        # sangat jarang
            shrink = avail / sum(min_widths)
            min_widths = [w * shrink for w in min_widths]

        def cell_lines(text: str, width: float) -> list[str]:
            self.use("", size)
            return pdf.multi_cell(width - 2 * pad, lh, self.san(strip_markup(text)),
                                  dry_run=True, output="LINES")

        # Sisa ruang setelah lebar minimum dibagi sesuai panjang isi kolom,
        # sehingga tidak ada kata yang terpotong dan kolom tetap proporsional.
        leftover = max(0.0, avail - sum(min_widths))
        widths = [min_widths[c] + leftover * weights[c] / total for c in range(n)]

        def draw_row(cells: list[str], bold: bool, fill, zebra: bool):
            nonlocal y
            lines = []
            for c in range(n):
                txt = cells[c] if c < len(cells) else ""
                lines.append(cell_lines(txt, widths[c]))
            h = max(4.6, lh * max(len(l) for l in lines) + 2 * pad)
            self.need(h + 1)
            y = pdf.get_y() if y is None else y
            if pdf.get_y() + h > PAGE_H - M_BOTTOM:
                pdf.add_page()
                y = pdf.get_y()
            pdf.set_fill_color(*fill)
            x = M_LEFT
            for c in range(n):
                pdf.rect(x, y, widths[c], h, style="DF" if fill != (255, 255, 255) else "D")
                x += widths[c]
            x = M_LEFT
            for c in range(n):
                self.use("B" if bold else "", size, INK if bold else (52, 60, 72))
                pdf.set_xy(x + pad, y + pad)
                pdf.multi_cell(widths[c] - 2 * pad, lh, self.san(strip_markup(
                    cells[c] if c < len(cells) else "")), align="L")
                x += widths[c]
            pdf.set_y(y + h)
            y = None

        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        y = None
        draw_row(header, True, TB_HEAD, False)
        for idx, r in enumerate(rows):
            draw_row(r, False, TB_ZEBRA if idx % 2 else (255, 255, 255), idx % 2 == 1)
        pdf.ln(2.6)

    def callout(self, title: str, text: str, color=ACCENT):
        pdf = self.pdf
        size = 9.7
        lh = 4.7
        inner = PAGE_W - M_LEFT - M_RIGHT - 8
        self.use("B", size)
        lines_b = pdf.multi_cell(inner, lh, self.san(strip_markup(title)),
                                 dry_run=True, output="LINES")
        self.use("", size)
        lines_t = pdf.multi_cell(inner, lh, self.san(strip_markup(text)),
                                 dry_run=True, output="LINES")
        height = lh * (len(lines_b) + len(lines_t)) + 5.4
        self.need(min(height, 150) + 2)
        y = pdf.get_y()
        pdf.set_fill_color(*PANEL)
        pdf.set_draw_color(*PANEL_BORDER)
        pdf.set_line_width(0.2)
        pdf.rect(M_LEFT, y, PAGE_W - M_LEFT - M_RIGHT, height, style="DF")
        pdf.set_fill_color(*color)
        pdf.rect(M_LEFT, y, 1.4, height, style="F")
        pdf.set_xy(M_LEFT + 4.2, y + 2.2)
        self.use("B", size, color)
        pdf.multi_cell(inner, lh, self.san(strip_markup(title)))
        pdf.set_x(M_LEFT + 4.2)
        self.use("", size, (58, 66, 78))
        pdf.multi_cell(inner, lh, self.san(strip_markup(text)))
        pdf.set_y(y + height + 2.4)

    # -- judul --------------------------------------------------------------
    def h1(self, text: str):
        """Pembuka Bagian: halaman baru, label Bagian, judul besar, dan angka
        romawi raksasa sebagai latar. Isi Bagian berikutnya mengalir bebas,
        jadi tidak ada halaman yang setengah kosong."""
        pdf = self.pdf
        clean = strip_markup(text)
        # Halaman baru hanya bila halaman sekarang sudah terisi — supaya tidak
        # ada halaman kosong setelah daftar isi (posisi sudah di awal halaman).
        if pdf.get_y() > M_TOP + 1:
            pdf.add_page()
        self.part_no += 1
        self.sec_no = 0
        self.sub_no = 0
        self.lead_pending = True
        eyebrow, roman, title = part_headings(text, self.part_no)
        heading = f"{eyebrow} \u2014 {title}"
        pdf.start_section(self.san(heading), level=0)
        self.outline.append((0, heading, pdf.page_no()))
        self.chapter = title

        self.use("B", 104, (230, 236, 244))
        pdf.set_xy(PAGE_W - M_RIGHT - 70, 60)
        pdf.cell(70, 42, self.san(roman), align="R")

        spaced = hasattr(pdf, "set_char_spacing")
        pdf.set_xy(M_LEFT, 74)
        self.use("B", 10.6, ACCENT)
        if spaced:
            pdf.set_char_spacing(1.4)
        pdf.cell(0, 6, self.san(eyebrow), new_x="LMARGIN", new_y="NEXT")
        if spaced:
            pdf.set_char_spacing(0)

        size = self._fit_size(title, 27, PAGE_W - M_LEFT - M_RIGHT)
        pdf.set_x(M_LEFT)
        self.use("B", size, INK)
        pdf.multi_cell(PAGE_W - M_LEFT - M_RIGHT, lead(size), self.san(title))
        pdf.ln(2.4)
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(1.2)
        pdf.line(M_LEFT, pdf.get_y(), M_LEFT + 40, pdf.get_y())
        pdf.ln(7.5)

    def h2(self, text: str):
        pdf = self.pdf
        clean = strip_markup(text)
        # need(36): judul harus ikut beberapa baris isinya, bukan menggantung sendiri
        # di dasar halaman; ditambah ruang blok berikutnya bila itu diagram/tabel.
        self.need(36 + self._keep_with_next(self.blocks, self.block_idx))
        self.sec_no += 1
        self.sub_no = 0
        heading = f"{self.part_no}.{self.sec_no}  {clean}"
        pdf.start_section(self.san(heading), level=1)
        self.outline.append((1, heading, pdf.page_no()))
        self.chapter = heading
        pdf.ln(3.4)
        self.use("B", 16.4, ACCENT)
        pdf.multi_cell(PAGE_W - M_LEFT - M_RIGHT, lead(16.4), self.san(heading))
        pdf.ln(1.2)
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.25)
        pdf.line(M_LEFT, pdf.get_y(), PAGE_W - M_RIGHT, pdf.get_y())
        pdf.ln(3.0)

    def h3(self, text: str):
        self.need(26 + self._keep_with_next(self.blocks, self.block_idx))
        self.sub_no += 1
        self.pdf.ln(2.6)
        self.use("B", 12.8, INK)
        heading = f"{self.part_no}.{self.sec_no}.{self.sub_no}  {strip_markup(text)}"
        self.pdf.multi_cell(PAGE_W - M_LEFT - M_RIGHT, lead(12.8), self.san(heading))
        self.pdf.ln(1.6)

    def h4(self, text: str):
        self.need(20)
        self.pdf.ln(1.8)
        self.use("B", 11.4, (44, 52, 64))
        self.pdf.multi_cell(PAGE_W - M_LEFT - M_RIGHT, lead(11.4), self.san(strip_markup(text)))
        self.pdf.ln(1.0)

    # -- sampul -------------------------------------------------------------
    def cover(self, meta: str = ""):
        pdf = self.pdf
        pdf.add_page()
        self.suppress_marks = True
        art = cover_art_path()
        if art is not None:
            pdf.image(str(art), x=0, y=0, w=PAGE_W, h=PAGE_H)
        else:                                              # cadangan tanpa Pillow
            pdf.set_fill_color(10, 14, 20)
            pdf.rect(0, 0, PAGE_W, PAGE_H, style="F")

        pdf.set_fill_color(*ACCENT)
        pdf.rect(0, 0, PAGE_W, 4.2, style="F")
        pdf.rect(0, PAGE_H - 2.4, PAGE_W, 2.4, style="F")

        spaced = hasattr(pdf, "set_char_spacing")
        if spaced:
            pdf.set_char_spacing(1.2)
        pdf.set_xy(M_LEFT, 149)
        self.use("B", 10.0, (128, 182, 255))
        pdf.cell(0, 6, self.san(SUBTITLE.upper()), new_x="LMARGIN", new_y="NEXT")
        if spaced:
            pdf.set_char_spacing(0)

        size = self._fit_size(TITLE, 40, PAGE_W - 2 * M_LEFT)
        pdf.set_xy(M_LEFT, 157)
        self.use("B", size, (255, 255, 255))
        pdf.multi_cell(PAGE_W - 2 * M_LEFT, lead(size), self.san(TITLE))

        y = pdf.get_y() + 2.6
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(1.4)
        pdf.line(M_LEFT, y, M_LEFT + 46, y)

        pdf.set_xy(M_LEFT, y + 6.2)
        self.use("", 12.8, (176, 192, 212))
        pdf.multi_cell(PAGE_W - 2 * M_LEFT, lead(12.8), self.san(
            "Panduan pemakaian, penjelasan mesin analisis Monte-Carlo, rujukan API, "
            "dan strategi bermain domino 28 kartu."))

        pdf.set_xy(M_LEFT, 236)
        self.use("B", 17, (255, 255, 255))
        pdf.cell(0, 8, self.san(f"by {AUTHOR}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_xy(M_LEFT, 248)
        self.use("", 10.6, (150, 170, 195))
        pdf.cell(0, 6, self.san(f"Versi aplikasi {APP_VERSION}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_xy(M_LEFT, 255)
        pdf.cell(0, 6, self.san(f"Build dokumen {BUILD_DATE}"), new_x="LMARGIN", new_y="NEXT")
        if meta:
            pdf.set_xy(M_LEFT, 262)
            pdf.cell(0, 6, self.san(meta), new_x="LMARGIN", new_y="NEXT")
        self.suppress_marks = False

    def _fit_size(self, text: str, base: float, width: float, bold: bool = True) -> float:
        """Ukuran font terbesar (<= base) yang membuat teks muat satu baris."""
        size = base
        while size > base * 0.6:
            self.use("B" if bold else "", size)
            if self.pdf.get_string_width(self.san(text)) <= width:
                return size
            size -= 0.5
        return round(base * 0.6, 1)

    def _keep_with_next(self, blocks: list[dict], idx: int) -> float:
        """Ruang tambahan yang harus disediakan judul agar blok berikutnya ikut.

        Tanpa ini sebuah judul bisa tercetak di dasar halaman sementara isinya
        (mis. diagram besar) berpindah ke halaman berikutnya.
        """
        if idx + 1 >= len(blocks):
            return 0.0
        nxt = blocks[idx + 1]["t"]
        if nxt == "diagram":
            return min(60.0, DIAGRAM_NEEDS.get(blocks[idx + 1]["key"], 80) + 8)
        if nxt in ("h3", "h4"):
            # judul induk tidak boleh menggantung sendirian di dasar halaman
            return 30.0
        if nxt in ("table", "code"):
            return 20.0
        return 0.0

    def render(self, blocks: list[dict]):
        self.blocks = blocks
        self.block_idx = 0
        for idx, blk in enumerate(blocks):
            self.block_idx = idx
            kind = blk["t"]
            # Hanya paragraf pertama sesudah judul Bagian yang jadi paragraf pembuka.
            is_lead = self.lead_pending and kind == "p"
            self.lead_pending = False
            if kind == "h1":
                self.h1(blk["text"])
            elif kind == "h2":
                self.h2(blk["text"])
            elif kind == "h3":
                self.h3(blk["text"])
            elif kind == "h4":
                self.h4(blk["text"])
            elif kind == "p":
                self.paragraph(blk["text"], lead_style=is_lead)
            elif kind == "ul":
                self.bullet_list(blk["items"], ordered=False)
            elif kind == "ol":
                self.bullet_list(blk["items"], ordered=True)
            elif kind == "code":
                self.code_block(blk["lines"])
            elif kind == "table":
                self.table(blk["header"], blk["rows"])
            elif kind == "quote":
                self.quote(blk["text"])
            elif kind == "hr":
                self.hr()
            elif kind == "newpage":
                self.pdf.add_page()
            elif kind == "diagram":
                self.diagram(blk["key"])
            else:                                          # pragma: no cover
                raise ValueError(f"blok tidak dikenal: {kind}")

    # -- diagram ------------------------------------------------------------
    def diagram(self, key: str):
        fn = DIAGRAMS.get(key)
        if fn is None:
            self.callout(f"Diagram '{key}'", "Diagram belum tersedia pada build ini.", ORANGE)
            return
        # Ruang yang diminta sesuai tinggi gambar itu sendiri; angka tetap 96mm
        # dulu membuat diagram besar selalu dilempar ke halaman berikutnya dan
        # meninggalkan sisa ruang.
        self.need(DIAGRAM_NEEDS.get(key, 80) + 8)
        self.pdf.ln(1.4)
        fn(self)
        self.pdf.ln(3.0)

    # -- helper gambar ------------------------------------------------------
    def box(self, x, y, w, h, text, fill=(255, 255, 255), border=PANEL_BORDER,
            text_color=INK, size=8.4, bold=False, radius=None):
        pdf = self.pdf
        pdf.set_fill_color(*fill)
        pdf.set_draw_color(*border)
        pdf.set_line_width(0.25)
        if radius:
            pdf.rect(x, y, w, h, round_corners=True, corner_radius=radius, style="DF")
        else:
            pdf.rect(x, y, w, h, style="DF")
        self.use("B" if bold else "", size, text_color)
        lines = text.split("\n")
        block_h = 4.0 * len(lines)
        pdf.set_xy(x + 1.5, y + (h - block_h) / 2 + 0.4)
        for line in lines:
            pdf.set_x(x + 1.5)
            pdf.cell(w - 3, 4.0, self.san(line), align="C",
                     new_x="LMARGIN", new_y="NEXT")

    def arrow(self, x1, y1, x2, y2, color=MUTED, width=0.35):
        pdf = self.pdf
        pdf.set_draw_color(*color)
        pdf.set_line_width(width)
        pdf.line(x1, y1, x2, y2)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        size = 1.9
        for da in (math.radians(155), math.radians(-155)):
            pdf.line(x2, y2, x2 + size * math.cos(ang + da), y2 + size * math.sin(ang + da))

    def caption(self, text: str):
        """Keterangan gambar; nomornya dihitung otomatis sesuai urutan tampil."""
        pdf = self.pdf
        self.figure_no += 1
        pdf.ln(0.6)
        self.use("I", 8.2, MUTED)
        pdf.multi_cell(PAGE_W - M_LEFT - M_RIGHT, 4.2,
                       self.san(f"Gambar {self.figure_no}. {text}"), align="C")
        pdf.ln(0.4)

    # -- daftar isi ---------------------------------------------------------
    def draw_toc_page(self, entries: list[tuple[int, str, int]], first: bool = False):
        """Gambar satu halaman daftar isi (dipakai lintasan kedua)."""
        pdf = self.pdf
        pdf.add_page()
        if first:
            self.use("B", 24, INK)
            pdf.set_y(30)
            pdf.cell(0, 12, self.san("Daftar Isi"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_draw_color(*ACCENT)
            pdf.set_line_width(1.1)
            pdf.line(M_LEFT, pdf.get_y() + 1, M_LEFT + 34, pdf.get_y() + 1)
            pdf.ln(7.0)
        else:
            pdf.set_y(M_TOP)
        for k, (level, name, page) in enumerate(entries):
            if level == 0 and k:
                pdf.ln(TOC_GAP)
            if pdf.get_y() > PAGE_H - M_BOTTOM - TOC_ROW_H - 2:
                # Jangan tambah halaman: itu akan menggeser nomor halaman yang
                # sudah diukur di lintasan pertama. Lebih baik gagal berisik.
                raise RuntimeError("daftar isi meluber dari halaman yang disediakan")
            indent = 0.0 if level == 0 else 7.0
            size = 12.6 if level == 0 else 10.8
            color = INK if level == 0 else (58, 68, 84)
            self.use("B" if level == 0 else "", size, color)
            text = self.san(name)
            page_txt = str(page)
            width = PAGE_W - M_LEFT - M_RIGHT
            page_w = pdf.get_string_width(page_txt)
            room = width - indent - page_w - 3.0          # ruang untuk judul + titik
            while name_w_needed(pdf, text) > room and len(text) > 12:
                text = text[:-2].rstrip()
                if not text.endswith("\u2026"):
                    text += "\u2026"
            name_w = name_w_needed(pdf, text)
            # Titik-titik harus mengisi persis sisa ruang, jadi lebar sisanya
            # dihitung SETELAH lebar judul diketahui dan diukur dengan font
            # titik-titik (bukan font judul) — kalau tidak, nomor halaman
            # terdorong melewati margin kanan.
            avail = max(0.0, room - name_w)
            # Lintasan pertama memakai nomor 0 (halaman belum terukur): barisnya
            # tetap digambar supaya tata letak kedua lintasan identik, tanpa tautan.
            link = pdf.add_link(page=page) if page > 0 else None
            pdf.set_x(M_LEFT + indent)
            pdf.cell(name_w, TOC_ROW_H, text, link=link)
            self.use("", size - 1.8, RULE)
            dot_w = pdf.get_string_width(".")
            n_dots = int(avail / (dot_w * 2.4)) if dot_w > 0.01 else 0
            if n_dots > 0 and hasattr(pdf, "set_char_spacing"):
                pdf.set_char_spacing((avail / n_dots - dot_w) * 2.8346)
            pdf.cell(avail, TOC_ROW_H, "." * n_dots, link=link)
            if n_dots > 0 and hasattr(pdf, "set_char_spacing"):
                pdf.set_char_spacing(0)
            self.use("", size, color)
            pdf.cell(page_w + 2, TOC_ROW_H, page_txt, align="R", link=link,
                     new_x="LMARGIN", new_y="NEXT")


# ---------------------------------------------------------------------------
# Diagram vektor
# ---------------------------------------------------------------------------
def _d_architecture(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y()
    w, h = 46.0, 19.0
    gap = 9.0
    total = 3 * w + 2 * gap
    x0 = M_LEFT + (PAGE_W - M_LEFT - M_RIGHT - total) / 2
    labels = [
        ("UI Web (web/)", "index.html + app.js\nstyles.css + sw.js\nPWA, offline shell"),
        ("Server Python", "server/domino_server.py\nport 2024, ThreadingHTTPServer\nvalidasi + normalisasi"),
        ("Engine C++20", "engine/domino_engine.cpp\nbin/domino_engine(.exe)\nMonte-Carlo + ranking"),
    ]
    for i, (title, body) in enumerate(labels):
        x = x0 + i * (w + gap)
        # Kotak digambar tanpa teks: judul dan isi ditulis terpisah supaya tidak
        # tercetak dua kali di posisi yang hampir sama (dulu saling menumpuk).
        bk.box(x, y, w, h, "", fill=PANEL)
        bk.use("B", 8.6, ACCENT)
        pdf.set_xy(x + 1.5, y + 2.2)
        pdf.cell(w - 3, 4.2, bk.san(title), align="C")
        bk.use("", 7.6, (70, 80, 95))
        for k, line in enumerate(body.split("\n")):
            pdf.set_xy(x + 1.5, y + 8.2 + k * 3.7)
            pdf.cell(w - 3, 3.7, bk.san(line), align="C")
        if i < 2:
            bk.arrow(x + w + 0.6, y + h / 2, x + w + gap - 0.6, y + h / 2, ACCENT)
    pdf.set_y(y + h + 3)
    bk.caption("Tiga lapisan aplikasi: UI web, server Python, dan engine C++ "
               "yang dipanggil lewat stdin/stdout berformat JSON.")
    pdf.ln(2.5)


def _d_dataflow(bk: "BookPDF"):
    pdf = bk.pdf
    y0 = pdf.get_y()
    w = PAGE_W - M_LEFT - M_RIGHT
    steps = [
        ("1. Aksi pengguna di UI", "ketuk kartu, catat PASS, atau ubah setup"),
        ("2. app.js menyusun JSON", "buildAnalyzeRequest(): myHand, played, playedBy, aturan meja, seed tetap"),
        ("3. POST /api/analyze", "server menormalkan kunci kartu dan memvalidasi permintaan"),
        ("4. Engine C++ dijalankan", "payload dikirim ke stdin, engine mensimulasikan ribuan gim"),
        ("5. Balasan JSON", "moves[] (winRate, CI, rankScore, alasan), opponents[], deadTiles[]"),
        ("6. UI menggambar ulang", "glow rekomendasi, siluet papan, panel hasil, profil lawan"),
    ]
    h = 10.4
    for i, (title, body) in enumerate(steps):
        y = y0 + i * (h + 2.4)
        bk.box(M_LEFT, y, w, h, "", fill=PANEL if i % 2 == 0 else (252, 253, 255))
        bk.use("B", 8.6, INK)
        pdf.set_xy(M_LEFT + 3, y + 1.6)
        pdf.cell(w / 2, 4.4, bk.san(title), align="L")
        bk.use("", 8.0, (70, 80, 95))
        pdf.set_xy(M_LEFT + 3, y + 6.0)
        pdf.cell(w - 6, 4.0, bk.san(body), align="L")
        if i < len(steps) - 1:
            bk.arrow(M_LEFT + 8, y + h + 0.3, M_LEFT + 8, y + h + 2.1, RULE)
    pdf.set_y(y0 + len(steps) * (h + 2.4) + 3)
    bk.caption("Alur satu permintaan analisis: dari ketukan di UI sampai "
               "hasil tergambar kembali di papan.")
    pdf.ln(2.5)


def _d_dealing(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y()
    # Lebar kotak dihitung dari lebar teks, bukan angka tetap: lima kotak
    # selebar 42mm (versi lama) meluber jauh melewati tepi kertas A4.
    avail = PAGE_W - M_LEFT - M_RIGHT
    gap = 6.0
    w, h = (avail - 2 * gap) / 3, 20.5
    y2 = y + h + 7.5
    cols = [
        ("Pool tak diketahui", "28 kartu - tangan saya\n- kartu di papan", (246, 248, 251)),
        ("Prioritas 0: held[]", "kartu yang PASTI dipegang\nlawan (atribusi) dipaksa\nmasuk tangan itu", (232, 244, 236)),
        ("Prioritas 1: elim[]", "kartu yang tidak mungkin\ndipegang (dari PASS)\ndibuang dari undian", (243, 240, 250)),
        ("Prioritas 2: fallback", "jika kuota belum terpenuhi,\nbatasan dilepas sedikit\ndan fallback dihitung", (253, 246, 232)),
        ("Boneyard", "sisa kartu = cangkul\n(atau sisa mati bila\ncangkul dimatikan)", (252, 236, 236)),
    ]
    # Tiga kotak di baris atas, dua di baris bawah (dibaca kiri ke kanan),
    # dengan panah membelok dari kotak ke-3 ke kotak ke-4.
    for i, (title, body, fill) in enumerate(cols):
        row, col = (0, i) if i < 3 else (1, i - 3)
        x = M_LEFT + col * (w + gap)
        yy = y if row == 0 else y2
        bk.box(x, yy, w, h, "", fill=fill)
        bk.use("B", 8.2, INK)
        pdf.set_xy(x + 1.5, yy + 2.0)
        pdf.cell(w - 3, 4.2, bk.san(title), align="C")
        bk.use("", 7.4, (70, 80, 95))
        for k, line in enumerate(body.split("\n")):
            pdf.set_xy(x + 1.5, yy + 6.6 + k * 3.7)
            pdf.cell(w - 3, 3.7, bk.san(line), align="C")
        if i < 2:                                       # panah di baris atas
            bk.arrow(x + w + 0.5, y + h / 2, x + w + gap - 0.5, y + h / 2, MUTED)
        if i == 3:                                      # panah di baris bawah
            bk.arrow(x + w + 0.5, y2 + h / 2, x + w + gap - 0.5, y2 + h / 2, MUTED)
    # belokan: dari kotak ke-3 turun ke kiri, lalu masuk ke kotak ke-4
    x_turn = M_LEFT + 2 * (w + gap) + w / 2
    x_into = M_LEFT + w / 2
    ymid = y + h + 3.7
    pdf.set_draw_color(*MUTED)
    pdf.set_line_width(0.35)
    pdf.line(x_turn, y + h + 0.3, x_turn, ymid)
    pdf.line(x_turn, ymid, x_into, ymid)
    bk.arrow(x_into, ymid, x_into, y2 - 0.4, MUTED)
    pdf.set_y(y2 + h + 3)
    bk.caption("Pembagian kartu secara sadar-batasan (constraint-aware dealing): "
               "bukti kuat diprioritaskan, batasan dilepas hanya bila kuota mustahil dipenuhi.")
    pdf.ln(2.5)


def _d_montecarlo(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y()
    cx = M_LEFT + (PAGE_W - M_LEFT - M_RIGHT) / 2
    bk.box(cx - 26, y, 52, 11, "Satu kandidat langkah\n(mis. 6|6 ke ujung kanan)",
           fill=PANEL, size=8.2)
    y2 = y + 17
    bk.use("", 7.8, MUTED)
    pdf.set_xy(M_LEFT, y2 - 4.6)
    pdf.cell(0, 4, bk.san("N pengulangan (numSims), tiap ulangan: bagi kartu -> mainkan gim penuh"), align="C")
    cols = 5
    w = 22.0
    gap = 3.4
    x0 = cx - (cols * w + (cols - 1) * gap) / 2
    for i in range(cols):
        x = x0 + i * (w + gap)
        bk.box(x, y2, w, 12.0, f"Deal #{i + 1}\nvs 3 profil\nlawan", fill=(250, 251, 253), size=7.0)
        bk.arrow(cx, y + 11.4, x + w / 2, y2 - 0.5, RULE)
    y3 = y2 + 18.5
    bk.box(cx - 34, y3, 68, 12, "Akumulasi hasil\nmenang / kalah, menang adu, sisa mata, "
                                "pass lawan, konservasi kartu", fill=(240, 246, 255), size=7.6)
    for i in range(cols):
        x = x0 + i * (w + gap)
        bk.arrow(x + w / 2, y2 + 12.4, cx, y3 - 0.5, RULE)
    y4 = y3 + 18.0
    bk.box(cx - 30, y4, 60, 10, "winRate + interval Wilson 95%\n+ rankScore (urut dari engine)",
           fill=(232, 244, 236), size=8.0)
    bk.arrow(cx, y3 + 12.4, cx, y4 - 0.5, RULE)
    pdf.set_y(y4 + 13)
    bk.caption("Monte-Carlo per kandidat langkah: setiap ulangan memakai pembagian "
               "kartu dan gaya lawan yang berbeda, lalu hasilnya diagregasi.")
    pdf.ln(2.5)


def _d_rankscore(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y()
    w = PAGE_W - M_LEFT - M_RIGHT
    components = [
        ("winRate x 100", "peluang menang dari simulasi", 100, ACCENT),
        ("domSupportScore x 0,6", "ujung mendukung angka dominan", 60, GREEN),
        ("trapScore x 0,8", "jerat untuk lawan", 80, PURPLE),
        ("blockScore x 0,7", "kunci ujung / blok terjamin", 70, ORANGE),
        ("deadlockWinRate x 20", "peluang menang lewat adu", 20, (0, 140, 160)),
        ("guaranteedBlocks x 8", "lawan yang pasti mati (data PASS)", 8, RED),
        ("avgOppPasses x 3", "lawan dipaksa lewat", 3, (120, 120, 130)),
        ("safetyRatio x 30", "hanya mode kartu pertama", 30, (150, 90, 20)),
    ]
    neg = [
        ("selfTrapScore x 0,5", "jebakan untuk diri sendiri", 50, RED),
        ("riskScore x 0,5", "kartu berbahaya di tangan lawan", 50, (140, 40, 60)),
    ]
    h = 7.2
    maxw = w - 74
    bk.use("", 7.8, MUTED)
    pdf.set_xy(M_LEFT, y)
    pdf.cell(0, 4, bk.san("Komponen positif"), new_x="LMARGIN", new_y="NEXT")
    yy = pdf.get_y() + 1
    for label, desc, val, color in components:
        pdf.set_fill_color(*color)
        pdf.rect(M_LEFT, yy, maxw * val / 100.0, h - 2.4, style="F")
        bk.use("", 7.6, (60, 68, 80))
        pdf.set_xy(M_LEFT + 1.5, yy - 0.1)
        pdf.cell(maxw, h - 2.6, bk.san(f"{label}  -  {desc}"), align="L")
        yy += h
    yy += 1.6
    bk.use("", 7.8, MUTED)
    pdf.set_xy(M_LEFT, yy)
    pdf.cell(0, 4, bk.san("Komponen negatif (mengurangi skor)"), new_x="LMARGIN", new_y="NEXT")
    yy = pdf.get_y() + 1
    for label, desc, val, color in neg:
        pdf.set_fill_color(*color)
        pdf.rect(M_LEFT, yy, maxw * val / 100.0, h - 2.4, style="F")
        bk.use("", 7.6, (60, 68, 80))
        pdf.set_xy(M_LEFT + 1.5, yy - 0.1)
        pdf.cell(maxw, h - 2.6, bk.san(f"{label}  -  {desc}"), align="L")
        yy += h
    pdf.set_y(yy + 3)
    bk.caption("Susunan rankScore di engine. Semua bobot dihitung di C++ supaya "
               "urutan kartu tidak berbeda antara tampilan dan mesin.")
    pdf.ln(2.5)


def _d_snake(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y() + 2
    tile_w, tile_h = 12.0, 6.0
    rows = [4, 4, 3]
    x_start = M_LEFT + 22
    for ri, count in enumerate(rows):
        yy = y + (len(rows) - 1 - ri) * (tile_h + 3.2)
        for c in range(count):
            x = x_start + c * (tile_w + 1.6)
            bk.box(x, yy, tile_w, tile_h, f"{ri}{c}", fill=(255, 255, 255),
                   size=6.4, border=RULE)
        if ri == 0:
            bk.use("B", 7.4, ORANGE)
            pdf.set_xy(x_start + 1, yy + tile_h + 1.2)
            pdf.cell(0, 4, bk.san("kartu pertama (penanda emas)"), align="L")
    bk.use("", 7.6, MUTED)
    pdf.set_xy(x_start + 4 * (tile_w + 1.6) + 3, y + 2 * (tile_h + 3.2) + 1)
    pdf.multi_cell(52, 4.0, bk.san("Baris 1 memanjang ke kanan,\n"
                                   "baris 2 arah berlawanan,\n"
                                   "baris 3 kembali ke kanan -\n"
                                   "pola ular (boustrophedon)."))
    pdf.set_y(y + 3 * (tile_h + 3.2) + 6)
    bk.caption("Susunan papan bergaya ular: kartu pertama berdiri tegak sebagai "
               "penanda emas, tikungan dibentuk kartu siku.")
    pdf.ln(2.5)


def _d_ghost(bk: "BookPDF"):
    pdf = bk.pdf
    # Ruang atas 22mm: siluet "ghost kanan" digambar 20mm DI ATAS titik awal,
    # jadi tanpa ruang ini diagram menimpa paragraf sebelumnya.
    y0 = pdf.get_y() + 22
    tile_w, tile_h = 11.0, 22.0
    # kartu pertama berdiri di tengah
    cx = M_LEFT + (PAGE_W - M_LEFT - M_RIGHT) / 2
    bk.box(cx - tile_w / 2, y0, tile_w, tile_h, "", fill=(255, 250, 230), border=ORANGE)
    bk.use("B", 7.0, ORANGE)
    pdf.set_xy(cx - 22, y0 + tile_h / 2 - 2)
    pdf.cell(44, 4, bk.san("kartu pertama"), align="C")
    # ghost kanan: di atas kepala
    gx = cx - tile_w / 2 + tile_w + 6
    bk.box(gx, y0 - 20, tile_w, tile_h, "", fill=(240, 246, 255), border=ACCENT)
    bk.use("", 6.8, ACCENT)
    pdf.set_xy(gx - 12, y0 - 16)
    pdf.multi_cell(28, 3.6, bk.san("ghost kanan:\n> di ATAS kepala\n> separuh cocok\n   menunjuk ke atas"))
    # ghost kiri: di kaki
    hx = cx - tile_w / 2 - 6 - tile_w
    bk.box(hx, y0 + tile_h - tile_h, tile_w, tile_h, "", fill=(240, 246, 255), border=ACCENT)
    pdf.set_xy(hx - 26, y0 + 8)
    pdf.multi_cell(26, 3.6, bk.san("ghost kiri:\n> di KAKI kartu\n> separuh cocok\n   menunjuk ke bawah"))
    bk.arrow(gx + tile_w / 2, y0 - 11, cx, y0 - 2, ACCENT)
    bk.arrow(hx + tile_w + 2, y0 + 11, cx - 1, y0 + 11, ACCENT)
    pdf.set_y(y0 + tile_h + 8)
    bk.caption("Siluet rekomendasi (ghost) diposisikan relatif ke kartu pertama: "
               "di atas kepala saat main ke kanan, di kaki saat main ke kiri.")
    pdf.ln(2.5)


def _d_wilson(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y() + 4
    w = PAGE_W - M_LEFT - M_RIGHT
    bk.use("", 7.8, MUTED)
    pdf.set_xy(M_LEFT, y - 4)
    pdf.cell(0, 4, bk.san("Perkiraan peluang menang dari N simulasi"), align="L")
    cases = [
        ("Titik 62% dengan 2000 sim", 0.62, 0.60, 0.64, GREEN),
        ("Titik 62% dengan 100 sim", 0.62, 0.52, 0.71, ORANGE),
        ("Titik 50% dengan 100 sim", 0.50, 0.40, 0.60, ACCENT),
    ]
    lh = 17.0
    for i, (label, mid, lo, hi, color) in enumerate(cases):
        yy = y + i * lh
        pdf.set_draw_color(*RULE)
        pdf.set_line_width(0.2)
        pdf.line(M_LEFT + 52, yy + 5, M_LEFT + 52 + w * 0.36, yy + 5)
        for frac in (0.0, 0.5, 1.0):
            x = M_LEFT + 52 + w * 0.36 * frac
            pdf.line(x, yy + 3.6, x, yy + 6.4)
        x_lo = M_LEFT + 52 + w * 0.36 * lo
        x_hi = M_LEFT + 52 + w * 0.36 * hi
        x_mid = M_LEFT + 52 + w * 0.36 * mid
        pdf.set_draw_color(*color)
        pdf.set_line_width(1.0)
        pdf.line(x_lo, yy + 5, x_hi, yy + 5)
        pdf.line(x_lo, yy + 3.4, x_lo, yy + 6.6)
        pdf.line(x_hi, yy + 3.4, x_hi, yy + 6.6)
        pdf.set_fill_color(*color)
        pdf.circle(x_mid, yy + 5, 1.4, style="F")
        bk.use("", 7.6, (60, 68, 80))
        pdf.set_xy(M_LEFT, yy + 1.4)
        pdf.cell(50, 4, bk.san(label), align="L")
        pdf.set_xy(x_hi + 2, yy + 3.0)
        pdf.cell(30, 4, bk.san(f"{lo * 100:.0f}-{hi * 100:.0f}%"), align="L")
    pdf.set_y(y + len(cases) * lh + 4)
    bk.caption("Interval Wilson 95%: jumlah simulasi yang lebih banyak membuat "
               "selang keyakinan menyempit, sehingga beda tipis tidak menyesatkan.")
    pdf.ln(2.5)


def _d_timeline(bk: "BookPDF"):
    pdf = bk.pdf
    y = pdf.get_y() + 2
    w = PAGE_W - M_LEFT - M_RIGHT
    n = 5
    step = (w - 16) / (n - 1)
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.5)
    pdf.line(M_LEFT + 8, y + 6, M_LEFT + 8 + step * (n - 1), y + 6)
    labels = ["mulai", "+ kartu", "+ PASS lawan", "+ atribusi", "Reset"]
    for i in range(n):
        x = M_LEFT + 8 + i * step
        pdf.set_fill_color(*(ACCENT if i < n - 1 else RED))
        pdf.circle(x, y + 6, 2.1, style="F")
        bk.use("", 7.4, (60, 68, 80))
        pdf.set_xy(x - 14, y + 10)
        pdf.cell(28, 4, bk.san(labels[i]), align="C")
    bk.use("", 7.6, MUTED)
    pdf.set_xy(M_LEFT, y + 16)
    pdf.multi_cell(w, 4.0, bk.san(
        "Setiap aksi menyimpan snapshot state (tangan, papan, atribusi, data PASS) ke "
        "timeline; tombol Undo memulihkan snapshot terakhir. Maksimum 100 langkah."))
    pdf.set_y(y + 26)
    bk.caption("Timeline undo: kartu, PASS lawan, dan atribusi ikut ter-undo "
               "sehingga data pelacakan tidak pernah setengah jalan.")
    pdf.ln(2.5)


# ---------------------------------------------------------------------------
# Daftar isi: tinggi baris dan jarak sebelum tiap Bagian juga dipakai untuk
# menghitung berapa entri yang muat per halaman, jadi jumlah halaman daftar isi
# diukur — bukan ditebak.
# ---------------------------------------------------------------------------
TOC_ROW_H = 6.4
TOC_GAP = 1.9


def name_w_needed(pdf, text: str) -> float:
    """Lebar kolom judul pada daftar isi (termasuk jarak aman setelah judul)."""
    return pdf.get_string_width(text) + 1.5


def toc_page_sizes(levels: list[int]) -> list[int]:
    """Berapa entri daftar isi yang muat di setiap halaman (fungsi murni).

    Hanya bergantung pada level tiap entri (0 = Bagian, 1 = sub-bab), sehingga
    jumlah halaman identik pada kedua lintasan build.
    """
    limit = PAGE_H - M_BOTTOM - 2
    sizes: list[int] = []
    count, y = 0, 50.0                    # 50mm: tepat di bawah judul "Daftar Isi"
    for level in levels:
        add = TOC_ROW_H + (TOC_GAP if (level == 0 and count) else 0.0)
        if count and y + add > limit:
            sizes.append(count)
            count, y, add = 0, M_TOP, TOC_ROW_H
        y += add
        count += 1
    if count:
        sizes.append(count)
    return sizes or [0]


# Perkiraan tinggi tiap diagram (mm, termasuk keterangan gambar) untuk keputusan
# pindah halaman. Dikalibrasi dari tinggi gambar sebenarnya supaya diagram tidak
# dilempar ke halaman berikutnya saat masih ada ruang.
DIAGRAM_NEEDS = {
    "arsitektur": 44, "alur-data": 94, "dealing": 68, "monte-carlo": 78,
    "rankscore": 98, "ular": 54, "ghost": 72, "wilson": 76, "timeline": 44,
}

DIAGRAMS = {
    "arsitektur": _d_architecture,
    "alur-data": _d_dataflow,
    "dealing": _d_dealing,
    "monte-carlo": _d_montecarlo,
    "rankscore": _d_rankscore,
    "ular": _d_snake,
    "ghost": _d_ghost,
    "wilson": _d_wilson,
    "timeline": _d_timeline,
}


# ---------------------------------------------------------------------------
# DOCX builder
# ---------------------------------------------------------------------------
def build_docx(blocks: list[dict], out_path: pathlib.Path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    def add_runs(par, text, size=None, bold_all=False):
        for kind, chunk in tokenize_inline(text):
            run = par.add_run(chunk)
            run.bold = bold_all or kind == "b"
            run.italic = kind == "i"
            if kind == "c":
                run.font.name = "Consolas"
                run.font.size = Pt(9.5)
            if size:
                run.font.size = Pt(size)
        return par

    doc.add_heading(TITLE, level=0)
    p = doc.add_paragraph()
    r = p.add_run(SUBTITLE)
    r.bold = True
    p2 = doc.add_paragraph()
    p2.add_run(f"by {AUTHOR}  |  Versi aplikasi {APP_VERSION}  |  Build {BUILD_DATE}")

    for blk in blocks:
        kind = blk["t"]
        if kind == "h1":
            doc.add_page_break()
            doc.add_heading(strip_markup(blk["text"]), level=1)
        elif kind == "h2":
            doc.add_heading(strip_markup(blk["text"]), level=2)
        elif kind == "h3":
            doc.add_heading(strip_markup(blk["text"]), level=3)
        elif kind == "h4":
            doc.add_heading(strip_markup(blk["text"]), level=4)
        elif kind == "p":
            add_runs(doc.add_paragraph(), blk["text"])
        elif kind in ("ul", "ol"):
            for item in blk["items"]:
                style_name = "List Number" if kind == "ol" else "List Bullet"
                add_runs(doc.add_paragraph(style=style_name), item)
        elif kind == "code":
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Pt(12)
            run = par.add_run("\n".join(blk["lines"]))
            run.font.name = "Consolas"
            run.font.size = Pt(8.6)
        elif kind == "table":
            cols = len(blk["header"])
            table = doc.add_table(rows=1, cols=cols)
            table.style = "Light Grid Accent 1"
            for i, cell in enumerate(blk["header"]):
                table.rows[0].cells[i].text = strip_markup(cell)
                for par in table.rows[0].cells[i].paragraphs:
                    for run in par.runs:
                        run.bold = True
            for row in blk["rows"]:
                cells = table.add_row().cells
                for i in range(cols):
                    cells[i].text = strip_markup(row[i]) if i < len(row) else ""
        elif kind == "quote":
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Pt(18)
            run = par.add_run(strip_markup(blk["text"]))
            run.italic = True
        elif kind == "diagram":
            par = doc.add_paragraph()
            run = par.add_run(f"[Diagram: {blk['key']} - lihat versi PDF untuk gambarnya]")
            run.italic = True
            run.font.size = Pt(9)
        elif kind == "hr":
            doc.add_paragraph("_" * 60).alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "newpage":
            doc.add_page_break()
    doc.save(str(out_path))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def read_sources() -> tuple[list[dict], str]:
    files = sorted(SRC_DIR.glob("*.md"))
    if not files:
        raise SystemExit(f"[docs] tidak ada sumber Markdown di {SRC_DIR}")
    blocks: list[dict] = []
    md_parts = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        blocks.extend(parse_markdown(text))
        md_parts.append(text.strip())
    return blocks, "\n\n".join(md_parts)


def font_preflight(blocks: list[dict]) -> None:
    """Pastikan semua karakter yang dipakai bisa dirender font terpilih."""
    choice = find_font(FONT_CANDIDATES)
    if choice is None:
        print("[docs] font: tidak ditemukan TrueType -> dipakai font inti (latin-1)")
        return
    family, paths = choice
    charset = font_charset(paths[0])
    if not charset:
        print(f"[docs] font: {family} (fontTools tidak ada, pemeriksaan glyph dilewati)")
        return
    used: set[str] = set()
    used_mono: set[str] = set()

    def add_text(chunk, target=None) -> None:
        (target if target is not None else used).update(str(chunk))

    for blk in blocks:
        if "text" in blk:
            add_text(blk["text"])
        for item in blk.get("items") or []:
            add_text(item)
        for cell in blk.get("header") or []:
            add_text(cell)
        for row in blk.get("rows") or []:
            for cell in row:
                add_text(cell)
        for line in blk.get("lines") or []:
            add_text(line, used_mono)
    def report(label: str, font_name: str, chars: set[str], available: set[str]) -> None:
        missing = {c for c in chars if ord(c) >= 128 and c not in available}
        replaced = {c for c in missing if c in SYMBOL_MAP}
        dropped = missing - replaced
        total = len({c for c in chars if ord(c) >= 128})
        print(f"[docs] font {label} ({font_name}): {total} karakter non-ASCII "
              f"| dipetakan: {len(replaced)} | dibuang: {len(dropped)}")
        if replaced:
            print("[docs]   dipetakan:", " ".join(f"U+{ord(c):04X}" for c in sorted(replaced)))
        if dropped:
            print("[docs]   dibuang  :", " ".join(f"U+{ord(c):04X}" for c in sorted(dropped)),
                  "(emoji -> hilang dari PDF, tetap ada di Markdown)")

    report("teks", family, used, charset)
    mono_choice = find_font(MONO_CANDIDATES)
    if mono_choice is not None:
        report("kode", mono_choice[0], used_mono, font_charset(mono_choice[1][0]))


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Domino Analyzer Pro docs")
    ap.add_argument("--check-fonts", action="store_true", help="hanya cek glyph")
    ap.add_argument("--no-docx", action="store_true", help="lewati DOCX")
    ap.add_argument("--no-md", action="store_true", help="lewati Markdown gabungan")
    args = ap.parse_args()

    blocks, combined = read_sources()
    font_preflight(blocks)
    if args.check_fonts:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.no_md:
        front = (
            f"# {TITLE}\n\n"
            f"**{SUBTITLE}**\n\n"
            f"by **{AUTHOR}**\n\n"
            f"*Versi aplikasi {APP_VERSION} · dokumen dibangun {BUILD_DATE}*\n\n"
            "---\n\n"
            "Dokumen ini adalah penjelasan lengkap sekaligus panduan pakai untuk aplikasi\n"
            "**Domino Analyzer Pro** — analisis langkah domino 28 kartu dengan mesin simulasi\n"
            "Monte-Carlo C++20, server API Python, dan antarmuka web PWA.\n\n"
            "Cara membaca: Bagian I-V untuk pemakaian sehari-hari, Bagian VI-VII untuk isi\n"
            "mesin dan pengujian, Bagian VIII-IX untuk strategi dan rujukan API, Bagian X\n"
            "untuk pemecahan masalah serta lampiran.\n\n"
            "Diagram pada buku ini digambar oleh pembangun PDF, sehingga di versi Markdown\n"
            "penandanya masih berupa komentar `<!--DIAGRAM:...-->`.\n\n"
            "---\n\n"
        )
        md_path = OUT_DIR / f"{BOOK_STEM}.md"
        md_path.write_text(front + combined + "\n", encoding="utf-8")
        print(f"[docs] markdown -> {md_path.relative_to(ROOT)}")

    pdf_path = OUT_DIR / f"{BOOK_STEM}.pdf"

    # Dua lintasan. Mekanisme placeholder fpdf2 menggambar isinya tepat di posisi
    # pembuatan placeholder (di sini halaman sampul) sehingga daftar isi
    # menumpuk di atas sampul, jadi jalur itu tidak dipakai. Lintasan pertama
    # mengukur nomor halaman setiap bagian dengan halaman daftar isi kosong;
    # lintasan kedua mencetak daftar isi sebenarnya pada jumlah halaman yang
    # sama, sehingga nomor halaman yang tercetak pasti cocok.
    names = outline_names(blocks)
    sizes = toc_page_sizes([lvl for lvl, _ in names])
    toc_pages = len(sizes)

    def build_book(toc_entries: list[tuple[int, str, int]] | None, cover_meta: str = ""):
        """Bangun seluruh buku. Satu-satunya beda antar lintasan adalah angka
        nomor halaman di daftar isi, sehingga paginasi keduanya identik."""
        bk = BookPDF()
        bk.cover(cover_meta)
        rows = toc_entries if toc_entries is not None else [
            (lvl, nm, 0) for lvl, nm in names]
        start = 0
        for n, size in enumerate(sizes):
            bk.draw_toc_page(rows[start:start + size], first=(n == 0))
            start += size
        bk.render(blocks)
        bk.pdf.alias_nb_pages()
        return bk

    measured = build_book(None)
    if len(measured.outline) != len(names):
        raise SystemExit("[docs] jumlah entri daftar isi tidak cocok dengan kerangka")
    if [(lvl, nm) for lvl, nm, _ in measured.outline] != names:
        raise SystemExit("[docs] kerangka daftar isi berbeda dari hasil render")
    meta = (f"{sum(1 for lvl, _, _ in measured.outline if lvl == 0)} Bagian \u00b7 "
            f"{measured.figure_no} diagram \u00b7 {measured.pdf.page_no()} halaman")
    final = build_book(measured.outline, meta)
    if ([(lvl, nm) for lvl, nm, _ in final.outline]
            != [(lvl, nm) for lvl, nm, _ in measured.outline]):
        raise SystemExit("[docs] tata letak berubah antar lintasan — daftar isi tidak konsisten")
    if final.pdf.page_no() != measured.pdf.page_no():
        # Kalau ini terjadi, nomor halaman di daftar isi (diukur di lintasan
        # pertama) tidak lagi menggambarkan dokumen akhir.
        raise SystemExit("[docs] jumlah halaman berbeda antar lintasan "
                         f"({measured.pdf.page_no()} vs {final.pdf.page_no()})")
    final.pdf.output(str(pdf_path))
    print(f"[docs] pdf      -> {pdf_path.relative_to(ROOT)} "
          f"({len(final.outline)} bagian, daftar isi {toc_pages} halaman)")

    if not args.no_docx:
        docx_path = OUT_DIR / f"{BOOK_STEM}.docx"
        build_docx(blocks, docx_path)
        print(f"[docs] docx     -> {docx_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
