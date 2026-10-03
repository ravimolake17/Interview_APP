from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import numpy as np
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_token(subject: str, token_type: str, minutes: int, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    payload.update(extra or {})
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_embedding(vector: np.ndarray) -> bytes:
    data = np.asarray(vector, dtype=np.float32).tobytes()
    return _fernet().encrypt(data)


def decrypt_embedding(blob: bytes) -> np.ndarray:
    try:
        raw = _fernet().decrypt(blob)
    except InvalidToken as exc:
        raise ValueError("biometric baseline decryption failed") from exc
    return np.frombuffer(raw, dtype=np.float32).copy()
