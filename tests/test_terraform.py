"""Static analysis tests for Terraform modules.

Prevents misconfigurations that are hard to catch during plan/apply,
such as combining multiple TXT record values into a single Route 53
record resource (which breaks DNS validation for ProtonMail, SPF, etc.).
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DNS_MODULE = PROJECT_ROOT / "terraform" / "modules" / "dns" / "main.tf"

# Matches: resource "aws_route53_record" "name" { ... }
_RESOURCE_BLOCK_RE = re.compile(
    r'resource\s+"aws_route53_record"\s+"(\w+)"\s*\{', re.MULTILINE
)


def _extract_record_blocks(content: str) -> list[tuple[str, str]]:
    """Return (resource_name, block_body) for each aws_route53_record."""
    blocks = []
    for match in _RESOURCE_BLOCK_RE.finditer(content):
        name = match.group(1)
        start = match.end()
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            if content[pos] == "{":
                depth += 1
            elif content[pos] == "}":
                depth -= 1
            pos += 1
        blocks.append((name, content[start:pos]))
    return blocks


def _get_type(block_body: str) -> str | None:
    """Extract the type attribute from a resource block."""
    m = re.search(r'type\s*=\s*"(\w+)"', block_body)
    return m.group(1) if m else None


def _count_records_entries(block_body: str) -> int | None:
    """Count literal string entries in a records = [...] list.

    Returns None if no records attribute found (e.g. alias blocks).
    Only counts top-level quoted strings; ignores variables/expressions.
    """
    m = re.search(r"records\s*=\s*\[([^\]]*)\]", block_body, re.DOTALL)
    if not m:
        return None
    inner = m.group(1)
    return len(re.findall(r'"[^"]*"', inner))


def test_txt_records_have_single_value():
    """Each TXT aws_route53_record must contain exactly one value.

    Combining multiple TXT values (e.g. SPF + ProtonMail verification)
    into one record resource causes Route 53 to merge them, which breaks
    DNS validation for services that expect a standalone TXT record.
    """
    assert DNS_MODULE.exists(), f"DNS module not found at {DNS_MODULE}"
    content = DNS_MODULE.read_text()
    blocks = _extract_record_blocks(content)

    violations = []
    for name, body in blocks:
        if _get_type(body) != "TXT":
            continue
        count = _count_records_entries(body)
        if count is not None and count > 1:
            violations.append(
                f"aws_route53_record.{name} has {count} values in records "
                f"(each TXT record must be a separate resource)"
            )

    assert (
        not violations
    ), "TXT records must not combine multiple values:\n" + "\n".join(
        f"  - {v}" for v in violations
    )
