from __future__ import annotations

from fitness.services import report_status


def test_collect_precommit_statuses_handles_missing(tmp_path):
    statuses = report_status.collect_precommit_statuses(
        hooks=["pytest"], log_dir=tmp_path
    )
    assert len(statuses) == 1
    assert statuses[0].name == "pytest"
    assert statuses[0].status == "missing"


def test_collect_precommit_statuses_reads_latest(tmp_path):
    log_dir = tmp_path
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pytest-20240101T000000Z.log"
    log_file.write_text(
        "[2024-01-01 12:00:00] Hook 'pytest' starting\n"
        "[2024-01-01 12:00:05] Hook 'pytest' completed with exit code 0\n",
        encoding="utf-8",
    )
    statuses = report_status.collect_precommit_statuses(
        hooks=["pytest"], log_dir=log_dir
    )
    assert statuses[0].status == "passed"
    assert statuses[0].exit_code == 0


def test_load_security_summary_parses_rows(tmp_path):
    reports_dir = tmp_path
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary = reports_dir / "SECURITY_SUMMARY-20240101-000000-00.md"
    summary.write_text(
        "**Generated:** 2024-01-01 00:00:00\n"
        "**Run ID:** `20240101`\n\n"
        "| Category | Tool | Status | Report |\n"
        "|----------|------|--------|--------|\n"
        "| SAST | Bandit | ✅ | [View](sast/bandit.md) |\n",
        encoding="utf-8",
    )
    data = report_status.load_security_summary(summary_dir=reports_dir)
    assert data["entries"][0]["tool"] == "Bandit"
    assert data["entries"][0]["status"] == "✅"
