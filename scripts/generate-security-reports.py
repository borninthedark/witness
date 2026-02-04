#!/usr/bin/env python3
"""Generate Markdown security reports with timestamped filenames."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

STAMP = datetime.now()
STAMP_SUFFIX = STAMP.strftime("%Y%m%d-%H%M%S")


def _load_json_report(file_path: Path) -> Any | None:
    """Load JSON data from a path if it exists and is non-empty."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        return None
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def _write(path: Path, content: str) -> None:
    """Write a report to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"✓ Wrote report {path}")


def _now() -> str:
    """Return a consistent timestamp for this run."""
    return STAMP.strftime("%Y-%m-%d %H:%M:%S")


def _timestamped_path(directory: Path, stem: str) -> Path:
    """Generate a timestamped Markdown filename."""
    return directory / f"{stem}-{STAMP_SUFFIX}.md"


def generate_bandit_report(src: Path, dest: Path) -> Path | None:
    """Convert Bandit JSON output into Markdown."""
    data = _load_json_report(src)
    if not data:
        return None

    results = data.get("results", [])
    metrics = data.get("metrics", {})
    severity_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for result in results:
        sev = result.get("issue_severity", "LOW")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    total = len(results)
    content = [
        "# Bandit SAST Report",
        "",
        f"**Status:** {'✅ PASS' if total == 0 else '❌ FAIL'}",
        f"**Last Updated:** {_now()}",
        f"**Total Issues:** {total}",
        "",
        "## Summary",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 High | {severity_counts.get('HIGH', 0)} |",
        f"| 🟡 Medium | {severity_counts.get('MEDIUM', 0)} |",
        f"| 🟢 Low | {severity_counts.get('LOW', 0)} |",
        "",
        "## Files Scanned",
        "",
        f"- **Total LOC:** {metrics.get('_totals', {}).get('loc', 'N/A')}",
        f"- **Files with Issues:** {len(set(r.get('filename') for r in results))}",
        "",
        "## Findings",
        "",
    ]

    if total == 0:
        content.append("✅ No security issues detected!")
    else:
        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
        for idx, result in enumerate(results, 1):
            code = result.get("code", "N/A").strip()
            location_value = result.get("filename", "N/A")
            line_value = result.get("line_number", "N/A")
            severity = result.get("issue_severity", "N/A")
            confidence = result.get("issue_confidence", "N/A")
            content.extend(
                [
                    f"### {idx}. {emoji.get(result.get('issue_severity', 'LOW'), '⚪')} "
                    f"{result.get('issue_text', 'Unknown')}",
                    "",
                    f"- **Severity:** {severity}",
                    f"- **Confidence:** {confidence}",
                    f"- **Location:** `{location_value}:{line_value}`",
                    f"- **CWE:** {result.get('issue_cwe', {}).get('id', 'N/A')}",
                    "",
                    "**Code:**",
                    "```python",
                    code,
                    "```",
                    "",
                    (
                        "**Recommendation:** "
                        f"{result.get('more_info', 'Review and address the issue.')}"
                    ),
                    "",
                    "---",
                    "",
                ]
            )

    _write(dest, "\n".join(content))
    return dest


def generate_semgrep_report(src: Path, dest: Path) -> Path | None:
    """Convert Semgrep JSON into Markdown."""
    data = _load_json_report(src)
    if not data:
        return None

    results = data.get("results", [])
    severity_counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for result in results:
        severity = result.get("extra", {}).get("severity", "INFO")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    content = [
        "# Semgrep SAST Report",
        "",
        f"**Status:** {'✅ PASS' if not results else '❌ FAIL'}",
        f"**Last Updated:** {_now()}",
        f"**Total Issues:** {len(results)}",
        "",
        "## Summary",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Error | {severity_counts.get('ERROR', 0)} |",
        f"| 🟡 Warning | {severity_counts.get('WARNING', 0)} |",
        f"| 🟢 Info | {severity_counts.get('INFO', 0)} |",
        "",
        "## Findings",
        "",
    ]

    if not results:
        content.append("✅ No Semgrep findings!")
    else:
        for idx, result in enumerate(results, 1):
            rule_id = result.get("check_id", "unknown")
            message = result.get("extra", {}).get("message", "No details provided")
            location = result.get("path", "N/A")
            start = result.get("start", {})
            end = result.get("end", {})
            line_range = f"{start.get('line', '?')} - {end.get('line', '?')}"
            content.extend(
                [
                    f"### {idx}. {rule_id}",
                    "",
                    f"- **Message:** {message}",
                    f"- **File:** `{location}:{line_range}`",
                    "",
                    "---",
                    "",
                ]
            )

    _write(dest, "\n".join(content))
    return dest


def generate_json_table_report(
    src: Path,
    dest: Path,
    title: str,
    key: str,
    columns: list[tuple[str, str]],
    ok_message: str,
) -> Path | None:
    """Transform tabular security outputs (Safety, pip-audit, etc.)."""
    data = _load_json_report(src)
    if not data:
        return None

    rows = data.get(key, [])
    content = [
        f"# {title}",
        "",
        f"**Last Updated:** {_now()}",
        f"**Total Findings:** {len(rows)}",
        "",
    ]

    if not rows:
        content.append(ok_message)
    else:
        header = " | ".join(name for name, _ in columns)
        content.append(f"| {header} |")
        content.append("|" + "|".join(["---"] * len(columns)) + "|")
        for row in rows:
            content.append(
                "| "
                + " | ".join(str(row.get(field, "N/A")) for _, field in columns)
                + " |"
            )

    _write(dest, "\n".join(content))
    return dest


def generate_summary_report(
    reports_dir: Path, generated: dict[str, Path | None]
) -> None:
    """Write the consolidated summary page."""
    entries = [
        ("SAST", "Bandit", generated.get("bandit")),
        ("SAST", "Semgrep", generated.get("semgrep")),
        ("SCA", "Safety", generated.get("safety")),
        ("SCA", "pip-audit", generated.get("pip_audit")),
        ("License", "pip-licenses", generated.get("licenses")),
    ]

    lines = [
        "# Security Scan Summary",
        "",
        f"**Generated:** {_now()}",
        f"**Run ID:** `{STAMP_SUFFIX}`",
        "",
        "## Scan Status",
        "",
        "| Category | Tool | Status | Report |",
        "|----------|------|--------|--------|",
    ]

    for category, tool, report_path in entries:
        if report_path and report_path.exists():
            rel_path = report_path.relative_to(reports_dir).as_posix()
            link = f"[View]({rel_path})"
            exists = True
        else:
            link = "—"
            exists = False
        lines.append(f"| {category} | {tool} | {'✅' if exists else '⏭️'} | {link} |")

    lines.extend(
        [
            "",
            "## Quick Actions",
            "",
            "- Regenerate: `python scripts/generate-security-reports.py`",
            f"- Reports timestamp: `{STAMP_SUFFIX}`",
        ]
    )

    summary_path = reports_dir / f"SECURITY_SUMMARY-{STAMP_SUFFIX}.md"
    _write(summary_path, "\n".join(lines))


def main() -> None:
    """Entry point for CLI usage."""
    repo_root = Path(__file__).resolve().parent.parent
    reports_dir = repo_root / "reports"
    sast_dir = reports_dir / "sast"
    sca_dir = reports_dir / "sca"

    generated: dict[str, Path | None] = {}

    generated["bandit"] = generate_bandit_report(
        sast_dir / "bandit.json", _timestamped_path(sast_dir, "bandit")
    )

    generated["semgrep"] = generate_semgrep_report(
        sast_dir / "semgrep.json", _timestamped_path(sast_dir, "semgrep")
    )

    generated["safety"] = generate_json_table_report(
        sca_dir / "safety.json",
        _timestamped_path(sca_dir, "safety"),
        "Safety SCA Report",
        "issues",
        [
            ("Package", "package"),
            ("Installed", "installed_version"),
            ("Vulnerable", "vulnerable_spec"),
            ("Fix Version", "fixed_versions"),
        ],
        "✅ Safety did not detect any issues!",
    )

    generated["pip_audit"] = generate_json_table_report(
        sca_dir / "pip-audit.json",
        _timestamped_path(sca_dir, "pip-audit"),
        "pip-audit SCA Report",
        "dependencies",
        [
            ("Package", "name"),
            ("Version", "version"),
            ("Vulns", "vulns"),
        ],
        "✅ pip-audit did not detect known vulnerabilities!",
    )

    generated["licenses"] = generate_json_table_report(
        sca_dir / "licenses.json",
        _timestamped_path(sca_dir, "licenses"),
        "License Compliance Report",
        "packages",
        [
            ("Package", "Name"),
            ("Version", "Version"),
            ("License", "License"),
        ],
        "✅ All packages use approved licenses!",
    )

    generate_summary_report(reports_dir, generated)
    print("\n✅ Security report generation complete.")


if __name__ == "__main__":
    main()
