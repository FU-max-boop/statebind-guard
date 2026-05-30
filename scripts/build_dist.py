#!/usr/bin/env python3
"""Build StateBind Guard wheel and source distribution artifacts."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import setuptools.build_meta as build_meta


ROOT = Path(__file__).resolve().parents[1]


def clean_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def build_artifacts(out_dir: Path, *, clean: bool = True) -> list[Path]:
    if clean:
        clean_directory(out_dir)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)

    previous_cwd = Path.cwd()
    os.chdir(ROOT)
    try:
        wheel_name = build_meta.build_wheel(str(out_dir))
        sdist_name = build_meta.build_sdist(str(out_dir))
    finally:
        os.chdir(previous_cwd)

    artifacts = [out_dir / wheel_name, out_dir / sdist_name]
    missing = [str(path) for path in artifacts if not path.exists()]
    if missing:
        raise FileNotFoundError("Build backend reported missing artifacts: " + ", ".join(missing))
    return artifacts


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="dist",
        help="Output directory for release artifacts. Defaults to ./dist.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove existing files in the output directory before building.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir = out_dir.resolve()

    for artifact in build_artifacts(out_dir, clean=not args.no_clean):
        print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
