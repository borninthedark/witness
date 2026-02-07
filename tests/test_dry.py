from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "tools"
CHECK_DRY_PATH = SCRIPTS_DIR / "check-dry.py"


def _load_check_dry_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("check_dry", CHECK_DRY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load tools/check-dry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _format_duplicate(block1, block2, similarity: float) -> str:
    return (
        f"{block1.file_path}:{block1.start_line}-{block1.end_line} "
        f"<-> {block2.file_path}:{block2.start_line}-{block2.end_line} "
        f"(similarity={similarity:.0%})"
    )


def test_python_functions_do_not_duplicate():
    """
    Mirror the previous pre-commit check-dry hook so duplicates fail during pytest runs.
    """
    import pytest

    # Skip this test until check-dry.py script is implemented
    if not CHECK_DRY_PATH.exists():
        pytest.skip(f"check-dry.py script not found at {CHECK_DRY_PATH}")

    target_root = PROJECT_ROOT / "fitness"
    module = _load_check_dry_module()
    python_files = module.find_python_files(target_root)
    detector = module.DuplicationDetector(min_lines=6, similarity_threshold=0.8)
    detector.find_duplicates(python_files, use_functions=True)

    duplicate_descriptions = [
        _format_duplicate(block1, block2, similarity)
        for block1, block2, similarity in detector.duplicates
    ]
    assert not duplicate_descriptions, "Duplicate functions found:\n" + "\n".join(
        duplicate_descriptions
    )
