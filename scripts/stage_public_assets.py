#!/usr/bin/env python3
"""Stage assets without personal configuration for native Windows builds."""

import argparse
from pathlib import Path
import shutil

from public_package import assert_public_distribution, assert_public_inputs, copy_public_tree


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    assert_public_inputs(ROOT)
    if args.audit:
        assert_public_distribution(args.audit)
        print("Public distribution credential-file audit passed.")
    if args.output:
        output = args.output.resolve()
        if output.parent != (ROOT / ".build").resolve() or output.name != "public-assets":
            parser.error("Asset staging output must be this project's .build/public-assets directory")
        if output.exists():
            shutil.rmtree(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if (ROOT / "assets").is_dir():
            copy_public_tree(ROOT / "assets", output)
        else:
            output.mkdir()
        print("Public assets staged; personal configuration and credential files excluded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
