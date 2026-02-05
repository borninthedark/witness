#!/usr/bin/env python3
"""Update README.md documentation section based on docs/ structure."""

from __future__ import annotations

import re
from pathlib import Path

DOC_CATEGORIES = {
    "Architecture": ["overview.md", "aks-network-architecture.md"],
    "Deployment": ["deployment.md"],
    "Operations": ["tooling.md", "admin-setup.md", "status-dashboard-setup.md"],
    "Features": ["certification-management.md"],
}

DOC_DESCRIPTIONS = {
    "overview.md": "Project structure, data sources, application flow.",
    "aks-network-architecture.md": "Network diagram, traffic flows, troubleshooting.",
    "deployment.md": "Container, Compose, AKS, systemd deployment.",
    "tooling.md": "Testing, linting, pre-commit workflows.",
    "admin-setup.md": "Admin authentication, user management.",
    "status-dashboard-setup.md": "Prometheus, Grafana, public status page.",
    "certification-management.md": "SHA-256 verification, status/visibility controls.",
}

APP_DOCS: list[tuple[str, str, str]] = [
    ("tests/README.md", "Test Suite Guide", "Test structure, coverage, writing tests."),
]


def _extract_title(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^#\s+(.+)$", line.strip())
            if match:
                return match.group(1)
    except FileNotFoundError:
        return None
    return None


def _extract_description(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    title_seen = False
    for line in lines:
        if not title_seen:
            if re.match(r"^#\s+", line):
                title_seen = True
            continue
        if not line.strip():
            continue
        if re.match(r"^#+\s+", line):
            continue
        return line.strip()[:100]
    return None


def _generate_docs_section() -> str:
    root = Path(__file__).resolve().parent.parent
    docs_dir = root / "docs"
    lines = ["## 📚 Documentation", ""]
    for category, files in DOC_CATEGORIES.items():
        lines.append(f"### {category}")
        for file in files:
            path = docs_dir / file
            if not path.exists():
                continue
            title = _extract_title(path) or file.replace(".md", "").replace("_", " ")
            desc = (
                DOC_DESCRIPTIONS.get(file.lower())
                or _extract_description(path)
                or title
            )
            lines.append(f"- **[{title}](docs/{file})** - {desc}")
        lines.append("")
    lines.append("### Application Documentation")
    for rel_path, title, desc in APP_DOCS:
        path = root / rel_path
        if path.exists():
            lines.append(f"- **[{title}]({rel_path})** - {desc}")
    lines.append("")
    return "\n".join(lines)


def update_readme() -> bool:
    root = Path(__file__).resolve().parent.parent
    readme = root / "README.md"
    if not readme.exists():
        print("README.md not found")
        return False
    content = readme.read_text(encoding="utf-8")
    docs_section = _generate_docs_section()
    pattern = (
        r"## 📚 Documentation.*?"
        r"(?=## License|## Tooling|## Deployment|## Observability|$)"
    )
    if not re.search(pattern, content, flags=re.DOTALL):
        print("Documentation section not found in README.md")
        return False
    updated = re.sub(pattern, docs_section + "\n", content, flags=re.DOTALL)
    readme.write_text(updated, encoding="utf-8")
    print("Updated README.md documentation section")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if update_readme() else 1)
