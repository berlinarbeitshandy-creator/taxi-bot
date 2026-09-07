"""Verschluesselung fuer Session-Strings und API-Hashes.

Die Telethon-Session ist ein Vollzugriff auf den Account - sie darf nicht
im Klartext in der Datenbank liegen. Der Schluessel kommt aus
PANEL_SECRET_KEY oder wird einmalig unter data/.secret erzeugt.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from .config import SECRET_PATH


def _load_key() -> bytes:
    raw = os.getenv("PANEL_SECRET_KEY", "").strip()
    if raw:
        try:
            Fernet(raw.encode())
            return raw.encode()
        except (ValueError, TypeError):
            # Beliebige Passphrase -> auf einen gueltigen Fernet-Key ableiten.
            digest = hashlib.sha256(raw.encode()).digest()
            return base64.urlsafe_b64encode(digest)

    if SECRET_PATH.exists():
        return SECRET_PATH.read_bytes().strip()

    key = Fernet.generate_key()
    SECRET_PATH.write_bytes(key)
    os.chmod(SECRET_PATH, 0o600)
    return key


_fernet = Fernet(_load_key())


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return None
