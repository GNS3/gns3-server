#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Encryption utilities for sensitive data like API keys.
Uses Fernet symmetric encryption.
"""

import os
import secrets
import logging
from typing import Optional
from cryptography.fernet import Fernet

log = logging.getLogger(__name__)

# Global encryption key - will be loaded from config
_fernet: Optional[Fernet] = None


def init_encryption(secrets_dir: str) -> None:
    """
    Initialize encryption by loading or generating the encryption key.

    :param secrets_dir: Directory to store the encryption key
    """

    global _fernet

    encryption_key_path = os.path.join(secrets_dir, "gns3_encryption_key")

    if not os.path.exists(encryption_key_path):
        log.info(f"No encryption key found, generating one in '{encryption_key_path}'...")
        try:
            key = Fernet.generate_key()
            os.makedirs(secrets_dir, exist_ok=True)
            with open(encryption_key_path, "w", encoding="utf-8") as f:
                # Use Fernet's base64-encoded key format
                f.write(key.decode() if isinstance(key, bytes) else key)
            # Set restrictive permissions (owner read/write only)
            os.chmod(encryption_key_path, 0o600)
        except OSError as e:
            log.error(f"Could not create encryption key file '{encryption_key_path}': {e}")
            raise

    try:
        with open(encryption_key_path, encoding="utf-8") as f:
            key_content = f.read().strip()
        _fernet = Fernet(key_content.encode() if isinstance(key_content, str) else key_content)
        log.debug("Encryption initialized successfully")
    except OSError as e:
        log.error(f"Could not read encryption key file '{encryption_key_path}': {e}")
        raise


def encrypt(plaintext: str) -> str:
    """
    Encrypt a plaintext string.

    :param plaintext: The plaintext to encrypt
    :returns: Base64-encoded encrypted string
    :raises RuntimeError: If encryption is not initialized
    """

    if _fernet is None:
        raise RuntimeError("Encryption not initialized. Call init_encryption() first.")

    if not plaintext:
        return ""

    encrypted = _fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a ciphertext string.

    :param ciphertext: The base64-encoded encrypted string
    :returns: Decrypted plaintext string
    :raises RuntimeError: If encryption is not initialized
    :raises ValueError: If decryption fails (invalid data or wrong key)
    """

    if _fernet is None:
        raise RuntimeError("Encryption not initialized. Call init_encryption() first.")

    if not ciphertext:
        return ""

    try:
        decrypted = _fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}") from e


def is_encrypted(value: str) -> bool:
    """
    Check if a value appears to be encrypted (heuristic).

    :param value: The value to check
    :returns: True if the value appears to be encrypted
    """

    if not value:
        return False

    # Fernet encrypted data is URL-safe base64 and has a specific structure
    # Check for Fernet prefix and valid format
    try:
        # Fernet tokens always start with 'gAAAAA' in base64
        if not value.startswith('gAAAAA'):
            return False
        # Attempt to decode as URL-safe base64
        import base64
        decoded = base64.urlsafe_b64decode(value)
        # Fernet tokens have a specific format (minimum 32 bytes)
        return len(decoded) >= 32
    except Exception:
        return False


def re_encrypt(old_key_path: str, new_key_path: str) -> None:
    """
    Re-encrypt data with a new key (for key rotation).

    :param old_key_path: Path to the old encryption key
    :param new_key_path: Path to the new encryption key
    """

    global _fernet

    # Load old key and decrypt all data
    with open(old_key_path, encoding="utf-8") as f:
        old_key = f.read().strip().encode()

    old_fernet = Fernet(old_key)

    # This would be used during a key rotation migration
    # Implementation depends on how data is stored
    log.warning("Key rotation not yet implemented")
