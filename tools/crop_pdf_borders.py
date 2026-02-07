#!/usr/bin/env python3
"""
Utility to crop excessive borders/headings from exported certification PDFs.
Relies on pdftoppm + Pillow to rasterize each page at 300 PPI, detect the
bounding box of non-white content (skipping the noisy top browser header),
and write a trimmed PDF back into place.

This is intentionally ad-hoc for cleaning vendor-issued PDFs that ship with
large white margins or unwanted headers.
"""

from __future__ import annotations

import subprocess  # nosec B404 - required for calling pdftoppm
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

WHITE_THRESHOLD = 245  # pixel values >= threshold are treated as background
ROW_WINDOW = 200  # sliding window (pixels) used to smooth horizontal activity
COL_WINDOW = 120  # likewise for columns
ROW_THRESHOLD = 0.05  # proportion of non-white pixels needed to treat as content
COL_THRESHOLD = 0.02
MARGIN = 8  # extra pixels to keep after auto-cropping


def _smooth_activity(values: np.ndarray, window: int) -> np.ndarray:
    """Smooth a 1D activity array with a moving average."""
    if len(values) == 0:
        return values
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(values, kernel, mode="same")


def _find_bounds(values: np.ndarray, window: int, threshold: float) -> tuple[int, int]:
    """Return (start, end) indices where activity exceeds the threshold."""
    if len(values) == 0:
        return 0, 0
    smooth = _smooth_activity(values, window)
    hits = np.where(smooth > threshold)[0]
    if hits.size == 0:
        return 0, len(values)
    start = max(0, int(hits[0]))
    end = min(len(values), int(hits[-1]))
    return start, end


def _compute_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    """Determine a tight bounding box around real content for a page image."""
    gray = image.convert("L")
    arr = np.array(gray)
    mask = arr < WHITE_THRESHOLD
    row_activity = mask.mean(axis=1)
    col_activity = mask.mean(axis=0)

    top, bottom = _find_bounds(row_activity, ROW_WINDOW, ROW_THRESHOLD)
    left, right = _find_bounds(col_activity, COL_WINDOW, COL_THRESHOLD)

    return (
        max(0, left - MARGIN),
        max(0, top - MARGIN),
        min(image.width, right + MARGIN),
        min(image.height, bottom + MARGIN),
    )


def crop_pdf(pdf_path: Path) -> None:
    """Rasterize, crop, and rewrite a single PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        base = tmpdir_path / pdf_path.stem
        subprocess.run(  # nosec B607,B603 - deterministic tool invocation
            ["pdftoppm", "-r", "300", "-png", str(pdf_path), str(base)],
            check=True,
        )
        page_images = sorted(base.parent.glob(f"{base.name}-*.png"))
        if not page_images:
            raise RuntimeError(f"No rasterized pages generated for {pdf_path}")

        cropped_pages: list[Image.Image] = []
        for page in page_images:
            img = Image.open(page).convert("RGB")
            bbox = _compute_bbox(img)
            cropped_pages.append(img.crop(bbox))

        output_tmp = pdf_path.with_suffix(".tmp.pdf")
        first, *rest = cropped_pages
        first.save(
            output_tmp,
            "PDF",
            resolution=300.0,
            save_all=bool(rest),
            append_images=rest,
        )
        output_tmp.replace(pdf_path)


def main() -> None:
    targets = [
        Path("fitness/static/certs/az-104.pdf"),
        Path("fitness/static/certs/az-305.pdf"),
        Path("fitness/static/certs/az-400.pdf"),
        Path("fitness/static/certs/azure-transcript.pdf"),
    ]
    for pdf in targets:
        if not pdf.exists():
            print(f"[skip] {pdf} missing")
            continue
        print(f"Cropping {pdf} ...")
        crop_pdf(pdf)
        print(f"✓ Updated {pdf}")


if __name__ == "__main__":
    main()
