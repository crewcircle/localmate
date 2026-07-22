"""Tests for the shared booking-credential helper."""
from unittest.mock import patch

from services.booking_credentials import get_credential


def test_get_credential_plaintext_returned_raw():
    """cliniko_api_key is a plaintext column — returned as-is (no decrypt)."""
    client = {"cliniko_api_key": "raw-cliniko-key"}
    assert get_credential(client, "cliniko_api_key") == "raw-cliniko-key"


def test_get_credential_decrypts_encrypted_key():
    """halaxy_client_secret is stored Fernet-encrypted — decrypted via crypto.decrypt."""
    client = {"halaxy_client_secret": "gAAAAAB-encrypted-token"}
    with patch("services.crypto.decrypt", return_value="decrypted-secret") as mock_decrypt:
        result = get_credential(client, "halaxy_client_secret")
    assert result == "decrypted-secret"
    mock_decrypt.assert_called_once_with("gAAAAAB-encrypted-token")


def test_get_credential_missing_key_returns_empty():
    assert get_credential({}, "nookal_api_key") == ""


def test_get_credential_empty_value_returns_empty():
    assert get_credential({"cliniko_api_key": ""}, "cliniko_api_key") == ""


def test_get_credential_none_client_returns_empty():
    assert get_credential(None, "cliniko_api_key") == ""


def test_get_credential_decrypt_failure_falls_back_to_raw():
    """A decrypt failure (plaintext / pre-backfill value, or unset key) falls back to
    the raw value for back-compat rather than raising or returning empty."""
    client = {"halaxy_client_secret": "plaintext-secret"}
    with patch("services.crypto.decrypt", side_effect=Exception("InvalidToken")):
        assert get_credential(client, "halaxy_client_secret") == "plaintext-secret"
