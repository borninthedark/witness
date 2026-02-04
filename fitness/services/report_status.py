"""Helpers for surfacing recent pre-commit hook results and security summaries."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(".precommit_logs")
SUMMARY_DIR = Path("reports")
LOG_PATTERN = re.compile(r"(?P<hook>.+)-(?P<stamp>\d{8}T\d{6}Z)\.log$")
TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


@dataclass
class HookStatus:
    """Lightweight representation of a hook invocation."""

    name: str
    status: str
    exit_code: int | None
    started_at: datetime | None
    completed_at: datetime | None
    log_excerpt: list[str]

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


def _parse_timestamp(text: str) -> datetime | None:
    match = re.search(r"\[(?P<stamp>[\d\-\:\s]+)\]", text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group("stamp"), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _parse_log(path: Path, hook_name: str) -> HookStatus:
    """Parse a single .precommit_logs file and extract status metadata."""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    exit_code: int | None = None
    status = "unknown"
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    for line in lines:
        if "starting" in line and hook_name in line:
            started_at = _parse_timestamp(line)
        elif "completed with exit code" in line and hook_name in line:
            completed_at = _parse_timestamp(line)
            try:
                exit_code = int(line.rsplit("exit code", 1)[-1].strip())
            except ValueError:
                exit_code = None
            status = "passed" if exit_code == 0 else "failed"
        elif "failed with exit code" in line and hook_name in line:
            completed_at = _parse_timestamp(line)
            try:
                exit_code = int(line.rsplit("exit code", 1)[-1].strip())
            except ValueError:
                exit_code = None
            status = "failed"
        elif "succeeded" in line and hook_name in line:
            completed_at = _parse_timestamp(line)
            status = "passed"
            exit_code = 0

    excerpt = lines[-12:] if lines else []
    return HookStatus(
        name=hook_name,
        status=status,
        exit_code=exit_code,
        started_at=started_at,
        completed_at=completed_at,
        log_excerpt=excerpt,
    )


def collect_precommit_statuses(
    hooks: Sequence[str] | None = None,
    log_dir: Path | None = None,
) -> list[HookStatus]:
    """Return the most recent log entry for each hook of interest."""
    hooks = hooks or ["pytest", "bandit", "flake8", "mypy", "trivy", "security-reports"]
    log_dir = log_dir or LOG_DIR
    latest: dict[str, tuple[datetime, Path]] = {}

    if log_dir.exists():
        for path in log_dir.glob("*.log"):
            match = LOG_PATTERN.match(path.name)
            if not match:
                continue
            hook = match.group("hook")
            if hook not in hooks:
                continue
            stamp = datetime.strptime(match.group("stamp"), TIMESTAMP_FORMAT)
            current = latest.get(hook)
            if current is None or stamp > current[0]:
                latest[hook] = (stamp, path)

    statuses: list[HookStatus] = []
    for hook in hooks:
        entry = latest.get(hook)
        if entry:
            statuses.append(_parse_log(entry[1], hook))
        else:
            statuses.append(
                HookStatus(
                    name=hook,
                    status="missing",
                    exit_code=None,
                    started_at=None,
                    completed_at=None,
                    log_excerpt=[],
                )
            )
    return statuses


def _parse_summary_rows(lines: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    link_pattern = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<href>[^\)]+)\)")
    for line in lines:
        if not line.startswith("|") or "Category" in line:
            continue
        # Skip separator lines (contain only |, -, and spaces)
        if all(c in "|- " for c in line.strip()):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 4:
            continue
        href = ""
        label = ""
        match = link_pattern.match(parts[3])
        if match:
            href = match.group("href")
            label = match.group("label")
        rows.append(
            {
                "category": parts[0],
                "tool": parts[1],
                "status": parts[2],
                "link_href": href,
                "link_label": label,
            }
        )
    return rows


def load_security_summary(summary_dir: Path | None = None) -> dict[str, object]:
    """Read the most recent SECURITY_SUMMARY report if available."""
    summary_dir = summary_dir or SUMMARY_DIR
    if not summary_dir.exists():
        return {}
    candidates = list(summary_dir.glob("SECURITY_SUMMARY-*.md"))
    if not candidates:
        return {}
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    content = latest.read_text(encoding="utf-8", errors="ignore").splitlines()
    generated_line = next(
        (line for line in content if line.startswith("**Generated:**")), ""
    )
    generated = generated_line.replace("**Generated:**", "").strip().strip("*")
    run_id_line = next((line for line in content if line.startswith("**Run ID:**")), "")
    run_id = run_id_line.replace("**Run ID:**", "").strip().strip("*`")
    rows = _parse_summary_rows(content)
    return {
        "generated": generated,
        "run_id": run_id or latest.stem,
        "entries": rows,
        "filename": latest.name,
    }
