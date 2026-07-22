"""Shared credential helper for booking-system adapters.

Centralises credential resolution so every adapter (existing + new) reads its keys
the same way, and we can migrate plaintext booking keys to Fernet-encrypted-at-rest
without touching each adapter.

``get_credential(client, key)`` returns plaintext. Whether the stored value is
decrypted depends on an explicit key-name mapping (per the plan's D4): keys that
are stored encrypted-at-rest are decrypted via :func:`services.crypto.decrypt`;
plaintext keys (current Cliniko/Square) are returned raw for back-compat.
"""
# Credential columns that are stored Fernet-encrypted at rest. Every other column
# is read as plaintext (back-compat with the current plaintext Cliniko/Square keys).
# Add a key here when its column is migrated to encrypted storage.
_ENCRYPTED_KEYS: set[str] = {"halaxy_client_secret"}


def get_credential(client: dict, key: str) -> str:
    """Return the plaintext value of ``client[key]``.

    For keys known to be stored encrypted (see :data:`_ENCRYPTED_KEYS`), decrypts via
    :func:`services.crypto.decrypt`; if decryption fails (e.g. the value is still
    plaintext during dev / pre-backfill, or the encryption key is unset) the raw
    value is returned for back-compat (part-clinical: "decrypt when encrypted, else
    plaintext"). For plaintext keys the raw value is returned directly. Returns
    ``""`` when the key is missing or empty — never raises.
    """
    value = client.get(key) if isinstance(client, dict) else None
    if not value:
        return ""
    if key in _ENCRYPTED_KEYS:
        try:
            from services.crypto import decrypt
            return decrypt(value)
        except Exception:
            # Not a valid Fernet token (plaintext / pre-backfill) or key unset —
            # fall back to the raw value (back-compat with current plaintext keys).
            return value
    return value
