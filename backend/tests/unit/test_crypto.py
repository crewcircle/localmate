"""Tests for Fernet encryption/decryption."""
import pytest
from unittest.mock import patch


def test_fernet_encrypt_decrypt_roundtrip():
    """Encrypt then decrypt returns original plaintext."""
    import services.crypto as crypto_module

    crypto_module._fernet = None

    test_key = "UvF5RUL6_NB18gPF4KW87awgiC_S6--EqbzvA_UsSFQ="

    with patch.object(crypto_module, "settings") as mock_settings:
        mock_settings.encryption_key = test_key

        plaintext = "Sydney Dental Clinic API key: sk_live_abc123"
        encrypted = crypto_module.encrypt(plaintext)
        decrypted = crypto_module.decrypt(encrypted)

    assert decrypted == plaintext
    assert encrypted != plaintext

    crypto_module._fernet = None
