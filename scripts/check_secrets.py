#!/usr/bin/env python3
"""Lightweight secret scanning utility."""

from __future__ import annotations

import re
import subprocess  # nosec B404 - required for invoking git/grep commands
import sys
from pathlib import Path

from scripts.utils import Colors, print_colored

AZURE_SUBSCRIPTION_PATTERN = (
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)


def run_git_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 - fixed command template, no user input
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


def _header(message: str) -> None:
    print(f"\n{Colors.YELLOW}{message}{Colors.NC}")


def check_sensitive_files() -> bool:
    _header("Checking for sensitive file patterns...")
    patterns = [
        r"\.env(\.|$)",
        r"\.pem$",
        r"\.key$",
        r"_rsa$",
        r"\.pfx$",
        r"\.p12$",
        r"sp-credentials\.json$",
        r"credentials\.json$",
        r"terraform\.tfvars$",
        r"\.vault_password$",
        r"kubeconfig$",
        r"\.kubeconfig$",
        r"k3s\.yaml$",
        r"auth\.json$",
        r"service-account.*\.json$",
    ]

    staged = subprocess.run(  # nosec B607,B603 - fixed git invocation
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()

    flagged = False
    for file_name in staged:
        for pattern in patterns:
            if re.search(pattern, file_name):
                print_colored(f"✗ Sensitive file tracked: {file_name}", Colors.RED)
                flagged = True
                break

    if not flagged:
        print_colored("✓ No sensitive files tracked", Colors.GREEN)
    return flagged


def _grep(pattern: str, excludes: str = "") -> bool:
    cmd = ["git", "grep", "-n", "--color=never", "-E", pattern]
    if excludes:
        # Parse excludes like " -- ':(exclude).git' ':(exclude)*.md'"
        cmd.extend(["--", ":(exclude).git", ":(exclude)*.md"])
    result = run_git_command(cmd)
    if result.returncode == 0 and result.stdout.strip():
        print(result.stdout.strip())
        return True
    return False


def check_patterns() -> int:
    _header("Scanning repository for secret patterns...")
    checks = [
        ("AWS keys", r"AKIA[0-9A-Z]{16}"),
        ("Azure subscription IDs", AZURE_SUBSCRIPTION_PATTERN),
        ("Private keys", r"-----BEGIN (EC|RSA|DSA|OPENSSH|PRIVATE) KEY-----"),
        ("GitHub tokens", r"ghp_[A-Za-z0-9]{36}"),
        ("Slack tokens", r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
        ("JWT tokens", r"eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),
    ]

    failures = 0
    for label, pattern in checks:
        print(f"- {label}...", end=" ")
        if _grep(pattern, " -- ':(exclude).git' ':(exclude)*.md'"):
            print_colored("FOUND", Colors.RED)
            failures += 1
        else:
            print_colored("none", Colors.GREEN)
    return failures


def check_gitignore() -> None:
    _header("Verifying .gitignore coverage...")
    required = [
        "*.env",
        ".env*",
        "*.pem",
        "*.key",
        "terraform.tfvars",
        ".vault_password",
        "kubeconfig",
        "sp-credentials.json",
    ]
    gitignore = Path(".gitignore")
    if not gitignore.exists():
        print_colored("! .gitignore missing", Colors.YELLOW)
        return

    content = gitignore.read_text(encoding="utf-8")
    for pattern in required:
        if pattern not in content:
            print_colored(f"! Add '{pattern}' to .gitignore", Colors.YELLOW)
            break
    else:
        print_colored("✓ Critical patterns found", Colors.GREEN)


def main() -> None:
    print("Scanning repository for leaked secrets...")
    print("=" * 54)
    failures = 0

    if check_sensitive_files():
        failures += 1
    failures += check_patterns()
    check_gitignore()

    print("\n" + "=" * 54)
    if failures == 0:
        print_colored("✓ No potential secrets detected", Colors.GREEN)
    else:
        print_colored("✗ Potential secrets found! Please investigate.", Colors.RED)
        sys.exit(1)


if __name__ == "__main__":
    main()
