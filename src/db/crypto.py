"""
Utility functions for encrypting and decrypting sensitive values.

Uses Fernet symmetric encryption from the ``cryptography`` package. The
module automatically generates a key if one does not exist and stores it
near the running project.
"""

import os
from typing import Optional
from cryptography.fernet import Fernet

# Path where the secret key will be stored
KEY_PATH = os.path.join(os.getcwd(), '.secret.key')

_fernet: Optional[Fernet] = None

def _load_key() -> bytes:
    """Loads an existing key or generates a new one."""
    if os.path.exists(KEY_PATH):
        return open(KEY_PATH, 'rb').read()
    key = Fernet.generate_key()
    with open(KEY_PATH, 'wb') as fh:
        fh.write(key)
    return key

def get_fernet() -> Fernet:
    """Returns a lazily initialised Fernet instance."""
    global _fernet
    if _fernet is None:
        key = _load_key()
        _fernet = Fernet(key)
    return _fernet

def encrypt(value: str) -> str:
    """Encrypts a string value and returns the token."""
    if value is None:
        return ''
    f = get_fernet()
    token = f.encrypt(value.encode('utf-8'))
    return token.decode('utf-8')

def decrypt(token: str) -> Optional[str]:
    """Decrypts a value previously returned by :func:`encrypt`."""
    if not token:
        return None
    f = get_fernet()
    try:
        value = f.decrypt(token.encode('utf-8'))
        return value.decode('utf-8')
    except Exception:
        return None
