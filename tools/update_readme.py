#!/usr/bin/env python3
"""Update README.md documentation section based on docs/ structure."""

from __future__ import annotations

import re
from pathlib import Path

# Map doc files to their descriptions (order preserved)
DOC_ENTRIES: list[tuple[str, str, str]] = [
    (
        "docs/architecture.md",
        "Architecture",
        "AWS architecture diagram, traffic flows, module details",
    ),
    (
        "docs/variables.md",
        "Variables",
        "Full variable reference for bootstrap, workspaces, and GitHub Actions",
    ),
    (
        "docs/certification-management.md",
        "Certification Management",
        "SHA-256 verification, status/visibility controls",
    ),
    ("docs/admin-setup.md", "Admin Setup", "Admin authentication, user management"),
    (
        "tests/README.md",
        "Test Suite",
        "Test structure, coverage goals, writing new tests",
    ),
]


def _generate_docs_section(root: Path) -> str:
    lines = [
        "## Documentation",
        "",
        "| Document | Description |",
        "|----------|-------------|",
    ]
    for rel_path, title, desc in DOC_ENTRIES:
        if (root / rel_path).exists():
            lines.append(f"| [{title}]({rel_path}) | {desc} |")
    lines.append("")
    return "\n".join(lines)


def update_readme() -> bool:
    root = Path(__file__).resolve().parent.parent
    readme = root / "README.md"
    if not readme.exists():
        print("README.md not found")
        return False

    content = readme.read_text(encoding="utf-8")
    docs_section = _generate_docs_section(root)

    pattern = r"## Documentation\n.*?(?=\n## |\Z)"
    if not re.search(pattern, content, flags=re.DOTALL):
        print("Documentation section not found in README.md")
        return False

    updated = re.sub(pattern, docs_section.rstrip() + "\n", content, flags=re.DOTALL)
    if updated == content:
        print("README.md documentation section is up to date")
        return True

    readme.write_text(updated, encoding="utf-8")
    print("Updated README.md documentation section")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if update_readme() else 1)
