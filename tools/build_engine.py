#!/usr/bin/env python3
"""Build the C++ domino engine.

Usage:
    python tools/build_engine.py [--force] [--debug]

Locates a C++ compiler in this order:
    1. MSVC (cl.exe) via vswhere + vcvars64.bat  -> bin/domino_engine.exe
    2. g++                                        -> bin/domino_engine
    3. clang++                                    -> bin/domino_engine
"""
from __future__ import annotations

import argparse
import os
import pathlib
import platform
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "engine" / "domino_engine.cpp"
BIN_DIR = ROOT / "bin"


def log(msg: str) -> None:
    print(f"[build] {msg}")


def run(cmd: list[str] | str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", **kw)


def find_msvc() -> tuple[str, list[str]] | None:
    """Return (cl_path, setup_env_prefix_cmd) for MSVC via vswhere."""
    vswhere = (
        r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
    )
    if not os.path.exists(vswhere):
        return None
    try:
        res = run([
            vswhere, "-latest", "-products", "*",
            "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property", "installationPath",
        ])
        install = res.stdout.strip().splitlines()[0].strip() if res.stdout.strip() else ""
    except OSError:
        return None
    if not install:
        return None
    vcvars = pathlib.Path(install) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
    if not vcvars.exists():
        return None
    return str(vcvars)


def compiler_available(name: str) -> str | None:
    path = shutil.which(name)
    return path


def get_msvc_env(vcvars: str) -> dict[str, str] | None:
    r"""Run vcvars64.bat and capture the resulting environment variables.

    Uses shell=True with a plain string so cmd.exe receives
    `call "C:\...\vcvars64.bat" && set` without Python's list2cmdline
    mangling the quotes (cmd does not understand backslash-escaped quotes).
    """
    script = f'call "{vcvars}" && set'
    res = run(script, shell=True)
    if res.returncode != 0:
        return None
    env = {}
    for line in res.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key and not key.startswith(" "):
            env[key] = value
    return env or None


def build_with_msvc(vcvars: str, out: pathlib.Path, debug: bool) -> bool:
    if platform.system() != "Windows":
        return False
    env = get_msvc_env(vcvars)
    if env is None:
        log("gagal memuat environment MSVC dari vcvars64.bat")
        return False
    # CreateProcess looks up the executable on the PARENT's PATH, so resolve
    # cl.exe explicitly from the vcvars environment.
    cl = None
    for d in env.get("PATH", "").split(os.pathsep):
        cand = pathlib.Path(d) / "cl.exe"
        if cand.exists():
            cl = str(cand)
            break
    if cl is None:
        log("cl.exe tidak ditemukan di PATH hasil vcvars64")
        return False
    optimize = ["/Od", "/Zi"] if debug else ["/O2", "/DNDEBUG"]
    obj = out.with_suffix(".obj")
    cmd = [
        cl, "/nologo", "/EHsc", "/std:c++20", "/utf-8", *optimize,
        str(SRC), f"/Fe:{out}", f"/Fo:{obj}",
    ]
    res = run(cmd, env=env)
    if res.returncode != 0 or not out.exists():
        log("MSVC build failed:")
        print((res.stdout + res.stderr)[-2000:])
        return False
    return True


def build_with_gxx(compiler: str, out: pathlib.Path, debug: bool) -> bool:
    flags = ["-std=c++20", "-O2", "-DNDEBUG", "-Wall", "-Wextra"]
    if debug:
        flags = ["-std=c++20", "-O0", "-g", "-Wall", "-Wextra"]
    res = run([compiler, *flags, str(SRC), "-o", str(out)])
    if res.returncode != 0:
        log(f"{compiler} build failed:\n{res.stderr[-2000:]}")
        return False
    return True


def is_up_to_date(out: pathlib.Path) -> bool:
    return out.exists() and out.stat().st_mtime > SRC.stat().st_mtime


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the domino C++ engine")
    ap.add_argument("--force", action="store_true", help="rebuild even if up to date")
    ap.add_argument("--debug", action="store_true", help="build with debug symbols")
    args = ap.parse_args()

    if not SRC.exists():
        log(f"source not found: {SRC}")
        return 1
    BIN_DIR.mkdir(exist_ok=True)

    is_win = platform.system() == "Windows"
    out = BIN_DIR / ("domino_engine.exe" if is_win else "domino_engine")

    if not args.force and is_up_to_date(out):
        log(f"engine up to date: {out}")
        return 0

    # 1) MSVC
    vcvars = find_msvc()
    if vcvars:
        log(f"compiling with MSVC ({'debug' if args.debug else 'release'}) ...")
        if build_with_msvc(vcvars, out, args.debug):
            log(f"OK -> {out}")
            return 0
    else:
        log("MSVC tidak ditemukan (vswhere/vcvars64), mencoba compiler lain...")

    # 2) g++ / clang++
    for cc in ("g++", "clang++"):
        if compiler_available(cc):
            log(f"compiling with {cc} ...")
            if build_with_gxx(cc, out, args.debug):
                log(f"OK -> {out}")
                return 0

    log("TIDAK ADA compiler yang bisa dipakai (MSVC/g++/clang++).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
