"""Authentication helpers for PlacementOS.

Two roles use this:
  - admin    : Placement Committee, manages student records
  - student  : logs in with Student ID + password, sees only their own dashboard

Passwords are never stored in plaintext — only a salted PBKDF2-SHA256 hash.
This is intentionally dependency-free (stdlib `hashlib` only) so it drops
into the existing prototype without touching requirements.txt.
"""
import hashlib
import os
import binascii

ITERATIONS = 100_000


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash `password` with PBKDF2-SHA256. Generates a new random salt if
    `salt` (hex string) isn't given — pass the stored salt back in to verify.
    Returns (password_hash_hex, salt_hex)."""
    salt_bytes = os.urandom(16) if salt is None else binascii.unhexlify(salt)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, ITERATIONS)
    return digest.hex(), salt_bytes.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Re-hashes `password` with the stored salt and compares to the stored hash."""
    check_hash, _ = hash_password(password, salt)
    return check_hash == password_hash
