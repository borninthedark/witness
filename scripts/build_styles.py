#!/usr/bin/env python3
"""Compile SCSS sources into CSS for the public site."""

from pathlib import Path

import sass

SRC = Path("fitness/static/styles.scss")
DEST = Path("fitness/static/styles.css")


def compile_scss() -> Path:
    if not SRC.exists():
        raise FileNotFoundError(f"Missing SCSS file: {SRC}")
    css = sass.compile(filename=str(SRC), output_style="expanded")
    DEST.write_text(css, encoding="utf-8")
    return DEST


def main():
    dest = compile_scss()
    print(f"✓ Compiled {SRC} -> {dest}")


if __name__ == "__main__":
    main()
