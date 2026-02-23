"""
Provides consistent console output, subprocess helpers, YAML loading with
newline coercion, hashing, slugification, color validation, optional DNS TXT
lookups, and QR code generation.
"""

from __future__ import annotations

import hashlib
import re
import shlex
import subprocess  # nosec B404 - utility helpers require subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

# from fitness.utils.yaml_helpers import load_yaml

# Optional dependencies (graceful degradation)
try:
    import yaml  # PyYAML
except Exception:  # pragma: no cover
    yaml = None

try:
    import qrcode  # qrcode[pil]
except Exception:  # pragma: no cover
    qrcode = None

try:
    import dns.resolver  # dnspython
except Exception:  # pragma: no cover
    dns = None


# -----------------------------
# Console colors & messaging
# -----------------------------
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"  # No Color


def print_colored(message: str, color: str = Colors.NC) -> None:
    print(f"{color}{message}{Colors.NC}")


def print_success(message: str) -> None:
    print_colored(f"✓ {message}", Colors.GREEN)


def print_error(message: str) -> None:
    print_colored(f"✗ {message}", Colors.RED)


def print_warning(message: str) -> None:
    print_colored(f"! {message}", Colors.YELLOW)


def print_info(message: str) -> None:
    print_colored(message, Colors.CYAN)


# -----------------------------
# Path & project helpers
# -----------------------------
def get_project_root() -> Path:
    """
    Returns the project root assuming this file is at `tools/utils.py`
    or similar — walks up two levels. Adjust as needed.
    """
    current = Path(__file__).resolve()
    return current.parents[2] if "fitness" in str(current) else current.parent.parent


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# -----------------------------
# Subprocess helpers
# -----------------------------
def run_command(
    command: str | list[str],
    capture_output: bool = False,
    check: bool = True,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess | None:
    """
    Execute a command and handle errors uniformly.
    """
    if isinstance(command, str):
        command_list: list[str] = shlex.split(command)
    else:
        command_list = list(command)

    try:
        result = subprocess.run(  # nosec B603 - commands constructed from trusted inputs
            command_list,
            capture_output=capture_output,
            text=True,
            check=check,
            cwd=cwd,
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            cmd_str = command if isinstance(command, str) else " ".join(command)
            print_error(f"Command failed: {cmd_str}")
            if e.stderr:
                print_colored(f"Error: {e.stderr}", Colors.RED)
            sys.exit(1)
        return None
    except FileNotFoundError:
        if check:
            cmd_str = command if isinstance(command, str) else command[0]
            print_error(f"Command not found: {cmd_str}")
            sys.exit(1)
        return None


def check_command_exists(command: str) -> bool:
    """
    Check if a command exists in PATH without invoking a shell.
    """
    from shutil import which

    return which(command) is not None


# -----------------------------
# YAML I/O
# -----------------------------
def _coerce_newlines(s: str) -> str:
    return s.replace("\\n", "\n") if "\\n" in s else s


def load_yaml(path: Path) -> dict:
    """
    Safe-load a YAML file with light newline coercion fallback.
    Returns {} if file missing or PyYAML unavailable.
    """
    if yaml is None or not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except Exception:
        data = yaml.safe_load(_coerce_newlines(raw))
    return data or {}


def dump_yaml(path: Path, data: dict) -> None:
    """
    Write YAML (safe_dump) if PyYAML present; otherwise raises RuntimeError.
    """
    if yaml is None:
        raise RuntimeError("PyYAML not installed; cannot write YAML.")
    ensure_dir(path.parent)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# -----------------------------
# Hashing & slugs
# -----------------------------
def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_slug_re = re.compile(r"[^a-z0-9\-]+")


def slugify(text: str, max_len: int = 80) -> str:
    """
    Lowercase, space->dash, strip invalids, collapse dashes.
    """
    s = text.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = _slug_re.sub("-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:max_len] if max_len > 0 else s


# -----------------------------
# Colors
# -----------------------------
_hex_color_re = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def is_hex_color(value: str) -> bool:
    return bool(_hex_color_re.match(value or ""))


def choose_color(value: str | None, default: str) -> str:
    """
    Returns a valid hex color (fallback to default if invalid/None).
    """
    return value if (isinstance(value, str) and is_hex_color(value)) else default


# -----------------------------
# DNS TXT (optional, dnspython)
# -----------------------------
def dns_txt(name: str) -> list[str]:
    """
    Resolve TXT records for a name. Returns [] if dnspython missing or errors occur.
    """
    try:
        if dns is None:
            return []
        answers = dns.resolver.resolve(name, "TXT")
        out: list[str] = []
        for r in answers:
            for b in r.strings:  # type: ignore[attr-defined]
                out.append(
                    b.decode("utf-8") if isinstance(b, (bytes, bytearray)) else str(b)
                )
        return out
    except Exception:
        return []


def has_txt_value(name: str, expected: str) -> bool:
    expected = expected.strip()
    return any(t.strip() == expected for t in dns_txt(name))


# -----------------------------
# QR generation (optional)
# -----------------------------
def write_qr_png(
    data: str, out_path: Path, box_size: int = 8, border: int = 2
) -> Path | None:
    """
    Generate a QR code PNG. Returns the written path, or None if qrcode not installed.
    """
    if qrcode is None:
        return None
    ensure_dir(out_path.parent)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(out_path)
    return out_path


# -----------------------------
# Prompt/confirm
# -----------------------------
def confirm_action(prompt: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    response = input(f"{prompt} [{default_str}]: ").lower().strip()
    if not response:
        return default
    return response in ("y", "yes")


# -----------------------------
# Collections
# -----------------------------
def dedup_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
