#!/usr/bin/env python3
"""Create a reproducible public source ZIP with no personal configuration."""

import argparse
import hashlib
from pathlib import Path
import stat
import tempfile
import zipfile

from public_package import assert_public_inputs, public_source_files


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/HoneyPet-Python-source.zip")
    args = parser.parse_args()
    assert_public_inputs(ROOT)
    files = sorted(public_source_files(ROOT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="honeypet-source-", dir=args.output.parent) as temporary:
        archive_path = Path(temporary) / "source.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in files:
                name = "HoneyPet-Python/" + path.relative_to(ROOT).as_posix()
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes(), compresslevel=6)
        with zipfile.ZipFile(archive_path) as archive:
            assert archive.testzip() is None
            for path in files:
                assert archive.read("HoneyPet-Python/" + path.relative_to(ROOT).as_posix()) == path.read_bytes()
        archive_path.replace(args.output)
    print(f"Created public source ZIP: {args.output} ({args.output.stat().st_size:,} bytes; {len(files)} files)")
    print(f"SHA-256: {hashlib.sha256(args.output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
