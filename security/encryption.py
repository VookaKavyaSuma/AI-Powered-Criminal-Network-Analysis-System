"""
encryption.py — Field-level encryption for sensitive intelligence data (informants, undercover notes).

Uses Fernet symmetric encryption with key derived from FERNET_KEY in .env.
"""

import os
from typing import Optional

from cryptography.fernet import Fernet
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

_fernet_instance = None


def get_fernet() -> Fernet:
    """Initialize and return Fernet encryption instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = os.getenv("FERNET_KEY")
        if not key or "change_me" in key:
            key_path = os.path.join(PROJECT_ROOT, ".fernet_key")
            if os.path.exists(key_path):
                with open(key_path, "rb") as f:
                    key = f.read().strip()
            else:
                key = Fernet.generate_key()
                with open(key_path, "wb") as f:
                    f.write(key)
        elif isinstance(key, str):
            key = key.encode()
        try:
            _fernet_instance = Fernet(key)
        except Exception:
            key = Fernet.generate_key()
            key_path = os.path.join(PROJECT_ROOT, ".fernet_key")
            with open(key_path, "wb") as f:
                f.write(key)
            _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_field(plaintext: str) -> str:
    """Encrypt a plaintext string into Fernet ciphertext token."""
    if not plaintext:
        return ""
    fernet = get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_field(ciphertext: str) -> str:
    """Decrypt a Fernet ciphertext token back into plaintext."""
    if not ciphertext:
        return ""
    fernet = get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        return "[DECRYPTION_FAILED]"
