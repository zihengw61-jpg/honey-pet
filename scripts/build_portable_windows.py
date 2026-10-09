#!/usr/bin/env python3
"""Assemble an offline Windows x64 pet without executing Windows binaries.

Runs on Linux, macOS, or Windows using only the standard library and pip for
optional downloads. The official Pythonw binary becomes the GUI launcher;
python312._pth and app/sitecustomize.py start the app with isolated packages.
"""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PYTHON_VERSION = "3.12.10"
QT_VERSION = "6.8.3"
PACKAGES = {
    "python.3.12.10.nupkg": "0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8",
    "PySide6_Essentials-6.8.3-cp39-abi3-win_amd64.whl": "3c0fae5550aff69f2166f46476c36e0ef56ce73d84829eac4559770b0c034b07",
    "shiboken6-6.8.3-cp39-abi3-win_amd64.whl": "bca3a94513ce9242f7d4bbdca902072a1631888e0aa3a8711a52cc5dbe93588f",
}
RUNTIME_URL = f"https://api.nuget.org/v3-flatcontainer/python/{PYTHON_VERSION}/python.{PYTHON_VERSION}.nupkg"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def download_packages(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    runtime = cache / f"python.{PYTHON_VERSION}.nupkg"
    if not runtime.exists():
        print(f"Downloading official Python {PYTHON_VERSION} runtime…")
        # urllib preserves inherited proxy settings and verifies TLS normally.
        with urllib.request.urlopen(RUNTIME_URL, timeout=90) as response, runtime.open("wb") as destination:
            shutil.copyfileobj(response, destination)
    if any(not (cache / name).exists() for name in PACKAGES if name.endswith(".whl")):
        subprocess.run([
            sys.executable, "-m", "pip", "download", "--index-url", "https://pypi.org/simple",
            "--dest", str(cache), "--only-binary=:all:", "--platform", "win_amd64",
            "--python-version", "312", "--implementation", "cp", "--abi", "cp312",
            f"PySide6-Essentials=={QT_VERSION}", f"shiboken6=={QT_VERSION}",
        ], check=True)


def verify_packages(cache: Path) -> None:
    for name, expected in PACKAGES.items():
        path = cache / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}; use --download to fetch pinned inputs.")
        actual = digest(path)
        if actual != expected:
            raise ValueError(f"SHA-256 mismatch for {name}: {actual}")
        with zipfile.ZipFile(path) as archive:
            failed = archive.testzip()
            if failed:
                raise ValueError(f"Damaged package member: {name}/{failed}")
            if name.endswith(".whl"):
                metadata_file = next(item for item in archive.namelist() if item.endswith(".dist-info/METADATA"))
                metadata = BytesParser().parsebytes(archive.read(metadata_file))
                if metadata["Version"] != QT_VERSION:
                    raise ValueError(f"Unexpected Qt package version: {metadata['Version']}")
        print(f"Verified {name} ({path.stat().st_size:,} bytes)")


def extract_checked(archive: zipfile.ZipFile, destination: Path, *, runtime: bool = False) -> None:
    for member in archive.infolist():
        name = PurePosixPath(member.filename)
        if name.is_absolute() or ".." in name.parts or "\\" in member.filename:
            raise ValueError(f"Unsafe archive path: {member.filename}")
        if "__pycache__" in name.parts or name.suffix == ".pyc":
            continue
        if runtime:
            if not name.parts or name.parts[0] != "tools":
                continue
            name = PurePosixPath(*name.parts[1:])
            if not name.parts:
                continue
            # Runtime pip is not needed offline. Dependencies come from pinned wheels.
            if name.parts[:2] == ("Lib", "site-packages") or name.parts[0] == "Scripts":
                continue
        target = destination.joinpath(*name.parts)
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)


def verify_pe_x64(path: Path) -> None:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError(f"Not a Windows executable: {path}")
        stream.seek(0x3C)
        offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0" or struct.unpack("<H", stream.read(2))[0] != 0x8664:
            raise ValueError(f"Not a Windows x64 binary: {path}")


def write_windows_text(path: Path, text: str) -> None:
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def assemble(cache: Path, destination: Path) -> None:
    with zipfile.ZipFile(cache / f"python.{PYTHON_VERSION}.nupkg") as archive:
        extract_checked(archive, destination, runtime=True)
    for name in PACKAGES:
        if name.endswith(".whl"):
            with zipfile.ZipFile(cache / name) as archive:
                extract_checked(archive, destination / "Lib/site-packages")

    app = destination / "app"
    app.mkdir()
    shutil.copy2(ROOT / "main.py", app / "main.py")
    shutil.copytree(ROOT / "foxpet", app / "foxpet", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if (ROOT / "assets").is_dir():
        shutil.copytree(ROOT / "assets", app / "assets", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT / "scripts/portable_bootstrap.py", app / "sitecustomize.py")
    (destination / "pythonw.exe").rename(destination / "HoneyPet.exe")
    write_windows_text(destination / "python312._pth", ".\nDLLs\nLib\nLib\\site-packages\napp\nimport site\n")
    write_windows_text(destination / "启动小狐狸.bat", """@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "%~dp0HoneyPet.exe"
""")
    write_windows_text(destination / "诊断启动.bat", r"""@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动小狐狸。关闭小狐狸后，将显示退出状态。
"%~dp0python.exe" "%~dp0app\main.py"
echo.
echo 程序退出状态：%errorlevel%
echo 日志位置：%LOCALAPPDATA%\HoneyPet
pause
""")
    write_windows_text(destination / "先读我.txt", r"""HoneyPet · 小狐狸桌面宠物

适用 Windows 10 / 11，64 位电脑。
请先把压缩包完整解压到一个文件夹，然后双击 HoneyPet.exe。
不需要安装 Python；使用时不需要联网。
请保留整个文件夹，不要单独把 EXE 文件移出去。

小狐狸默认在桌面右下角探出脑袋；点击后钻出来。
通过右键菜单或系统托盘中的小狐狸图标，可以收起或退出。
如果没有正常启动，请双击“诊断启动.bat”查看错误。
启动日志保存在 %LOCALAPPDATA%\HoneyPet\launcher.log。

此便携包在 Linux 上组装，未在真实 Windows 桌面进行运行验证。
随包附带完整应用源码；第三方运行库和许可说明在 THIRD_PARTY.txt。
""")
    for source_name in ("README.md", "WINDOWS.md", "LICENSE"):
        if (ROOT / source_name).is_file():
            shutil.copy2(ROOT / source_name, destination / source_name)
    shutil.copytree(ROOT / "third_party", destination / "third_party")
    shutil.copy2(ROOT / "third_party/THIRD_PARTY.txt", destination / "THIRD_PARTY.txt")
    manifest = {
        "platform": "Windows 10/11 x64", "python": PYTHON_VERSION,
        "PySide6-Essentials": QT_VERSION, "shiboken6": QT_VERSION,
        "launcher": "Unmodified official Pythonw executable, renamed HoneyPet.exe",
        "windows_execution_tested": False,
        "sources": {"python": RUNTIME_URL, "wheels": "https://pypi.org/"},
        "input_sha256": PACKAGES,
    }
    (destination / "distribution.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for relative in (
        "HoneyPet.exe", "python.exe", "python312.dll", "DLLs/_ctypes.pyd",
        "Lib/site-packages/PySide6/QtCore.pyd", "Lib/site-packages/PySide6/QtGui.pyd",
        "Lib/site-packages/PySide6/QtWidgets.pyd", "Lib/site-packages/PySide6/plugins/platforms/qwindows.dll",
    ):
        verify_pe_x64(destination / relative)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / ".build/windows/downloads")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/HoneyPet-Windows-x64.zip")
    parser.add_argument("--download", action="store_true", help="Fetch pinned runtime and wheels if absent")
    parser.add_argument("--check-inputs-only", action="store_true", help="Verify input hashes and archives without building")
    args = parser.parse_args()
    if args.download:
        download_packages(args.cache)
    verify_packages(args.cache)
    if args.check_inputs_only:
        return 0
    if not (ROOT / "main.py").is_file() or not (ROOT / "foxpet").is_dir():
        parser.error("Application main.py and foxpet/ must exist before packaging")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="honeypet-portable-", dir=args.output.parent) as temporary:
        pet_dir = Path(temporary) / "HoneyPet"
        pet_dir.mkdir()
        assemble(args.cache, pet_dir)
        temporary_zip = Path(temporary) / "portable.zip"
        with zipfile.ZipFile(temporary_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(pet_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(Path(temporary)))
        with zipfile.ZipFile(temporary_zip) as archive:
            failed = archive.testzip()
            if failed:
                raise ValueError(f"Output ZIP is damaged: {failed}")
        temporary_zip.replace(args.output)
    print(f"Created {args.output} ({args.output.stat().st_size / 1024 ** 2:.1f} MiB)")
    print(f"SHA-256: {digest(args.output)}")
    print("Windows binaries verified as x64; native Windows execution has not been tested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
