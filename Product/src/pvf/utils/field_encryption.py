from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

STORED_SECRET_PREFIX = "enc:v1:"


def _settings():
    from ..config.pvf_config_settings import pvf_settings

    return pvf_settings


def _fernet_key_bytes() -> bytes:
    s = _settings()
    raw = str(getattr(s, "PVF_FIELD_ENCRYPTION_KEY", "") or "").strip()
    if not raw:
        raw = str(getattr(s, "JWT_SECRET_KEY", "") or "")
    material = raw.encode("utf-8") if raw else b"pvf-field-encryption-fallback"
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"pvf-field-enc-v1",
        info=b"customer-secret-fields",
    ).derive(material)
    return base64.urlsafe_b64encode(derived)


def encrypt_secret(plaintext: str | None) -> str:
    value = "" if plaintext is None else str(plaintext)
    if value == "":
        return ""
    token = Fernet(_fernet_key_bytes()).encrypt(value.encode("utf-8"))
    return STORED_SECRET_PREFIX + token.decode("ascii")


def decrypt_secret(stored: str | None) -> str:
    value = "" if stored is None else str(stored)
    if value == "":
        return ""
    if not value.startswith(STORED_SECRET_PREFIX):
        return value
    try:
        token = value[len(STORED_SECRET_PREFIX):].encode("ascii")
        return Fernet(_fernet_key_bytes()).decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def is_stored_secret(value: str | None) -> bool:
    return bool(value) and str(value).startswith(STORED_SECRET_PREFIX)


def secret_fingerprint(stored: str | None) -> str:
    value = "" if stored is None else str(stored)
    if not value:
        return ""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
