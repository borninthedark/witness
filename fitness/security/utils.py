from __future__ import annotations

import secrets


def generate_nonce(length: int = 16) -> str:
    # 128 bits default
    return secrets.token_urlsafe(length)
