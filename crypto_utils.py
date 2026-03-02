"""
AES-256-GCM encryption utilities for exam answer protection.

Key hierarchy:
  Master key (env var) -> wraps per-exam keys -> encrypt individual answers.

Every answer gets a unique IV.  AES-GCM provides authenticated encryption,
so any ciphertext tampering is detected on decryption.  An additional
HMAC-SHA256 integrity hash is stored as an independent audit trail.
"""

import base64
import hashlib
import hmac
import os
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ---------------------------------------------------------------------------
#  Master key helpers
# ---------------------------------------------------------------------------

def generate_master_key() -> str:
    """Return a random 256-bit key as a URL-safe base64 string.

    Run once, then store the result in the EXAM_MASTER_KEY env var.
    """
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def load_master_key() -> bytes:
    """Read the master key from the environment and decode it."""
    raw = os.environ.get("EXAM_MASTER_KEY")
    if not raw:
        raise RuntimeError(
            "EXAM_MASTER_KEY environment variable is not set. "
            "Generate one with: python -c \"from crypto_utils import generate_master_key; print(generate_master_key())\""
        )
    return base64.urlsafe_b64decode(raw)


# ---------------------------------------------------------------------------
#  Per-exam key management
# ---------------------------------------------------------------------------

def generate_exam_key() -> bytes:
    """Return a fresh random 256-bit AES key (32 bytes)."""
    return os.urandom(32)


def encrypt_exam_key(exam_key: bytes, master_key: bytes) -> tuple[bytes, bytes, bytes]:
    """Wrap *exam_key* with *master_key* using AES-256-GCM.

    Returns (ciphertext, iv, tag) where tag is the last 16 bytes of the
    AESGCM ciphertext (GCM appends it automatically).
    """
    iv = os.urandom(12)
    aesgcm = AESGCM(master_key)
    ct_with_tag = aesgcm.encrypt(iv, exam_key, None)
    ciphertext = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]
    return ciphertext, iv, tag


def decrypt_exam_key(ciphertext: bytes, iv: bytes, tag: bytes, master_key: bytes) -> bytes:
    """Unwrap a per-exam key.  Raises on tamper."""
    aesgcm = AESGCM(master_key)
    return aesgcm.decrypt(iv, ciphertext + tag, None)


# ---------------------------------------------------------------------------
#  Answer encryption / decryption
# ---------------------------------------------------------------------------

def encrypt_answer(plaintext: str, exam_key: bytes) -> tuple[bytes, bytes, bytes]:
    """Encrypt an answer string with the exam's AES key.

    Returns (ciphertext, iv, tag).
    """
    iv = os.urandom(12)
    aesgcm = AESGCM(exam_key)
    ct_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    ciphertext = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]
    return ciphertext, iv, tag


def decrypt_answer(ciphertext: bytes, iv: bytes, tag: bytes, exam_key: bytes) -> str:
    """Decrypt an answer.  Raises ``cryptography.exceptions.InvalidTag`` on tamper."""
    aesgcm = AESGCM(exam_key)
    plaintext_bytes = aesgcm.decrypt(iv, ciphertext + tag, None)
    return plaintext_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
#  HMAC integrity hash
# ---------------------------------------------------------------------------

def compute_integrity_hash(
    master_key: bytes,
    answer_text: str,
    question_id: int,
    session_id: int,
    timestamp: datetime,
) -> str:
    """Compute HMAC-SHA256 over the answer and its metadata.

    Returns the hex digest (64 chars).
    """
    ts_str = timestamp.isoformat()
    message = f"{answer_text}|{question_id}|{session_id}|{ts_str}"
    return hmac.new(master_key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_integrity_hash(
    master_key: bytes,
    answer_text: str,
    question_id: int,
    session_id: int,
    timestamp: datetime,
    expected_hash: str,
) -> bool:
    """Constant-time comparison of the stored hash against a recomputed one."""
    computed = compute_integrity_hash(
        master_key, answer_text, question_id, session_id, timestamp
    )
    return hmac.compare_digest(computed, expected_hash)


# ---------------------------------------------------------------------------
#  CLI convenience
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    key = generate_master_key()
    print("Generated EXAM_MASTER_KEY (add to your environment):\n")
    print(f"  export EXAM_MASTER_KEY=\"{key}\"\n")
