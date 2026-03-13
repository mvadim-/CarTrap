"""VIN decoding helpers for Copart payloads."""

from __future__ import annotations

import base64


KEY = "g2memberutil97534"


def decode_encrypted_vin(encrypted_vin: str, key: str = KEY) -> str:
    encrypted_bytes = base64.b64decode(encrypted_vin)

    vin_chars: list[str] = []
    for i, byte in enumerate(encrypted_bytes):
        vin_chars.append(chr(byte ^ ord(key[i])))

    return "".join(vin_chars)


def try_decode_encrypted_vin(encrypted_vin: str | None, key: str = KEY) -> str | None:
    if not encrypted_vin:
        return None
    try:
        return decode_encrypted_vin(encrypted_vin, key=key)
    except Exception:
        return None
